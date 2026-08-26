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

from accounts import get_accounts_store

# Routes reachable without a JWT. GEARLEDGER_JWT_SECRET should always be set
# in real deployments — the fallback below is only so local dev doesn't
# require extra setup, and is loud about it so it can't be mistaken for a
# real deployment secret.
_PUBLIC_PATHS = {"/api/auth/signup", "/api/auth/login", "/api/status"}


def init_auth(app: flask.Flask) -> None:
    secret = os.getenv("GEARLEDGER_JWT_SECRET")
    if not secret:
        secret = "dev-only-insecure-secret-do-not-deploy"
        print(
            "[AUTH] WARNING: GEARLEDGER_JWT_SECRET not set — using an "
            "insecure development default. Set it before deploying anywhere "
            "reachable from outside localhost."
        )
    app.config["JWT_SECRET_KEY"] = secret
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(days=7)
    JWTManager(app)

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
