# -*- coding: utf-8 -*-
"""
Auth: signup/login/refresh/logout/password-reset routes + the
before_request guard that locks down every other route on the Flask app.
gearledger.server.GearLedgerServer ships with zero auth on any route —
this is what makes running it on the public internet safe.

Access/refresh split: a short-lived access token (30 min) is what every
ordinary request carries; a longer-lived refresh token (30 days) is only
ever sent to /api/auth/refresh to mint a new access token. Refresh tokens
are individually revocable via the `sessions` table in accounts.py (see
its module docstring) — logging out, or a password reset, actually means
something instead of just "the client deleted its local copy."
"""
import datetime
import os

import flask
from flask import jsonify, request
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    verify_jwt_in_request,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from accounts import get_accounts_store
from email_sender import get_email_sender

# Routes reachable without a valid *access* token. /api/auth/refresh and
# /api/auth/logout are "public" in that sense too — they authenticate via
# an explicit refresh-token check of their own (see below) rather than
# the access-token check every other route gets from before_request.
_PUBLIC_PATHS = {
    "/api/auth/signup",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/auth/password-reset/request",
    "/api/auth/password-reset/confirm",
    "/api/status",
}

_MIN_SECRET_BYTES = 32  # matches HS256's recommended minimum key length


def _load_jwt_secret() -> str:
    """No insecure fallback: a missing or weak secret fails the boot loudly
    instead of quietly signing tokens with something guessable. (This is
    what an earlier version of this file didn't do — it fell back to a
    hardcoded dev string, which is exactly the kind of thing that survives
    into a real deployment by accident.)

    For local dev: export GEARLEDGER_JWT_SECRET="$(openssl rand -hex 32)"
    """
    secret = os.getenv("GEARLEDGER_JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "GEARLEDGER_JWT_SECRET is not set. Generate one with "
            "`openssl rand -hex 32` and export it before starting the "
            "server — there is no dev fallback, so tokens are never signed "
            "with a guessable key."
        )
    if len(secret.encode()) < _MIN_SECRET_BYTES:
        raise RuntimeError(
            f"GEARLEDGER_JWT_SECRET is only {len(secret.encode())} bytes — "
            f"need at least {_MIN_SECRET_BYTES} for HS256. Generate one with "
            "`openssl rand -hex 32`."
        )
    return secret


def _issue_tokens(user_id: str, tenant_id: str) -> dict:
    """Mint a fresh access+refresh pair and record the refresh token's
    session row so it can later be individually revoked (logout, a
    password reset, or a future "sign out this device")."""
    additional_claims = {"tenant_id": tenant_id}
    access_token = create_access_token(
        identity=user_id, additional_claims=additional_claims
    )
    refresh_token = create_refresh_token(
        identity=user_id, additional_claims=additional_claims
    )

    decoded = decode_token(refresh_token)
    expires_at = datetime.datetime.utcfromtimestamp(decoded["exp"]).isoformat()
    get_accounts_store().create_session(decoded["jti"], user_id, expires_at)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "tenant_id": tenant_id,
    }


def init_auth(app: flask.Flask) -> Limiter:
    app.config["JWT_SECRET_KEY"] = _load_jwt_secret()
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(minutes=30)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = datetime.timedelta(days=30)
    jwt = JWTManager(app)

    @jwt.token_in_blocklist_loader
    def _check_if_revoked(jwt_header, jwt_payload):
        # This callback runs for every token verified, access and refresh
        # alike — there's no built-in "only check refresh tokens" config
        # in this version of flask-jwt-extended, so that filtering has to
        # happen here. Only refresh tokens get a sessions row in the first
        # place (see _issue_tokens); access tokens just expire naturally
        # every 30 min, so there's no DB lookup to do (or session row to
        # find) for them — treating every access token as revoked because
        # it has no session row would be wrong, not "safe."
        if jwt_payload.get("type") != "refresh":
            return False
        return get_accounts_store().is_session_revoked(jwt_payload["jti"])

    # In-memory storage: rate limits are per-process, not shared across
    # gunicorn workers. Fine for a single worker (today's deployment size);
    # revisit with a Redis storage_uri if/when this runs with >1 worker.
    # Returned so routes.py can put a tighter limit on /api/scan, which
    # costs real money per call unlike everything else here.
    limiter = Limiter(get_remote_address, app=app, storage_uri="memory://")

    @app.before_request
    def _require_auth():
        if request.method == "OPTIONS" or request.path in _PUBLIC_PATHS:
            return None
        try:
            verify_jwt_in_request()
        except Exception as exc:
            return jsonify({"error": "unauthorized", "detail": str(exc)}), 401
        claims = get_jwt()
        flask.g.user_id = get_jwt_identity()
        flask.g.tenant_id = claims["tenant_id"]
        return None

    @app.route("/api/auth/signup", methods=["POST"])
    @limiter.limit("5 per hour")
    def signup():
        body = request.get_json(silent=True) or {}
        email = (body.get("email") or "").strip()
        password = body.get("password") or ""
        if not email or not password:
            return jsonify({"error": "email and password are required"}), 400
        if len(password) < 8:
            return jsonify({"error": "password must be at least 8 characters"}), 400

        try:
            user = get_accounts_store().create_tenant_and_user(email, password)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409

        tokens = _issue_tokens(user["id"], user["tenant_id"])
        return jsonify(tokens), 201

    @app.route("/api/auth/login", methods=["POST"])
    @limiter.limit("10 per minute")
    def login():
        body = request.get_json(silent=True) or {}
        email = (body.get("email") or "").strip()
        password = body.get("password") or ""
        if not email or not password:
            return jsonify({"error": "email and password are required"}), 400

        user = get_accounts_store().verify_login(email, password)
        if user is None:
            return jsonify({"error": "invalid email or password"}), 401

        tokens = _issue_tokens(user["id"], user["tenant_id"])
        return jsonify(tokens), 200

    @app.route("/api/auth/refresh", methods=["POST"])
    @limiter.limit("30 per minute")
    def refresh():
        try:
            verify_jwt_in_request(refresh=True)
        except Exception as exc:
            return jsonify({"error": "unauthorized", "detail": str(exc)}), 401

        claims = get_jwt()
        user_id = get_jwt_identity()
        tenant_id = claims["tenant_id"]

        # Rotation: the refresh token just used to get here is revoked
        # immediately, so it can't also be replayed later. The caller
        # gets a brand-new refresh token in the response to use next time.
        get_accounts_store().revoke_session(claims["jti"])

        tokens = _issue_tokens(user_id, tenant_id)
        return jsonify(tokens), 200

    @app.route("/api/auth/logout", methods=["POST"])
    @limiter.limit("10 per minute")
    def logout():
        try:
            verify_jwt_in_request(refresh=True)
        except Exception as exc:
            return jsonify({"error": "unauthorized", "detail": str(exc)}), 401

        get_accounts_store().revoke_session(get_jwt()["jti"])
        return jsonify({"ok": True}), 200

    @app.route("/api/auth/password-reset/request", methods=["POST"])
    @limiter.limit("3 per hour")
    def password_reset_request():
        body = request.get_json(silent=True) or {}
        email = (body.get("email") or "").strip()

        # Always the same response regardless of whether the email has an
        # account — otherwise this endpoint becomes a way to enumerate
        # registered emails one guess at a time.
        generic_response = jsonify(
            {"ok": True, "message": "If that email has an account, a reset code was sent."}
        )

        if not email:
            return generic_response, 200

        user = get_accounts_store().get_user_by_email(email)
        if user is None:
            return generic_response, 200

        code = get_accounts_store().create_password_reset(user["id"])
        try:
            get_email_sender().send_password_reset_email(user["email"], code)
        except RuntimeError as exc:
            # Only reachable if RESEND_API_KEY isn't configured or Resend
            # itself errored — a real operational problem worth a distinct
            # status code, not something to hide behind the generic 200
            # (that 200 is about not leaking *which emails have accounts*,
            # not about hiding "email sending is broken").
            return jsonify({"error": str(exc)}), 503

        return generic_response, 200

    @app.route("/api/auth/password-reset/confirm", methods=["POST"])
    @limiter.limit("5 per hour")
    def password_reset_confirm():
        body = request.get_json(silent=True) or {}
        code = (body.get("code") or "").strip().upper()
        new_password = body.get("new_password") or ""
        if not code or not new_password:
            return jsonify({"error": "code and new_password are required"}), 400
        if len(new_password) < 8:
            return jsonify({"error": "password must be at least 8 characters"}), 400

        user_id = get_accounts_store().consume_password_reset(code, new_password)
        if user_id is None:
            return jsonify({"error": "invalid or expired code"}), 400

        # A reset means any refresh token issued before it should stop
        # working — the credential that vouched for the account holder
        # just changed.
        get_accounts_store().revoke_all_sessions_for_user(user_id)
        return jsonify({"ok": True}), 200

    return limiter
