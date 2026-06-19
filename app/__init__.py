from __future__ import annotations

import os
import warnings
from typing import List, Tuple, Union

from flask import Flask, jsonify
from flask_cors import CORS

from app.core.config import API_PREFIX, CORS_ORIGINS, PERMANENT_SESSION_LIFETIME, SECRET_KEY, SESSION_COOKIE_NAME, SESSION_COOKIE_SAMESITE, SESSION_COOKIE_SECURE


def _parse_origins(origins_raw: str) -> Tuple[Union[str, List[str]], bool]:
    raw = (origins_raw or "").strip()
    if not raw or raw == "*":
        return "*", False
    return [origin.strip() for origin in raw.split(",") if origin.strip()], True


def create_app() -> Flask:
    app = Flask(__name__)

    secret_key = (SECRET_KEY or "").strip()
    if not secret_key:
        if os.getenv("FLASK_ENV") == "development":
            secret_key = "dev-secret-key-do-not-use-in-production"
            warnings.warn("Using temporary SECRET_KEY in development only")
        else:
            raise RuntimeError("SECRET_KEY environment variable is required in production")

    app.config.update(
        SECRET_KEY=secret_key,
        SESSION_COOKIE_NAME=SESSION_COOKIE_NAME,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE,
        SESSION_COOKIE_SAMESITE=SESSION_COOKIE_SAMESITE,
        SESSION_COOKIE_PATH="/",
        PERMANENT_SESSION_LIFETIME=PERMANENT_SESSION_LIFETIME,
    )

    origins, supports_credentials = _parse_origins(CORS_ORIGINS)
    CORS(app, resources={r"/*": {"origins": origins}}, supports_credentials=supports_credentials)

    from app.routes import admin, auth, health, opportunities, partners, platform_modules, profiles, readiness_tools, relocation_public, reports, saved_routes, timeline, watchlist

    app.register_blueprint(health.bp)
    app.register_blueprint(relocation_public.bp, url_prefix=f"{API_PREFIX}/relocation")
    app.register_blueprint(platform_modules.bp, url_prefix=f"{API_PREFIX}/platform")
    app.register_blueprint(opportunities.bp, url_prefix=f"{API_PREFIX}/opportunities")
    app.register_blueprint(reports.bp, url_prefix=f"{API_PREFIX}/reports")
    app.register_blueprint(readiness_tools.bp, url_prefix=f"{API_PREFIX}/readiness")
    app.register_blueprint(watchlist.bp, url_prefix=f"{API_PREFIX}/watchlist")
    app.register_blueprint(saved_routes.bp, url_prefix=f"{API_PREFIX}/saved-routes")
    app.register_blueprint(timeline.bp, url_prefix=f"{API_PREFIX}/timeline")
    app.register_blueprint(partners.bp, url_prefix=f"{API_PREFIX}/partners")
    app.register_blueprint(profiles.bp, url_prefix=f"{API_PREFIX}/profiles")
    app.register_blueprint(auth.bp, url_prefix=f"{API_PREFIX}/auth")
    app.register_blueprint(platform_modules.planned_bp, url_prefix=API_PREFIX)
    app.register_blueprint(admin.bp, url_prefix=f"{API_PREFIX}/admin")

    @app.get("/")
    def root():
        return jsonify({"ok": True, "service": "MoveReady API", "api_prefix": API_PREFIX})

    return app