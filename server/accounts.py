# -*- coding: utf-8 -*-
"""
Central accounts/tenants store — genuinely new, web-only state that has no
analog in the desktop app (which has no concept of a login or a tenant).

Deliberately separate from gearledger.database.Database: that class holds
one tenant's *results* (scanned parts, catalog matches), one SQLite file
per tenant. This module holds the small, shared table of who's allowed to
log in and which tenant they belong to — a different lifecycle, a different
file, queried on every request instead of per-tenant.
"""
import datetime
import os
import secrets
import sqlite3
import string
import threading
import uuid
from pathlib import Path
from typing import Optional, TypedDict

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Password-reset codes: 8 chars, uppercase + digits, ambiguous characters
# (0/O, 1/I/L) excluded — this is typed back in by hand from an email, so
# it needs to survive a human copying it without transcription errors.
_RESET_CODE_ALPHABET = "".join(
    c for c in string.ascii_uppercase + string.digits if c not in "0O1IL"
)


class User(TypedDict):
    id: str
    email: str
    tenant_id: str
    is_admin: bool
    subscription_status: str


class Account(TypedDict):
    tenant_id: str
    email: str
    created_at: str
    subscription_status: str


def _default_db_path() -> str:
    return os.getenv("GEARLEDGER_ACCOUNTS_DB_PATH", "accounts.db")


# argon2id, not werkzeug's default (scrypt via hashlib, which needs OpenSSL
# built with scrypt support — unavailable under LibreSSL, the macOS system
# Python's SSL backend). argon2-cffi doesn't go through OpenSSL at all, so
# this sidesteps that instead of trading one hashing weakness for another.
_hasher = PasswordHasher()


class AccountsStore:
    """Thread-safe SQLite store for tenants and users."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_db_path()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path, check_same_thread=False, timeout=30.0
            )
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _init_db(self):
        conn = self._get_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                tenant_id TEXT NOT NULL REFERENCES tenants(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # One row per issued refresh token. What makes revocation
        # (logout, a password reset, a future "sign out this device")
        # actually mean something — a stateless-only JWT refresh token is
        # valid until it expires no matter what the server "thinks"
        # happened to it.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                jti TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_resets (
                code TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()
        self._migrate_add_columns(conn)

    def _migrate_add_columns(self, conn: sqlite3.Connection) -> None:
        """CREATE TABLE IF NOT EXISTS (above) only creates tables that
        don't exist yet — it never adds a column to a table this class
        already shipped without one. Idempotent, safe on every boot."""
        users_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "is_admin" not in users_columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")

        tenants_columns = {row["name"] for row in conn.execute("PRAGMA table_info(tenants)")}
        if "subscription_status" not in tenants_columns:
            # 'inactive' by default: a signup alone doesn't grant access —
            # this is the actual manual-activation gate, until Stripe
            # exists to set it automatically.
            conn.execute(
                "ALTER TABLE tenants ADD COLUMN subscription_status TEXT NOT NULL DEFAULT 'inactive'"
            )
        conn.commit()

    def create_tenant_and_user(self, email: str, password: str) -> User:
        """Sign up a brand-new account: one tenant, one user, that user
        owning it. Raises ValueError if the email is already registered."""
        conn = self._get_connection()
        email = email.strip().lower()
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise ValueError("email already registered")

        tenant_id = uuid.uuid4().hex
        user_id = uuid.uuid4().hex
        # Hash before opening any write transaction: hashing is pure CPU
        # work with no DB access, so if it ever raises, nothing has been
        # written and there's no dangling transaction left holding SQLite's
        # write lock for other requests.
        password_hash = _hasher.hash(password)

        conn.execute(
            "INSERT INTO tenants (id, name) VALUES (?, ?)", (tenant_id, email)
        )
        conn.execute(
            "INSERT INTO users (id, email, password_hash, tenant_id) VALUES (?, ?, ?, ?)",
            (user_id, email, password_hash, tenant_id),
        )
        conn.commit()
        return {
            "id": user_id,
            "email": email,
            "tenant_id": tenant_id,
            "is_admin": False,
            "subscription_status": "inactive",
        }

    # Shared by verify_login/get_user_by_email/promote_to_admin_if_listed —
    # every caller that resolves "a user" needs is_admin and the tenant's
    # subscription_status alongside it, so this is the one place that JOIN
    # lives instead of four slightly-different copies of it.
    _USER_SELECT = (
        "SELECT users.id, users.email, users.tenant_id, users.password_hash, "
        "users.is_admin, tenants.subscription_status "
        "FROM users JOIN tenants ON users.tenant_id = tenants.id "
    )

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return {
            "id": row["id"],
            "email": row["email"],
            "tenant_id": row["tenant_id"],
            "is_admin": bool(row["is_admin"]),
            "subscription_status": row["subscription_status"],
        }

    def verify_login(self, email: str, password: str) -> Optional[User]:
        """Returns the User dict on success, None on bad email/password."""
        conn = self._get_connection()
        row = conn.execute(
            self._USER_SELECT + "WHERE users.email = ?",
            (email.strip().lower(),),
        ).fetchone()
        if row is None:
            return None
        try:
            _hasher.verify(row["password_hash"], password)
        except VerifyMismatchError:
            return None
        return self._row_to_user(row)

    def get_user_by_email(self, email: str) -> Optional[User]:
        conn = self._get_connection()
        row = conn.execute(
            self._USER_SELECT + "WHERE users.email = ?",
            (email.strip().lower(),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        conn = self._get_connection()
        row = conn.execute(
            self._USER_SELECT + "WHERE users.id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def get_user_by_tenant_id(self, tenant_id: str) -> Optional[User]:
        """Today it's always exactly one user per tenant (see
        create_tenant_and_user), so "the tenant's user" is unambiguous —
        used by the admin dashboard's manual reset-code action, which
        only has a tenant_id (from list_accounts_with_status) to work
        from. Revisit if/when multi-user tenants exist."""
        conn = self._get_connection()
        row = conn.execute(
            self._USER_SELECT + "WHERE users.tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def promote_to_admin_if_listed(self, user_id: str, email: str) -> None:
        """Bootstraps admin access: if `email` appears in the
        GEARLEDGER_ADMIN_EMAILS env var (comma-separated, case-
        insensitive), grants is_admin. Idempotent — cheap to call on
        every login. This is the only way to become an admin; there's no
        UI path that grants it, deliberately (an admin dashboard that
        could create more admins through itself would be its own
        privilege-escalation surface)."""
        admin_emails = {
            e.strip().lower()
            for e in os.getenv("GEARLEDGER_ADMIN_EMAILS", "").split(",")
            if e.strip()
        }
        if email.strip().lower() not in admin_emails:
            return
        conn = self._get_connection()
        conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user_id,))
        conn.commit()

    # ------------------------------------------------------------------
    # Admin: account listing + subscription status
    # ------------------------------------------------------------------

    def list_accounts_with_status(self) -> list:
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT tenants.id AS tenant_id, users.email, tenants.created_at, "
            "tenants.subscription_status "
            "FROM tenants JOIN users ON users.tenant_id = tenants.id "
            "ORDER BY tenants.created_at DESC"
        ).fetchall()
        return [
            {
                "tenant_id": row["tenant_id"],
                "email": row["email"],
                "created_at": row["created_at"],
                "subscription_status": row["subscription_status"],
            }
            for row in rows
        ]

    def get_tenant_subscription_status(self, tenant_id: str) -> Optional[str]:
        conn = self._get_connection()
        row = conn.execute(
            "SELECT subscription_status FROM tenants WHERE id = ?", (tenant_id,)
        ).fetchone()
        return row["subscription_status"] if row else None

    def set_subscription_status(self, tenant_id: str, status: str) -> bool:
        """Returns False if tenant_id doesn't exist, True on success."""
        conn = self._get_connection()
        cursor = conn.execute(
            "UPDATE tenants SET subscription_status = ? WHERE id = ?",
            (status, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Sessions (refresh token revocation)
    # ------------------------------------------------------------------

    def create_session(self, jti: str, user_id: str, expires_at: str) -> None:
        conn = self._get_connection()
        conn.execute(
            "INSERT INTO sessions (jti, user_id, expires_at) VALUES (?, ?, ?)",
            (jti, user_id, expires_at),
        )
        conn.commit()

    def revoke_session(self, jti: str) -> None:
        conn = self._get_connection()
        conn.execute("UPDATE sessions SET revoked = 1 WHERE jti = ?", (jti,))
        conn.commit()

    def revoke_all_sessions_for_user(self, user_id: str) -> None:
        """Called on password reset — any refresh token issued before the
        reset should stop working, since the credential that vouched for
        the account holder just changed."""
        conn = self._get_connection()
        conn.execute("UPDATE sessions SET revoked = 1 WHERE user_id = ?", (user_id,))
        conn.commit()

    def is_session_revoked(self, jti: str) -> bool:
        """True if this refresh token's session is revoked, or was never
        recorded at all. The latter shouldn't happen for a token this
        server actually issued, but treating an unrecognized jti as
        revoked (rather than valid) is the safe default."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT revoked FROM sessions WHERE jti = ?", (jti,)
        ).fetchone()
        if row is None:
            return True
        return bool(row["revoked"])

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------

    def create_password_reset(self, user_id: str, ttl_minutes: int = 15) -> str:
        conn = self._get_connection()
        code = "".join(secrets.choice(_RESET_CODE_ALPHABET) for _ in range(8))
        expires_at = (
            datetime.datetime.utcnow() + datetime.timedelta(minutes=ttl_minutes)
        ).isoformat()
        conn.execute(
            "INSERT INTO password_resets (code, user_id, expires_at) VALUES (?, ?, ?)",
            (code, user_id, expires_at),
        )
        conn.commit()
        return code

    def consume_password_reset(self, code: str, new_password: str) -> Optional[str]:
        """Validates the code (exists, unused, unexpired), marks it used,
        and updates the user's password hash — all as one method so a
        code can't be raced into being consumed twice by two concurrent
        requests. Takes the plain new password (not a pre-hashed value)
        and hashes it internally, matching create_tenant_and_user's
        pattern of keeping hashing entirely inside this class. Returns
        the user_id on success, None on any validation failure (caller
        doesn't need to know *why* — a wrong, expired, or reused code all
        just mean "try again")."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT user_id, expires_at, used FROM password_resets WHERE code = ?",
            (code,),
        ).fetchone()
        if row is None or row["used"]:
            return None
        if datetime.datetime.fromisoformat(row["expires_at"]) < datetime.datetime.utcnow():
            return None

        user_id = row["user_id"]
        password_hash = _hasher.hash(new_password)
        conn.execute("UPDATE password_resets SET used = 1 WHERE code = ?", (code,))
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()
        return user_id


_store: Optional[AccountsStore] = None
_store_lock = threading.Lock()


def get_accounts_store() -> AccountsStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = AccountsStore()
    return _store
