from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.passport_destination_detail import (
    detail_provider_status,
    get_destination_detail,
)
from app.services.passport_index_provider import clean_text
from app.services.passport_official_sources import enrich_destination_result
from app.utils.admin_auth import require_admin_access


bp = Blueprint("passport_destination_detail", __name__)


def _safe_error(exc: Exception) -> str:
    return str(exc).replace("\n", " ")[:700]


@bp.get("/passport-index/destination/status")
def destination_detail_status():
    return jsonify({"ok": True, **detail_provider_status()})


@bp.post("/passport-index/destination/check")
def destination_detail_check():
    payload = request.get_json(silent=True) or {}
    passport_country = clean_text(payload.get("passport_country"), 160)
    destination = clean_text(payload.get("destination"), 180)

    if not passport_country or not destination:
        return jsonify(
            {
                "ok": False,
                "status": "invalid_request",
                "message": "passport_country and destination are required.",
            }
        ), 400

    try:
        result = get_destination_detail(passport_country, destination)
        return jsonify(enrich_destination_result(result))
    except ValueError as exc:
        return jsonify({"ok": False, "status": "invalid_request", "error": _safe_error(exc)}), 400
    except LookupError as exc:
        return jsonify(
            {
                "ok": False,
                "status": "destination_not_found",
                "error": _safe_error(exc),
                "message": "Sync the passport index first, then choose a destination from its current list.",
            }
        ), 404
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "status": "destination_detail_failed",
                "error": _safe_error(exc),
                "provider_status": detail_provider_status(),
            }
        ), 502


@bp.post("/provider/destination/test")
@require_admin_access
def destination_detail_admin_test():
    payload = request.get_json(silent=True) or {}
    passport_country = clean_text(payload.get("passport_country") or "Nigeria", 160)
    destination = clean_text(payload.get("destination") or "Canada", 180)

    try:
        result = enrich_destination_result(
            get_destination_detail(
                passport_country,
                destination,
                force_refresh=bool(payload.get("force_refresh", True)),
            )
        )
        return jsonify({**result, "ok": True, "test_status": "destination_detail_test_success"})
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "status": "destination_detail_test_failed",
                "passport_country": passport_country,
                "destination": destination,
                "error": _safe_error(exc),
                "provider_status": detail_provider_status(),
            }
        ), 502
