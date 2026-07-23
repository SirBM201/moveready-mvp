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

    from app.services.account_session_context import attach_verified_session_email_to_json

    app.before_request(attach_verified_session_email_to_json)

    from app.services.passport_index_provider_travelbuddy_patch import apply_patch

    apply_patch()

    from app.routes import account, account_auth, admin, admin_review_evidence_extension, admin_review_queue, billing, billing_admin, education_planner, evidence_admin, evidence_workflow, health, journey_planner, opportunities, operations, partners, passport_destination_detail, passport_provider, passport_provider_schedule, platform_modules, profiles, readiness_tools, relocation_public, reports, saved_route_reports, saved_routes, service_handoff_safety, service_handoffs, settlement_execution, source_governance, timeline, travel_planner, visa_power, watchlist
    from app.routes.visa_power_safety import visa_power_check_safe
    from app.services.journey_module_patch import apply_journey_module_patch
    from app.services.travel_provider_publication import apply_travel_provider_publication_patch

    apply_journey_module_patch()
    apply_travel_provider_publication_patch()

    app.register_blueprint(health.bp)
    app.register_blueprint(relocation_public.bp, url_prefix=f"{API_PREFIX}/relocation")
    app.register_blueprint(platform_modules.bp, url_prefix=f"{API_PREFIX}/platform")
    app.register_blueprint(opportunities.bp, url_prefix=f"{API_PREFIX}/opportunities")
    app.register_blueprint(reports.bp, url_prefix=f"{API_PREFIX}/reports")
    app.register_blueprint(readiness_tools.bp, url_prefix=f"{API_PREFIX}/readiness")
    app.register_blueprint(evidence_workflow.bp, url_prefix=f"{API_PREFIX}/evidence")
    app.register_blueprint(journey_planner.bp, url_prefix=f"{API_PREFIX}/journey")
    app.register_blueprint(education_planner.bp, url_prefix=f"{API_PREFIX}/education")
    app.register_blueprint(travel_planner.bp, url_prefix=f"{API_PREFIX}/travel")
    app.register_blueprint(billing.bp, url_prefix=f"{API_PREFIX}/billing")
    app.register_blueprint(operations.public_bp, url_prefix=f"{API_PREFIX}/operations")
    app.register_blueprint(source_governance.public_bp, url_prefix=f"{API_PREFIX}/source-health")
    app.register_blueprint(watchlist.bp, url_prefix=f"{API_PREFIX}/watchlist")
    app.register_blueprint(saved_routes.bp, url_prefix=f"{API_PREFIX}/saved-routes")
    app.register_blueprint(saved_route_reports.bp, url_prefix=f"{API_PREFIX}/saved-route-reports")
    app.register_blueprint(timeline.bp, url_prefix=f"{API_PREFIX}/timeline")
    app.register_blueprint(partners.bp, url_prefix=f"{API_PREFIX}/partners")
    app.register_blueprint(profiles.bp, url_prefix=f"{API_PREFIX}/profiles")
    app.register_blueprint(account_auth.bp, url_prefix=f"{API_PREFIX}/auth")
    app.register_blueprint(account.bp, url_prefix=f"{API_PREFIX}/account")

    # `/api/handoffs` is the established frontend contract. The more explicit
    # `/api/service-handoffs` path is retained as a compatibility alias.
    app.register_blueprint(service_handoffs.user_bp, url_prefix=f"{API_PREFIX}/handoffs")
    app.register_blueprint(
        service_handoffs.user_bp,
        url_prefix=f"{API_PREFIX}/service-handoffs",
        name="service_handoffs_alias",
    )

    app.register_blueprint(passport_provider.bp, url_prefix=f"{API_PREFIX}/visa-power")
    app.register_blueprint(passport_provider_schedule.bp, url_prefix=f"{API_PREFIX}/visa-power")
    app.register_blueprint(passport_destination_detail.bp, url_prefix=f"{API_PREFIX}/visa-power")
    app.register_blueprint(visa_power.bp, url_prefix=f"{API_PREFIX}/visa-power")
    app.register_blueprint(platform_modules.planned_bp, url_prefix=API_PREFIX)
    app.register_blueprint(admin.bp, url_prefix=f"{API_PREFIX}/admin")
    app.register_blueprint(admin_review_queue.bp, url_prefix=f"{API_PREFIX}/admin")
    app.register_blueprint(billing_admin.bp, url_prefix=f"{API_PREFIX}/admin")
    app.register_blueprint(evidence_admin.bp, url_prefix=f"{API_PREFIX}/admin")
    app.register_blueprint(service_handoffs.admin_bp, url_prefix=f"{API_PREFIX}/admin")
    app.register_blueprint(source_governance.admin_bp, url_prefix=f"{API_PREFIX}/admin")
    app.register_blueprint(operations.admin_bp, url_prefix=f"{API_PREFIX}/admin")

    # Keep stable URLs while replacing legacy handlers with stricter safety gates
    # and runtime extensions.
    app.view_functions["passport_provider.visa_power_check_live"] = visa_power_check_safe
    app.view_functions["service_handoffs_admin.update_handoff_status"] = service_handoff_safety.safe_update_handoff_status
    app.view_functions["service_handoffs_admin.update_support_case"] = service_handoff_safety.safe_update_support_case
    app.view_functions["admin_review_queue.review_queue"] = admin_review_evidence_extension.review_queue_with_evidence
    app.view_functions["journey_planner.settlement_plan"] = settlement_execution.settlement_plan_with_timeline

    @app.get("/")
    def root():
        return jsonify({"ok": True, "service": "MoveReady API", "api_prefix": API_PREFIX})

    return app
