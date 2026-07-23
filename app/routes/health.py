from __future__ import annotations

import os
import platform
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify

from app.core import config

bp = Blueprint("health", __name__)

_PROCESS_STARTED_AT = datetime.now(timezone.utc)
_PROCESS_STARTED_MONOTONIC = time.monotonic()
_RELEASE_LABEL = "moveready-controlled-launch-2026-07-23"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _first_env(*names: str) -> str:
    for name in names:
        value = _env(name)
        if value:
            return value
    return ""


def _commit_sha() -> str:
    return _first_env(
        "RAILWAY_GIT_COMMIT_SHA",
        "GIT_COMMIT_SHA",
        "SOURCE_COMMIT",
        "COMMIT_SHA",
    )


def _deployment_environment() -> str:
    return _first_env("RAILWAY_ENVIRONMENT_NAME", "ENV_MODE", "FLASK_ENV") or "unknown"


def _schedule_summary() -> Dict[str, Any]:
    countries = [
        item.strip()
        for item in str(config.PASSPORT_INDEX_SCHEDULED_COUNTRIES or "Nigeria").split(",")
        if item.strip()
    ]
    return {
        "cadence": "weekly",
        "weekdays": config.PASSPORT_INDEX_SYNC_WEEKDAYS,
        "hour_utc": config.PASSPORT_INDEX_SYNC_HOUR_UTC,
        "minute_utc": config.PASSPORT_INDEX_SYNC_MINUTE_UTC,
        "scheduled_countries": countries,
        "maximum_countries_per_run": config.PASSPORT_INDEX_MAX_COUNTRIES_PER_SYNC,
        "cache_max_days": config.PASSPORT_INDEX_CACHE_MAX_DAYS,
        "execution_model": "scheduled sync plus stale-cache refresh protection",
    }


def _feature_flags() -> Dict[str, Any]:
    return {
        "account_auth": True,
        "account_summary": True,
        "profiles": True,
        "saved_routes": True,
        "reports": True,
        "watchlist": True,
        "in_app_alerts": True,
        "service_requests": True,
        "study_planner": True,
        "journey_planner": True,
        "trip_planner": True,
        "evidence_inventory": True,
        "evidence_packs": True,
        "refusal_repair": True,
        "source_health": True,
        "source_governance_admin": True,
        "commercial_quotes": bool(config.COMMERCIAL_QUOTES_ENABLED),
        "payment_links": bool(config.PAYMENT_LINKS_ENABLED),
        "provider_publication_controls": True,
        "provider_handoffs": True,
        "support_cases": True,
        "visa_power": bool(config.VISA_POWER_ENABLED),
        "passport_index": bool(config.VISA_POWER_ENABLED),
        "passport_provider_cache": True,
        "passport_weekly_sync": True,
        "external_passport_provider_enabled": bool(config.PASSPORT_INDEX_PROVIDER_ENABLED),
        "external_email_alerts": bool(config.OPPORTUNITY_ALERTS_ENABLED),
        "whatsapp_alerts": bool(config.WHATSAPP_ALERTS_ENABLED),
    }


def _expected_endpoints() -> List[str]:
    prefix = config.API_PREFIX
    return [
        f"{prefix}/auth/health",
        f"{prefix}/account/summary",
        f"{prefix}/operations/status",
        f"{prefix}/source-health/summary",
        f"{prefix}/evidence/options",
        f"{prefix}/evidence/documents",
        f"{prefix}/evidence/packs",
        f"{prefix}/evidence/packs/generate",
        f"{prefix}/evidence/refusal-repair",
        f"{prefix}/billing/status",
        f"{prefix}/handoffs",
        f"{prefix}/handoffs/support-cases",
        f"{prefix}/visa-power/provider/status",
        f"{prefix}/visa-power/provider/schedule/status",
        f"{prefix}/visa-power/passport-index/check",
        f"{prefix}/visa-power/check",
        f"{prefix}/admin/operations/status",
        f"{prefix}/admin/source-governance/queue",
        f"{prefix}/admin/review-queue",
    ]


def _route_contract() -> Dict[str, Any]:
    expected = _expected_endpoints()
    registered = {rule.rule for rule in current_app.url_map.iter_rules()}
    missing = [route for route in expected if route not in registered]
    return {
        "ok": not missing,
        "expected_count": len(expected),
        "registered_route_count": len(registered),
        "missing_routes": missing,
    }


def _deployment_payload() -> Dict[str, Any]:
    commit_sha = _commit_sha()
    uptime_seconds = max(0, int(time.monotonic() - _PROCESS_STARTED_MONOTONIC))
    return {
        "release_label": _RELEASE_LABEL,
        "commit_sha": commit_sha or None,
        "commit_short": commit_sha[:12] if commit_sha else None,
        "environment": _deployment_environment(),
        "railway_service": _env("RAILWAY_SERVICE_NAME") or None,
        "railway_environment_id_present": bool(_env("RAILWAY_ENVIRONMENT_ID")),
        "process_started_at": _PROCESS_STARTED_AT.isoformat(),
        "uptime_seconds": uptime_seconds,
        "python_version": platform.python_version(),
    }


def _health_payload() -> Dict[str, Any]:
    return {
        "ok": True,
        "status": "healthy",
        "service": "moveready-api",
        "api_prefix": config.API_PREFIX,
        "deployment": _deployment_payload(),
        "features": _feature_flags(),
        "passport_index_schedule": _schedule_summary(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@bp.get("/health")
def health():
    return jsonify(_health_payload())


@bp.get("/api/health")
def api_health():
    return jsonify(_health_payload())


@bp.get("/api/build-info")
def build_info():
    payload = _health_payload()
    payload["expected_endpoints"] = _expected_endpoints()
    payload["route_contract"] = _route_contract()
    payload["deployment_verification"] = {
        "commit_available": bool(payload["deployment"].get("commit_sha")),
        "instruction": "Compare deployment.commit_sha with the latest main-branch commit before treating production as current.",
        "older_deploy_warning": "If an expected endpoint, route contract, or current release label is missing, Railway is serving an older revision or the wrong service.",
    }
    payload["safety_contract"] = {
        "evidence_storage": "metadata only; raw files and full document numbers are not accepted",
        "source_health": "freshness and confidence reporting does not guarantee that every rule is unchanged",
        "public_provider_listing": "fail closed until schema and publication checks pass",
        "provider_handoff": "exact-field user consent and delivery evidence required",
        "payment_links": "disabled until payment activation controls pass" if not config.PAYMENT_LINKS_ENABLED else "enabled by production configuration",
        "email_login": "controlled by provider readiness and abuse limits",
    }
    return jsonify(payload)
