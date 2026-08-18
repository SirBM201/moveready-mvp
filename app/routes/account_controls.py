from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.routes import account_auth
from app.services.smart_alerts import (
    SmartAlertPreferenceError,
    normalize_preferences,
    preferences_from_payload,
)
from app.services.supabase_client import get_supabase


bp = Blueprint("account_controls", __name__)

PREFERENCE_FIELDS = {
    "preferred_language",
    "preferred_currency",
    "timezone",
    "date_format",
    "reminder_lead_days",
    "in_app_notifications_enabled",
    "email_notifications_enabled",
    "whatsapp_notifications_enabled",
    "marketing_messages_enabled",
    "source_change_alerts_enabled",
    "application_deadline_alerts_enabled",
    "document_expiry_alerts_enabled",
    "opportunity_alerts_enabled",
    "reduced_motion",
    "high_contrast",
    "simple_language",
    "larger_text",
    "onboarding_status",
    "onboarding_step",
}

BOOLEAN_FIELDS = {
    "in_app_notifications_enabled",
    "email_notifications_enabled",
    "whatsapp_notifications_enabled",
    "marketing_messages_enabled",
    "source_change_alerts_enabled",
    "application_deadline_alerts_enabled",
    "document_expiry_alerts_enabled",
    "opportunity_alerts_enabled",
    "reduced_motion",
    "high_contrast",
    "simple_language",
    "larger_text",
}

DATE_FORMATS = {"day_month_year", "month_day_year", "year_month_day"}
ONBOARDING_STATUSES = {"not_started", "in_progress", "completed", "skipped"}
ONBOARDING_STEPS = {"profile", "route", "evidence", "application", "alerts", "completed"}
PRIVACY_REQUEST_TYPES = {
    "data_export",
    "correction",
    "restriction",
    "account_deletion",
    "consent_withdrawal",
    "other",
}
DELETION_CONFIRMATION = "DELETE MY MOVEREADY ACCOUNT"

DEFAULT_PREFERENCES: Dict[str, Any] = {
    "preferred_language": "en",
    "preferred_currency": "USD",
    "timezone": "UTC",
    "date_format": "day_month_year",
    "reminder_lead_days": 7,
    "in_app_notifications_enabled": True,
    "email_notifications_enabled": False,
    "whatsapp_notifications_enabled": False,
    "marketing_messages_enabled": False,
    "source_change_alerts_enabled": True,
    "application_deadline_alerts_enabled": True,
    "document_expiry_alerts_enabled": True,
    "opportunity_alerts_enabled": False,
    "reduced_motion": False,
    "high_contrast": False,
    "simple_language": False,
    "larger_text": False,
    "onboarding_status": "not_started",
    "onboarding_step": "profile",
}

ACTIVITY_SOURCES = [
    ("profile", "relocation_user_profiles", "Profile updated", "/dashboard", "updated_at"),
    ("saved_route", "relocation_saved_routes", "Route saved", "/saved-routes", "created_at"),
    ("watchlist", "relocation_watchlist_subscriptions", "Alert subscription updated", "/watchlist", "updated_at"),
    ("timeline", "relocation_timeline_events", "Timeline task updated", "/timeline", "updated_at"),
    ("evidence_document", "relocation_user_document_inventory", "Document metadata updated", "/evidence-pack", "updated_at"),
    ("evidence_pack", "relocation_evidence_packs", "Evidence pack updated", "/evidence-pack", "updated_at"),
    ("application_case", "relocation_application_cases", "Application case updated", "/applications", "updated_at"),
    ("application_alert", "relocation_application_case_alerts", "Application alert generated", "/application-alerts", "created_at"),
    ("report", "relocation_generated_reports", "Readiness report generated", "/my-reports", "created_at"),
    ("quote", "relocation_commercial_quotes", "Commercial quote updated", "/billing", "updated_at"),
    ("handoff", "relocation_service_handoffs", "Provider handoff updated", "/support-center", "updated_at"),
    ("support_case", "relocation_support_cases", "Support case updated", "/support-center", "updated_at"),
    ("privacy_request", "relocation_privacy_requests", "Privacy request updated", "/settings#privacy", "updated_at"),
]

EXPORT_TABLES = [
    "relocation_user_profiles",
    "relocation_saved_routes",
    "relocation_watchlist_subscriptions",
    "relocation_timeline_events",
    "relocation_user_document_inventory",
    "relocation_evidence_packs",
    "relocation_application_cases",
    "relocation_application_case_alerts",
    "relocation_generated_reports",
    "relocation_commercial_quotes",
    "relocation_service_handoffs",
    "relocation_support_cases",
    "relocation_privacy_requests",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:limit] if cleaned else None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _auth_session() -> Tuple[Optional[Dict[str, Any]], Optional[Any]]:
    token = account_auth._auth._extract_session_token()
    if not token:
        return None, (jsonify({"ok": False, "error": "session_token_required"}), 401)
    session, error = account_auth._auth._load_active_session(token)
    if not session:
        return None, (jsonify({"ok": False, "error": error or "invalid_session"}), 401)
    return session, None


def _email(session: Dict[str, Any]) -> str:
    return str(session.get("email") or "").strip().lower()


def _public_preferences(row: Optional[Dict[str, Any]], email: str) -> Dict[str, Any]:
    merged = {**DEFAULT_PREFERENCES, **(row or {})}
    metadata = merged.get("metadata") if isinstance(merged.get("metadata"), dict) else {}
    return {
        "email": email,
        **{field: merged.get(field) for field in PREFERENCE_FIELDS},
        "smart_alert_preferences": normalize_preferences(metadata.get("smart_alerts")),
        "created_at": merged.get("created_at"),
        "updated_at": merged.get("updated_at"),
        "delivery_status": {
            "in_app": "available" if merged.get("in_app_notifications_enabled") else "disabled_by_user",
            "email": "preference_recorded_provider_activation_required" if merged.get("email_notifications_enabled") else "disabled_by_user",
            "whatsapp": "preference_recorded_provider_activation_required" if merged.get("whatsapp_notifications_enabled") else "disabled_by_user",
            "marketing": "consent_recorded_no_delivery_without_provider_controls" if merged.get("marketing_messages_enabled") else "disabled_by_user",
        },
    }


def _load_preferences(email: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_account_preferences")
        .select("*")
        .eq("email", email)
        .limit(1)
        .execute()
    )
    return (response.data or [None])[0]


def _preference_payload(payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    row: Dict[str, Any] = {}
    for field in PREFERENCE_FIELDS:
        if field not in payload:
            continue
        value = payload.get(field)
        if field in BOOLEAN_FIELDS:
            row[field] = _bool(value)
        elif field == "reminder_lead_days":
            try:
                days = int(value)
            except Exception:
                return None, "reminder_lead_days_must_be_an_integer"
            if days < 0 or days > 90:
                return None, "reminder_lead_days_out_of_range"
            row[field] = days
        else:
            row[field] = _text(value, 120)

    if "date_format" in row and row["date_format"] not in DATE_FORMATS:
        return None, "invalid_date_format"
    if "onboarding_status" in row and row["onboarding_status"] not in ONBOARDING_STATUSES:
        return None, "invalid_onboarding_status"
    if "onboarding_step" in row and row["onboarding_step"] not in ONBOARDING_STEPS:
        return None, "invalid_onboarding_step"
    if row.get("onboarding_status") == "completed":
        row["onboarding_step"] = "completed"
    return row, None


def _row_title(kind: str, row: Dict[str, Any], fallback: str) -> str:
    candidates = {
        "profile": [row.get("full_name"), row.get("goal")],
        "saved_route": [row.get("route_name"), row.get("target_country"), row.get("country_name")],
        "watchlist": [row.get("title"), row.get("route_name"), row.get("target_country")],
        "timeline": [row.get("event_title")],
        "evidence_document": [row.get("document_label"), row.get("document_type")],
        "evidence_pack": [row.get("pack_ref"), row.get("route_name")],
        "application_case": [row.get("case_title"), row.get("case_ref")],
        "application_alert": [row.get("title"), row.get("alert_type")],
        "report": [row.get("report_title"), row.get("report_ref")],
        "quote": [row.get("quote_ref"), row.get("service_name")],
        "handoff": [row.get("handoff_ref"), row.get("service_type")],
        "support_case": [row.get("case_ref"), row.get("case_type")],
        "privacy_request": [row.get("request_ref"), row.get("request_type")],
    }.get(kind, [])
    for candidate in candidates:
        value = _text(candidate, 180)
        if value:
            return value
    return fallback


def _safe_rows_for_email(table: str, email: str, limit: int = 50, order_by: str = "created_at") -> Dict[str, Any]:
    try:
        response = (
            get_supabase()
            .table(table)
            .select("*")
            .eq("email", email)
            .order(order_by, desc=True)
            .limit(limit)
            .execute()
        )
        return {"ok": True, "rows": response.data or [], "error": None}
    except Exception as exc:
        return {"ok": False, "rows": [], "error": str(exc)[:800]}


def _public_session(row: Dict[str, Any], current_session_id: Any) -> Dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    user_agent = _text(metadata.get("user_agent"), 300) or "Unknown device"
    return {
        "id": row.get("id"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
        "last_seen_at": row.get("last_seen_at"),
        "expires_at": row.get("expires_at"),
        "device": user_agent,
        "current": str(row.get("id") or "") == str(current_session_id or ""),
    }


@bp.get("/preferences")
def get_preferences():
    session, error_response = _auth_session()
    if error_response:
        return error_response
    email = _email(session or {})
    try:
        row = _load_preferences(email)
        return jsonify({"ok": True, "preferences": _public_preferences(row, email)})
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": "account_preferences_unavailable",
            "details": str(exc)[:800],
            "hint": "Run supabase/migrations/030_account_preferences_privacy_activity.sql.",
        }), 503


@bp.put("/preferences")
def update_preferences():
    session, error_response = _auth_session()
    if error_response:
        return error_response
    email = _email(session or {})
    payload = request.get_json(silent=True) or {}
    row, error = _preference_payload(payload)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    if "smart_alert_preferences" in payload:
        try:
            smart_preferences = preferences_from_payload(payload.get("smart_alert_preferences"))
        except SmartAlertPreferenceError as exc:
            return jsonify({"ok": False, "error": exc.code}), 400
        try:
            existing = _load_preferences(email) or {}
        except Exception:
            return jsonify({"ok": False, "error": "account_preferences_unavailable"}), 503
        metadata = existing.get("metadata") if isinstance(existing.get("metadata"), dict) else {}
        row["metadata"] = {**metadata, "smart_alerts": smart_preferences}
    if not row:
        return jsonify({"ok": False, "error": "at_least_one_preference_required"}), 400

    row["email"] = email
    row["consent_version"] = "moveready-account-preferences-v2"
    row["consent_recorded_at"] = _now_iso()
    try:
        response = (
            get_supabase()
            .table("relocation_account_preferences")
            .upsert(row, on_conflict="email")
            .execute()
        )
        stored = (response.data or [None])[0] or _load_preferences(email)
        return jsonify({
            "ok": True,
            "preferences": _public_preferences(stored, email),
            "safety_note": "External email, WhatsApp, marketing, or push delivery remains disabled until its provider, opt-in, templates, audit, unsubscribe, and production tests are approved.",
        })
    except Exception:
        return jsonify({"ok": False, "error": "account_preferences_save_failed"}), 503


@bp.get("/sessions")
def list_sessions():
    session, error_response = _auth_session()
    if error_response:
        return error_response
    email = _email(session or {})
    try:
        response = (
            get_supabase()
            .table("relocation_user_sessions")
            .select("id,email,status,created_at,last_seen_at,expires_at,metadata")
            .eq("email", email)
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(25)
            .execute()
        )
        rows = [_public_session(row, (session or {}).get("id")) for row in (response.data or [])]
        return jsonify({"ok": True, "sessions": rows, "count": len(rows)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "session_list_unavailable", "details": str(exc)[:800]}), 503


@bp.post("/sessions/revoke")
def revoke_session():
    session, error_response = _auth_session()
    if error_response:
        return error_response
    email = _email(session or {})
    session_id = _text((request.get_json(silent=True) or {}).get("session_id"), 80)
    if not session_id:
        return jsonify({"ok": False, "error": "session_id_required"}), 400
    try:
        response = (
            get_supabase()
            .table("relocation_user_sessions")
            .update({"status": "revoked"})
            .eq("id", session_id)
            .eq("email", email)
            .eq("status", "active")
            .execute()
        )
        revoked = bool(response.data)
        return jsonify({
            "ok": True,
            "revoked": revoked,
            "current_session_revoked": revoked and str(session_id) == str((session or {}).get("id") or ""),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": "session_revoke_failed", "details": str(exc)[:800]}), 503


@bp.post("/sessions/revoke-others")
def revoke_other_sessions():
    session, error_response = _auth_session()
    if error_response:
        return error_response
    email = _email(session or {})
    current_id = str((session or {}).get("id") or "")
    try:
        response = (
            get_supabase()
            .table("relocation_user_sessions")
            .select("id")
            .eq("email", email)
            .eq("status", "active")
            .limit(50)
            .execute()
        )
        revoked = 0
        for row in response.data or []:
            session_id = str(row.get("id") or "")
            if not session_id or session_id == current_id:
                continue
            update = (
                get_supabase()
                .table("relocation_user_sessions")
                .update({"status": "revoked"})
                .eq("id", session_id)
                .eq("email", email)
                .execute()
            )
            revoked += len(update.data or [])
        return jsonify({"ok": True, "revoked_count": revoked})
    except Exception as exc:
        return jsonify({"ok": False, "error": "other_sessions_revoke_failed", "details": str(exc)[:800]}), 503


@bp.get("/activity")
def account_activity():
    session, error_response = _auth_session()
    if error_response:
        return error_response
    email = _email(session or {})
    limit_raw = request.args.get("limit")
    try:
        limit = max(10, min(int(limit_raw or 75), 200))
    except Exception:
        limit = 75

    items: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}
    for kind, table, fallback, href, timestamp_field in ACTIVITY_SOURCES:
        result = _safe_rows_for_email(table, email, limit=20, order_by=timestamp_field)
        if not result["ok"]:
            errors[kind] = result["error"]
            continue
        for row in result["rows"]:
            occurred_at = row.get(timestamp_field) or row.get("created_at")
            items.append({
                "kind": kind,
                "id": row.get("id"),
                "title": _row_title(kind, row, fallback),
                "summary": fallback,
                "status": row.get("status") or row.get("application_stage") or row.get("event_status") or row.get("risk_level"),
                "occurred_at": occurred_at,
                "href": href,
            })
    items.sort(key=lambda item: str(item.get("occurred_at") or ""), reverse=True)
    return jsonify({
        "ok": True,
        "generated_at": _now_iso(),
        "activity": items[:limit],
        "count": min(len(items), limit),
        "partial_errors": errors,
        "privacy_note": "Activity includes account-owned metadata and status history only. It does not expose raw documents, full authority references, OTPs, passwords, payment credentials, or session-token hashes.",
    })


@bp.get("/data-export")
def data_export():
    session, error_response = _auth_session()
    if error_response:
        return error_response
    email = _email(session or {})
    export: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    try:
        export["preferences"] = _public_preferences(_load_preferences(email), email)
    except Exception as exc:
        export["preferences"] = None
        errors["preferences"] = str(exc)[:800]

    for table in EXPORT_TABLES:
        result = _safe_rows_for_email(table, email, limit=500, order_by="created_at")
        if result["ok"]:
            export[table] = result["rows"]
        else:
            export[table] = []
            errors[table] = result["error"]

    return jsonify({
        "ok": True,
        "export_version": "moveready-account-export-v1",
        "generated_at": _now_iso(),
        "email": email,
        "data": export,
        "partial_errors": errors,
        "excluded_security_data": [
            "OTP codes and hashes",
            "session tokens and token hashes",
            "administrator secrets",
            "payment credentials",
            "passwords and private keys",
            "raw documents and file contents",
        ],
        "note": "This is an immediate machine-readable account export. A formal privacy request can also be opened for reviewed access, correction, restriction, consent withdrawal, or deletion.",
    })


@bp.get("/privacy-requests")
def list_privacy_requests():
    session, error_response = _auth_session()
    if error_response:
        return error_response
    email = _email(session or {})
    result = _safe_rows_for_email("relocation_privacy_requests", email, limit=50, order_by="created_at")
    if not result["ok"]:
        return jsonify({"ok": False, "error": "privacy_requests_unavailable", "details": result["error"]}), 503
    rows = [
        {
            "id": row.get("id"),
            "request_ref": row.get("request_ref"),
            "request_type": row.get("request_type"),
            "status": row.get("status"),
            "priority": row.get("priority"),
            "request_summary": row.get("request_summary"),
            "requested_scope": row.get("requested_scope"),
            "identity_reverification_required": row.get("identity_reverification_required"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "completed_at": row.get("completed_at"),
        }
        for row in result["rows"]
    ]
    return jsonify({"ok": True, "requests": rows, "count": len(rows)})


@bp.post("/privacy-requests")
def create_privacy_request():
    session, error_response = _auth_session()
    if error_response:
        return error_response
    email = _email(session or {})
    payload = request.get_json(silent=True) or {}
    request_type = _text(payload.get("request_type"), 60)
    summary = _text(payload.get("request_summary"), 1500)
    scope = _text(payload.get("requested_scope"), 1500)
    confirmation = _text(payload.get("confirmation_phrase"), 120)

    if request_type not in PRIVACY_REQUEST_TYPES:
        return jsonify({"ok": False, "error": "invalid_privacy_request_type"}), 400
    if not summary:
        return jsonify({"ok": False, "error": "request_summary_required"}), 400

    destructive = request_type in {"account_deletion", "consent_withdrawal"}
    if destructive and confirmation != DELETION_CONFIRMATION:
        return jsonify({
            "ok": False,
            "error": "explicit_confirmation_phrase_required",
            "required_phrase": DELETION_CONFIRMATION,
        }), 400

    row = {
        "request_ref": f"MRPRIV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}",
        "email": email,
        "request_type": request_type,
        "status": "identity_verification_required" if destructive else "received",
        "priority": "high" if destructive else "normal",
        "request_summary": summary,
        "requested_scope": scope,
        "user_confirmation": destructive,
        "identity_reverification_required": True,
        "metadata": {
            "source_page": _text(payload.get("source_page"), 240) or "/settings",
            "verified_session_id": (session or {}).get("id"),
            "instant_deletion_performed": False,
        },
    }
    try:
        response = get_supabase().table("relocation_privacy_requests").insert(row).execute()
        stored = (response.data or [row])[0]
        return jsonify({
            "ok": True,
            "request": {
                "request_ref": stored.get("request_ref"),
                "request_type": stored.get("request_type"),
                "status": stored.get("status"),
                "priority": stored.get("priority"),
                "identity_reverification_required": stored.get("identity_reverification_required"),
                "created_at": stored.get("created_at"),
            },
            "safety_note": "No account data was deleted automatically. Destructive requests require identity reverification, scope review, legal-retention checks, administrator approval, and an auditable completion record.",
        }), 201
    except Exception as exc:
        return jsonify({"ok": False, "error": "privacy_request_create_failed", "details": str(exc)[:800]}), 503


@bp.post("/privacy-requests/<request_ref>/cancel")
def cancel_privacy_request(request_ref: str):
    session, error_response = _auth_session()
    if error_response:
        return error_response
    email = _email(session or {})
    try:
        response = (
            get_supabase()
            .table("relocation_privacy_requests")
            .select("id,status")
            .eq("request_ref", request_ref)
            .eq("email", email)
            .limit(1)
            .execute()
        )
        row = (response.data or [None])[0]
        if not row:
            return jsonify({"ok": False, "error": "privacy_request_not_found"}), 404
        if row.get("status") not in {"received", "identity_verification_required", "reviewing"}:
            return jsonify({"ok": False, "error": "privacy_request_cannot_be_cancelled_at_current_status"}), 409
        update = (
            get_supabase()
            .table("relocation_privacy_requests")
            .update({"status": "cancelled"})
            .eq("id", row.get("id"))
            .eq("email", email)
            .execute()
        )
        return jsonify({"ok": True, "cancelled": bool(update.data), "request_ref": request_ref})
    except Exception as exc:
        return jsonify({"ok": False, "error": "privacy_request_cancel_failed", "details": str(exc)[:800]}), 503
