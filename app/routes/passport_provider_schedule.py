from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from app.core.config import (
    PASSPORT_INDEX_MAX_COUNTRIES_PER_SYNC,
    PASSPORT_INDEX_SCHEDULED_COUNTRIES,
    PASSPORT_INDEX_SYNC_WEEKDAYS,
)
from app.services.passport_index_provider import (
    clean_text,
    fetch_provider_payload,
    log_sync_run,
    next_sync_due_iso,
    normalize_provider_payload,
    provider_status_payload,
    write_cache,
)
from app.utils.admin_auth import require_admin_access


bp = Blueprint("passport_provider_schedule", __name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_error(exc: Exception) -> str:
    return str(exc).replace("\n", " ")[:700]


def _configured_countries() -> List[str]:
    output: List[str] = []
    for raw in (PASSPORT_INDEX_SCHEDULED_COUNTRIES or "Nigeria").split(","):
        country = clean_text(raw, 160)
        if country and country.lower() not in {item.lower() for item in output}:
            output.append(country)
    if not output:
        output = ["Nigeria"]
    return output[:PASSPORT_INDEX_MAX_COUNTRIES_PER_SYNC]


def schedule_status_payload() -> Dict[str, Any]:
    return {
        "scheduled_countries": _configured_countries(),
        "max_countries_per_sync": PASSPORT_INDEX_MAX_COUNTRIES_PER_SYNC,
        "sync_weekdays": PASSPORT_INDEX_SYNC_WEEKDAYS,
        "next_sync_due_at": next_sync_due_iso(),
        "cost_guardrail": "The scheduled endpoint processes no more than the configured maximum number of passport countries per run.",
        "provider_status": provider_status_payload(),
    }


@bp.get("/provider/schedule/status")
def provider_schedule_status():
    return jsonify({"ok": True, **schedule_status_payload()})


@bp.post("/provider/scheduled-sync")
@require_admin_access
def scheduled_provider_sync():
    payload = request.get_json(silent=True) or {}
    requested_country = clean_text(payload.get("passport_country"), 160)
    countries = [requested_country] if requested_country else _configured_countries()
    countries = countries[:PASSPORT_INDEX_MAX_COUNTRIES_PER_SYNC]

    status = provider_status_payload()
    if not status.get("provider_enabled") or not status.get("provider_configured"):
        details = {
            "message": "Scheduled provider sync skipped because the passport provider is not fully configured.",
            "countries_requested": countries,
            "provider_status": status,
        }
        log_sync_run("scheduled_sync_skipped_provider_not_configured", details)
        return jsonify({"ok": False, "status": "scheduled_sync_skipped_provider_not_configured", **details}), 503

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for country in countries:
        try:
            provider_payload = fetch_provider_payload(country)
            normalized = normalize_provider_payload(country, provider_payload)
            normalized_row_count = len(normalized.get("destination_access_rows") or [])
            if normalized_row_count <= 0:
                raise RuntimeError("scheduled_sync_zero_normalized_rows")
            written = write_cache(country, normalized, provider_payload)
            results.append(
                {
                    "country": country,
                    "normalized_row_count": normalized_row_count,
                    **written,
                }
            )
        except Exception as exc:
            errors.append({"country": country, "error": _safe_error(exc)})

    run_status = "scheduled_sync_completed" if results and not errors else "scheduled_sync_failed"
    details = {
        "countries_requested": countries,
        "results": results,
        "errors": errors,
        "synced_at": _now_iso(),
        "next_sync_due_at": next_sync_due_iso(),
        "max_countries_per_sync": PASSPORT_INDEX_MAX_COUNTRIES_PER_SYNC,
    }
    log_sync_run(run_status, details)

    if errors or len(results) != len(countries):
        return jsonify({"ok": False, "status": run_status, **details}), 502
    return jsonify({"ok": True, "status": run_status, **details})
