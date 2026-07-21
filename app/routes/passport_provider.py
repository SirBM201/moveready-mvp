from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from app.routes.visa_power import (
    PASSPORT_INDEX_RECORDS,
    _clean_visa_codes,
    _combined_score,
    _destination_count,
    _matched_rules,
    _passport_options,
    _passport_record,
    _visa_benefit_score,
)
from app.services.passport_index_provider import (
    ACCESS_LABELS,
    clean_text,
    country_key,
    fetch_provider_payload,
    log_sync_run,
    next_sync_due_iso,
    normalize_provider_payload,
    provider_status_payload,
    read_cached_destination_rows,
    read_cached_passport,
    write_cache,
)
from app.utils.admin_auth import require_admin_access

bp = Blueprint("passport_provider", __name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fallback_destination_rows(passport_index: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    groups = [
        ("visa_free", passport_index.get("visa_free_examples")),
        ("visa_on_arrival", passport_index.get("visa_on_arrival_examples")),
        ("evisa", passport_index.get("evisa_examples")),
        ("visa_required", passport_index.get("visa_required_examples")),
    ]
    for bucket, items in groups:
        for item in items or []:
            row = dict(item or {})
            row["access_bucket"] = row.get("access_bucket") or bucket
            row["access_label"] = ACCESS_LABELS.get(bucket, bucket)
            row["source_status"] = row.get("source_status") or passport_index.get("confidence") or "starter_pending_official_review"
            row["confidence"] = row.get("confidence") or passport_index.get("confidence") or "starter_pending_official_review"
            rows.append(row)
    return rows


def _with_count_fallback(passport_index: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    index = dict(passport_index)
    for bucket, count_key, estimate_key in [
        ("visa_free", "visa_free_count", "visa_free_count_estimate"),
        ("visa_on_arrival", "visa_on_arrival_count", "visa_on_arrival_count_estimate"),
        ("evisa", "evisa_count", "evisa_count_estimate"),
        ("visa_required", "visa_required_count", "visa_required_count_estimate"),
    ]:
        count = sum(1 for row in rows if row.get("access_bucket") == bucket)
        if index.get(count_key) is None and count:
            index[count_key] = count
        if index.get(estimate_key) in {None, ""} and count:
            index[estimate_key] = count
    return index


def _cache_status_from_row(cache_row: Dict[str, Any] | None) -> Dict[str, Any]:
    if not cache_row:
        return {
            "data_source": "starter_fallback",
            "source_provider": "MoveReady starter records",
            "last_synced_at": None,
            "next_sync_due_at": next_sync_due_iso(),
            "sync_frequency": "twice weekly after provider setup",
            "source_status": "starter_pending_provider_connection",
        }
    return {
        "data_source": "provider_cache",
        "source_provider": cache_row.get("source_provider") or "Configured passport provider",
        "last_synced_at": cache_row.get("last_synced_at"),
        "next_sync_due_at": cache_row.get("next_sync_due_at") or next_sync_due_iso(),
        "sync_frequency": "twice weekly",
        "source_status": cache_row.get("source_status") or cache_row.get("confidence") or "provider_cache_pending_admin_review",
    }


def _build_public_passport_response(passport_country: str) -> Dict[str, Any]:
    fallback = _passport_record(passport_country)
    fallback_rows = _fallback_destination_rows(fallback)

    try:
        cache_row = read_cached_passport(passport_country)
        cached_rows = read_cached_destination_rows(passport_country) if cache_row else []
    except Exception as exc:
        fallback_index = _with_count_fallback(fallback, fallback_rows)
        fallback_index.update(
            {
                "destination_access_rows": fallback_rows,
                "source_provider": "MoveReady starter records",
                "data_source": "starter_fallback_database_unavailable",
                "last_synced_at": None,
                "sync_frequency": "twice weekly after provider setup",
                "next_sync_due_at": next_sync_due_iso(),
            }
        )
        return {
            "ok": True,
            "passport_country": fallback_index.get("country"),
            "passport_index": fallback_index,
            "passport_opportunity_score": fallback_index.get("passport_opportunity_score"),
            "source_status": fallback_index.get("confidence"),
            "cache_status": _cache_status_from_row(None),
            "provider_status": provider_status_payload(),
            "warning": f"Provider cache table is not ready yet: {exc}",
            "safety_note": "Passport access can change quickly. Confirm official destination rules, airline checks, passport validity, funds, return ticket, and personal history before travel.",
        }

    if cache_row:
        cached_index = dict(cache_row.get("passport_index_payload") or {})
        cached_index.update(
            {
                "country": cached_index.get("country") or cache_row.get("passport_country") or fallback.get("country"),
                "country_key": cached_index.get("country_key") or cache_row.get("country_key") or country_key(passport_country),
                "passport_rank": cached_index.get("passport_rank") or cache_row.get("passport_rank"),
                "passport_opportunity_score": cached_index.get("passport_opportunity_score") or cache_row.get("passport_opportunity_score") or fallback.get("passport_opportunity_score"),
                "passport_strength_band": cached_index.get("passport_strength_band") or cache_row.get("passport_strength_band") or fallback.get("passport_strength_band"),
                "visa_free_count": cached_index.get("visa_free_count") or cache_row.get("visa_free_count"),
                "visa_on_arrival_count": cached_index.get("visa_on_arrival_count") or cache_row.get("visa_on_arrival_count"),
                "evisa_count": cached_index.get("evisa_count") or cache_row.get("evisa_count"),
                "visa_required_count": cached_index.get("visa_required_count") or cache_row.get("visa_required_count"),
                "source_provider": cache_row.get("source_provider"),
                "last_synced_at": cache_row.get("last_synced_at"),
                "next_sync_due_at": cache_row.get("next_sync_due_at") or next_sync_due_iso(),
                "sync_frequency": "twice weekly",
                "data_source": "provider_cache",
            }
        )
        rows = cached_rows or _fallback_destination_rows(cached_index) or fallback_rows
        cached_index["destination_access_rows"] = rows
        cached_index = _with_count_fallback(cached_index, rows)
        return {
            "ok": True,
            "passport_country": cached_index.get("country"),
            "passport_index": cached_index,
            "passport_opportunity_score": cached_index.get("passport_opportunity_score"),
            "source_status": cached_index.get("confidence") or cache_row.get("confidence"),
            "cache_status": _cache_status_from_row(cache_row),
            "provider_status": provider_status_payload(),
            "safety_note": "Passport access can change quickly. Confirm official destination rules, airline checks, passport validity, funds, return ticket, and personal history before travel.",
        }

    fallback_index = _with_count_fallback(fallback, fallback_rows)
    fallback_index.update(
        {
            "destination_access_rows": fallback_rows,
            "source_provider": "MoveReady starter records",
            "data_source": "starter_fallback",
            "last_synced_at": None,
            "sync_frequency": "twice weekly after provider setup",
            "next_sync_due_at": next_sync_due_iso(),
        }
    )
    return {
        "ok": True,
        "passport_country": fallback_index.get("country"),
        "passport_index": fallback_index,
        "passport_opportunity_score": fallback_index.get("passport_opportunity_score"),
        "source_status": fallback_index.get("confidence"),
        "cache_status": _cache_status_from_row(None),
        "provider_status": provider_status_payload(),
        "safety_note": "Passport access can change quickly. Confirm official destination rules, airline checks, passport validity, funds, return ticket, and personal history before travel.",
    }


@bp.get("/provider/status")
def provider_status():
    payload = provider_status_payload()
    payload["ok"] = True
    return jsonify(payload)


@bp.post("/provider/sync")
@require_admin_access
def sync_provider_cache():
    payload = request.get_json(silent=True) or {}
    requested_country = clean_text(payload.get("passport_country"), 160)
    countries = [requested_country] if requested_country else [row["country"] for row in PASSPORT_INDEX_RECORDS]

    status = provider_status_payload()
    if not status["provider_enabled"] or not status["provider_configured"]:
        details = {
            "message": "Provider sync skipped because PASSPORT_INDEX_PROVIDER_ENABLED, PASSPORT_INDEX_PROVIDER_URL, or PASSPORT_INDEX_PROVIDER_KEY is not configured.",
            "provider_status": status,
            "countries_requested": countries,
        }
        log_sync_run("skipped_provider_not_configured", details)
        return jsonify({"ok": True, "status": "skipped_provider_not_configured", **details})

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for country in countries:
        try:
            provider_payload = fetch_provider_payload(country)
            normalized = normalize_provider_payload(country, provider_payload)
            written = write_cache(country, normalized, provider_payload)
            results.append({"country": country, **written})
        except Exception as exc:
            errors.append({"country": country, "error": str(exc)[:500]})

    run_status = "completed_with_errors" if errors else "completed"
    details = {"results": results, "errors": errors, "synced_at": _now_iso(), "next_sync_due_at": next_sync_due_iso()}
    log_sync_run(run_status, details)
    http_status = 207 if errors and results else (500 if errors and not results else 200)
    return jsonify({"ok": not errors or bool(results), "status": run_status, **details}), http_status


@bp.get("/passport-index/options")
def passport_index_options_live():
    return jsonify(
        {
            "ok": True,
            "feature": "passport_index_provider_ready_cache",
            "passport_country_options": _passport_options(),
            "provider_status": provider_status_payload(),
            "source_status": "provider_cache_ready_with_starter_fallback",
            "safety_note": "Do not treat passport index records as permission to travel. Confirm the current official destination rule before booking or travelling.",
        }
    )


@bp.post("/passport-index/check")
def passport_index_check_live():
    payload = request.get_json(silent=True) or {}
    passport_country = clean_text(payload.get("passport_country"), 120)
    return jsonify(_build_public_passport_response(passport_country))


@bp.post("/check")
def visa_power_check_live():
    payload = request.get_json(silent=True) or {}
    passport_country = clean_text(payload.get("passport_country"), 120)
    held_visas = _clean_visa_codes(payload.get("held_visas"))
    multiple_entry_confirmed = bool(payload.get("multiple_entry_confirmed"))
    visa_used_before_confirmed = bool(payload.get("visa_used_before_confirmed"))

    passport_response = _build_public_passport_response(passport_country)
    passport_record = passport_response.get("passport_index") or _passport_record(passport_country)
    matched_rules = _matched_rules(held_visas, multiple_entry_confirmed, visa_used_before_confirmed)
    visa_score = _visa_benefit_score(matched_rules, held_visas)
    passport_score = int(passport_record.get("passport_opportunity_score") or 0)
    combined_score = _combined_score(passport_record, matched_rules, held_visas)

    return jsonify(
        {
            "ok": True,
            "feature": "visa_power_and_travel_benefits_provider_ready",
            "passport_country": passport_record.get("country"),
            "held_visas": held_visas,
            "multiple_entry_confirmed": multiple_entry_confirmed,
            "visa_used_before_confirmed": visa_used_before_confirmed,
            "passport_only_score": passport_score,
            "visa_opportunity_score": visa_score,
            "combined_opportunity_score": combined_score,
            "matched_destination_count": _destination_count(matched_rules),
            "passport_index": passport_record,
            "cache_status": passport_response.get("cache_status"),
            "provider_status": passport_response.get("provider_status"),
            "matches": matched_rules,
            "next_actions": [
                "Open the official destination source before booking or paying anyone.",
                "Check passport validity, blank pages, funds, return ticket, and accommodation evidence.",
                "Confirm visa conditions such as multiple-entry, previous use, remaining validity, and travel purpose.",
                "Save this route or create an alert if you want MoveReady to remind you to re-check later.",
            ],
            "safety_note": "This result is not permission to travel. Entry depends on current official rules, airline checks, border officers, document validity, travel purpose, funds, ticket, and personal history.",
        }
    )
