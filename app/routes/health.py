from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify

from app.core.config import API_PREFIX, VISA_POWER_ENABLED

bp = Blueprint("health", __name__)


BUILD_FEATURES = {
    "account_summary": True,
    "profiles": True,
    "saved_routes": True,
    "reports": True,
    "watchlist": True,
    "service_requests": True,
    "visa_power": VISA_POWER_ENABLED,
    "passport_index": VISA_POWER_ENABLED,
}


def _health_payload() -> dict:
    return {
        "ok": True,
        "status": "healthy",
        "service": "moveready-api",
        "api_prefix": API_PREFIX,
        "build_label": "moveready-launch-core-2026-07-20",
        "features": BUILD_FEATURES,
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
    payload["diagnostic_note"] = "If this endpoint is missing on Railway, Railway is serving an older backend deploy or the wrong service."
    payload["expected_visa_power_endpoints"] = [
        f"{API_PREFIX}/visa-power/options",
        f"{API_PREFIX}/visa-power/passport-index/options",
        f"{API_PREFIX}/visa-power/passport-index/check",
        f"{API_PREFIX}/visa-power/check",
    ]
    return jsonify(payload)
