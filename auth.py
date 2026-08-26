# -*- coding: utf-8 -*-
"""
Auth: signup/login routes + the before_request guard that locks down every
other route on the Flask app. gearledger.server.GearLedgerServer ships with
zero auth on any route — this is what makes running it on the public
internet safe.

No refresh-token flow yet — a single longish-lived access token is the
simplest thing that works for an early self-serve product. Revisit if
"log back in every week" turns out to be annoying in practice.
"""
import datetime
import os

import flask
from flask import jsonify, request
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt,
    get_jwt_identity,
    verify_jwt_in_request,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from accounts import get_accounts_store

# Routes reachable without a JWT.
_PUBLIC_PATHS = {"/api/auth/signup", "/api/auth/login", "/api/status"}

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


def init_auth(app: flask.Flask) -> None:
    app.config["JWT_SECRET_KEY"] = _load_jwt_secret()
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(days=7)
    JWTManager(app)

    # In-memory storage: rate limits are per-process, not shared across
    # gunicorn workers. Fine for a single worker (today's deployment size);
    # revisit with a Redis storage_uri if/when this runs with >1 worker.
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

        token = create_access_token(
            identity=user["id"], additional_claims={"tenant_id": user["tenant_id"]}
        )
        return jsonify({"access_token": token, "tenant_id": user["tenant_id"]}), 201

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

        token = create_access_token(
            identity=user["id"], additional_claims={"tenant_id": user["tenant_id"]}
        )
        return jsonify({"access_token": token, "tenant_id": user["tenant_id"]}), 200
