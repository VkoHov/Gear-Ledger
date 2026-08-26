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
import os
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Optional, TypedDict

from werkzeug.security import check_password_hash, generate_password_hash


class User(TypedDict):
    id: str
    email: str
    tenant_id: str


def _default_db_path() -> str:
    return os.getenv("GEARLEDGER_ACCOUNTS_DB_PATH", "accounts.db")


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
        # Hash before opening any write transaction: pbkdf2 is pure Python/C
        # with no DB access, so if it ever raises, nothing has been written
        # and there's no dangling transaction left holding SQLite's write
        # lock for other requests.
        #
        # Pinned to pbkdf2 rather than werkzeug's scrypt default: scrypt
        # needs hashlib.scrypt, which requires OpenSSL built with scrypt
        # support — unavailable under LibreSSL (the macOS system Python's
        # SSL backend), so the default crashes signup in that environment.
        password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        conn.execute(
            "INSERT INTO tenants (id, name) VALUES (?, ?)", (tenant_id, email)
        )
        conn.execute(
            "INSERT INTO users (id, email, password_hash, tenant_id) VALUES (?, ?, ?, ?)",
            (user_id, email, password_hash, tenant_id),
        )
        conn.commit()
        return {"id": user_id, "email": email, "tenant_id": tenant_id}

    def verify_login(self, email: str, password: str) -> Optional[User]:
        """Returns the User dict on success, None on bad email/password."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT id, email, password_hash, tenant_id FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
        if row is None or not check_password_hash(row["password_hash"], password):
            return None
        return {"id": row["id"], "email": row["email"], "tenant_id": row["tenant_id"]}


_store: Optional[AccountsStore] = None
_store_lock = threading.Lock()


def get_accounts_store() -> AccountsStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = AccountsStore()
    return _store
