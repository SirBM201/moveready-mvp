from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request

from app.routes import account_auth
from app.services.supabase_client import get_supabase


user_bp = Blueprint("application_cases", __name__)
admin_bp = Blueprint("application_cases_admin", __name__)

ROUTE_CATEGORIES = [
    "visit", "study", "work", "startup", "business", "digital_nomad",
    "family", "scholarship", "permanent_residence", "citizenship", "other",
]
APPLICATION_STAGES = [
    "research",
    "preparing",
    "appointment_booked",
    "submitted",
    "biometrics_completed",
    "interview_scheduled",
    "additional_documents_requested",
    "decision_pending",
    "approved",
    "refused",
    "withdrawn",
    "expired",
    "closed",
]
CASE_STATUSES = ["active", "attention_required", "completed", "archived"]
RISK_LEVELS = ["low", "medium", "high", "critical"]
SOURCE_STATUSES = ["verified", "review_required", "stale", "unavailable"]
PAYMENT_STATUSES = ["not_recorded", "not_required", "planned", "pending", "paid", "refunded", "disputed"]
EVENT_TYPES = [
    "case_created",
    "status_changed",
    "deadline_added",
    "appointment",
    "submission",
    "biometrics",
    "interview",
    "additional_documents_request",
    "payment",
    "communication",
    "decision",
    "note",
    "timeline_tasks_created",
    "case_archived",
]
EVENT_STATUSES = ["recorded", "pending", "completed", "cancelled", "disputed"]
TERMINAL_STAGES = {"approved", "refused", "withdrawn", "expired", "closed"}

STAGE_TRANSITIONS: Dict[str, Set[str]] = {
    "research": {"preparing", "withdrawn", "closed"},
    "preparing": {"appointment_booked", "submitted", "withdrawn", "expired", "closed"},
    "appointment_booked": {"preparing", "submitted", "biometrics_completed", "interview_scheduled", "withdrawn", "expired", "closed"},
    "submitted": {"biometrics_completed", "interview_scheduled", "additional_documents_requested", "decision_pending", "approved", "refused", "withdrawn", "expired", "closed"},
    "biometrics_completed": {"interview_scheduled", "additional_documents_requested", "decision_pending", "approved", "refused", "withdrawn", "expired", "closed"},
    "interview_scheduled": {"additional_documents_requested", "decision_pending", "approved", "refused", "withdrawn", "expired", "closed"},
    "additional_documents_requested": {"submitted", "decision_pending", "approved", "refused", "withdrawn", "expired", "closed"},
    "decision_pending": {"additional_documents_requested", "approved", "refused", "withdrawn", "expired", "closed"},
    "approved": {"closed"},
    "refused": {"closed"},
    "withdrawn": {"closed"},
    "expired": {"closed"},
    "closed": set(),
}

FORBIDDEN_FIELDS = {
    "file", "file_content", "file_url", "passport_number", "document_number",
    "national_id_number", "bank_account_number", "card_number", "cvv", "otp",
    "password", "private_key", "full_authority_reference", "raw_correspondence",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _text(value: Any, limit: int = 500) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _number(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        parsed = round(float(value), 2)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _date(value: Any) -> Optional[date]:
    raw = _text(value, 40)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _datetime(value: Any) -> Optional[datetime]:
    raw = _text(value, 80)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _valid_url(value: Optional[str]) -> bool:
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _forbidden(payload: Dict[str, Any]) -> List[str]:
    return sorted(field for field in FORBIDDEN_FIELDS if payload.get(field) not in (None, "", [], {}))


def _auth_email() -> Tuple[Optional[str], Optional[str]]:
    try:
        token = account_auth._extract_session_token()
        if not token:
            return None, "session_token_required"
        session, error = account_auth._load_active_session(token)
        if not session:
            return None, error or "invalid_session"
        email = str(session.get("email") or "").strip().lower()
        return (email or None), (None if email else "session_email_missing")
    except Exception:
        return None, "session_validation_failed"


def _owned_link(email: str, table: str, value: Any) -> Optional[str]:
    record_id = _text(value, 80)
    if not record_id:
        return None
    try:
        response = (
            get_supabase()
            .table(table)
            .select("id,email")
            .eq("id", record_id)
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        return (response.data or {}).get("id")
    except Exception:
        return None


def _route_version(value: Any) -> Optional[str]:
    record_id = _text(value, 80)
    if not record_id:
        return None
    try:
        response = (
            get_supabase()
            .table("relocation_route_versions")
            .select("id,status")
            .eq("id", record_id)
            .maybe_single()
            .execute()
        )
        return (response.data or {}).get("id")
    except Exception:
        return None


def _case_for_email(case_ref: str, email: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_application_cases")
        .select("*")
        .eq("case_ref", case_ref)
        .eq("email", email)
        .maybe_single()
        .execute()
    )
    return response.data


def _risk_from_case(row: Dict[str, Any]) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    score = 0
    stage = str(row.get("application_stage") or "research")
    source_status = str(row.get("source_status") or "review_required")
    payment_status = str(row.get("payment_status") or "not_recorded")
    next_deadline = _datetime(row.get("next_deadline_at"))
    appointment = _datetime(row.get("appointment_date"))

    if source_status == "unavailable":
        score += 45
        warnings.append("The official source is unavailable. Do not rely on the stored route or deadline without current verification.")
    elif source_status == "stale":
        score += 30
        warnings.append("The official source or route information is marked stale.")
    elif source_status == "review_required":
        score += 15
        warnings.append("Official source verification is still required.")

    if next_deadline:
        hours = (next_deadline - _now()).total_seconds() / 3600
        if hours < 0:
            score += 45
            warnings.append("The recorded next deadline has passed.")
        elif hours <= 72:
            score += 35
            warnings.append("The next deadline is within 72 hours.")
        elif hours <= 336:
            score += 20
            warnings.append("The next deadline is within 14 days.")
    if appointment:
        hours = (appointment - _now()).total_seconds() / 3600
        if -24 <= hours <= 168:
            score += 20
            warnings.append("An appointment is within seven days or was due within the last day.")

    if stage == "additional_documents_requested":
        score += 35
        warnings.append("The authority requested additional documents. Confirm the exact request, format, channel, and deadline from the official notice.")
    if stage == "refused":
        score += 55
        warnings.append("The case is refused. Preserve the written decision and use refusal-repair or qualified legal review before a new substantive application.")
    if stage == "submitted" and not row.get("submission_date"):
        score += 20
        warnings.append("The case is marked submitted but no submission date is recorded.")
    if stage in {"submitted", "decision_pending", "biometrics_completed", "interview_scheduled"} and not row.get("official_source_url"):
        score += 15
        warnings.append("No official tracking or instruction source is recorded for an active submitted case.")
    if payment_status in {"pending", "disputed"}:
        score += 15 if payment_status == "pending" else 35
        warnings.append(f"Application payment is {payment_status}.")

    if score >= 100:
        risk = "critical"
    elif score >= 60:
        risk = "high"
    elif score >= 25:
        risk = "medium"
    else:
        risk = "low"
    return risk, warnings


def _public_case(row: Dict[str, Any]) -> Dict[str, Any]:
    risk, warnings = _risk_from_case(row)
    next_deadline = _datetime(row.get("next_deadline_at"))
    return {
        "id": row.get("id"),
        "case_ref": row.get("case_ref"),
        "profile_id": row.get("profile_id"),
        "saved_route_id": row.get("saved_route_id"),
        "route_version_id": row.get("route_version_id"),
        "evidence_pack_id": row.get("evidence_pack_id"),
        "case_title": row.get("case_title"),
        "target_country": row.get("target_country"),
        "target_city": row.get("target_city"),
        "route_category": row.get("route_category"),
        "route_name": row.get("route_name"),
        "responsible_authority": row.get("responsible_authority"),
        "application_stage": row.get("application_stage"),
        "status": row.get("status"),
        "risk_level": risk,
        "stored_risk_level": row.get("risk_level"),
        "source_status": row.get("source_status"),
        "authority_reference_hint": row.get("authority_reference_hint"),
        "application_date": row.get("application_date"),
        "appointment_date": row.get("appointment_date"),
        "submission_date": row.get("submission_date"),
        "next_deadline_at": row.get("next_deadline_at"),
        "hours_until_deadline": round((next_deadline - _now()).total_seconds() / 3600, 1) if next_deadline else None,
        "decision_date": row.get("decision_date"),
        "fee_amount": row.get("fee_amount"),
        "fee_currency": row.get("fee_currency"),
        "payment_status": row.get("payment_status"),
        "official_source_url": row.get("official_source_url"),
        "official_source_note": row.get("official_source_note"),
        "result_summary": row.get("result_summary"),
        "notes": row.get("notes"),
        "warnings": warnings,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "privacy_note": "This case stores application metadata only. Use a masked reference hint and do not paste raw authority correspondence or document contents.",
    }


def _public_event(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "event_type": row.get("event_type"),
        "event_status": row.get("event_status"),
        "event_title": row.get("event_title"),
        "event_summary": row.get("event_summary"),
        "event_at": row.get("event_at"),
        "due_at": row.get("due_at"),
        "actor_type": row.get("actor_type"),
        "created_at": row.get("created_at"),
    }


def _record_event(case: Dict[str, Any], event_type: str, title: str, *, summary: Optional[str] = None, due_at: Optional[str] = None, actor_type: str = "user", actor_reference: Optional[str] = None, status: str = "recorded", payload: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    try:
        response = get_supabase().table("relocation_application_case_events").insert(
            {
                "application_case_id": case.get("id"),
                "event_type": event_type,
                "event_status": status,
                "event_title": title,
                "event_summary": summary,
                "event_at": _now_iso(),
                "due_at": due_at,
                "actor_type": actor_type,
                "actor_reference": actor_reference,
                "event_payload": payload or {},
            }
        ).execute()
        return (response.data or [None])[0]
    except Exception:
        return None


def _event_type_for_stage(stage: str) -> str:
    return {
        "appointment_booked": "appointment",
        "submitted": "submission",
        "biometrics_completed": "biometrics",
        "interview_scheduled": "interview",
        "additional_documents_requested": "additional_documents_request",
        "approved": "decision",
        "refused": "decision",
        "withdrawn": "decision",
        "expired": "decision",
        "closed": "decision",
    }.get(stage, "status_changed")


def _clean_reference_hint(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    hint = _text(payload.get("authority_reference_hint"), 80)
    if not hint:
        return None, None
    if payload.get("reference_is_masked") is not True:
        return None, "masked_reference_confirmation_required"
    compact = "".join(character for character in hint if character.isalnum())
    if len(compact) > 20:
        return None, "reference_hint_too_detailed"
    return hint, None


def _case_payload(email: str, payload: Dict[str, Any], *, existing: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[Dict[str, Any], int]]]:
    forbidden = _forbidden(payload)
    if forbidden:
        return None, ({"ok": False, "error": "raw_or_sensitive_application_field_not_allowed", "forbidden_fields": forbidden}, 400)

    route_category = _text(payload.get("route_category"), 80) or (existing or {}).get("route_category") or "other"
    stage = _text(payload.get("application_stage"), 80) or (existing or {}).get("application_stage") or "research"
    status = _text(payload.get("status"), 40) or (existing or {}).get("status") or "active"
    source_status = _text(payload.get("source_status"), 40) or (existing or {}).get("source_status") or "review_required"
    payment_status = _text(payload.get("payment_status"), 40) or (existing or {}).get("payment_status") or "not_recorded"

    if route_category not in ROUTE_CATEGORIES:
        return None, ({"ok": False, "error": "invalid_route_category", "allowed": ROUTE_CATEGORIES}, 400)
    if stage not in APPLICATION_STAGES:
        return None, ({"ok": False, "error": "invalid_application_stage", "allowed": APPLICATION_STAGES}, 400)
    if status not in CASE_STATUSES:
        return None, ({"ok": False, "error": "invalid_case_status", "allowed": CASE_STATUSES}, 400)
    if source_status not in SOURCE_STATUSES:
        return None, ({"ok": False, "error": "invalid_source_status", "allowed": SOURCE_STATUSES}, 400)
    if payment_status not in PAYMENT_STATUSES:
        return None, ({"ok": False, "error": "invalid_payment_status", "allowed": PAYMENT_STATUSES}, 400)

    if existing:
        old_stage = str(existing.get("application_stage") or "research")
        if stage != old_stage and stage not in STAGE_TRANSITIONS.get(old_stage, set()):
            return None, ({"ok": False, "error": "invalid_application_stage_transition", "current_stage": old_stage, "requested_stage": stage, "allowed": sorted(STAGE_TRANSITIONS.get(old_stage, set()))}, 409)

    case_title = _text(payload.get("case_title"), 180) or (existing or {}).get("case_title")
    if not case_title:
        return None, ({"ok": False, "error": "case_title_required"}, 400)
    if payload.get("consent_to_store") is not True and not existing:
        return None, ({"ok": False, "error": "application_case_storage_consent_required"}, 400)

    source_url = _text(payload.get("official_source_url"), 900) if "official_source_url" in payload else (existing or {}).get("official_source_url")
    if not _valid_url(source_url):
        return None, ({"ok": False, "error": "valid_official_source_url_required"}, 400)

    reference_hint, reference_error = _clean_reference_hint(payload) if "authority_reference_hint" in payload else ((existing or {}).get("authority_reference_hint"), None)
    if reference_error:
        return None, ({"ok": False, "error": reference_error, "message": "Use a masked label or short last-character hint only. Do not store a full authority, passport, permit, or payment reference."}, 400)

    decision_date = _date(payload.get("decision_date")) if "decision_date" in payload else _date((existing or {}).get("decision_date"))
    result_summary = _text(payload.get("result_summary"), 1600) if "result_summary" in payload else (existing or {}).get("result_summary")
    if stage in TERMINAL_STAGES and (not decision_date or not result_summary):
        return None, ({"ok": False, "error": "terminal_stage_requires_date_and_result_summary"}, 400)
    if status == "completed" and stage not in TERMINAL_STAGES:
        return None, ({"ok": False, "error": "completed_case_requires_terminal_stage"}, 400)

    appointment = _datetime(payload.get("appointment_date")) if "appointment_date" in payload else _datetime((existing or {}).get("appointment_date"))
    deadline = _datetime(payload.get("next_deadline_at")) if "next_deadline_at" in payload else _datetime((existing or {}).get("next_deadline_at"))
    application_date = _date(payload.get("application_date")) if "application_date" in payload else _date((existing or {}).get("application_date"))
    submission_date = _date(payload.get("submission_date")) if "submission_date" in payload else _date((existing or {}).get("submission_date"))
    if application_date and submission_date and submission_date < application_date:
        return None, ({"ok": False, "error": "submission_date_before_application_date"}, 400)

    row: Dict[str, Any] = {
        "email": email,
        "case_title": case_title,
        "target_country": _text(payload.get("target_country"), 120) if "target_country" in payload else (existing or {}).get("target_country"),
        "target_city": _text(payload.get("target_city"), 120) if "target_city" in payload else (existing or {}).get("target_city"),
        "route_category": route_category,
        "route_name": _text(payload.get("route_name"), 180) if "route_name" in payload else (existing or {}).get("route_name"),
        "responsible_authority": _text(payload.get("responsible_authority"), 180) if "responsible_authority" in payload else (existing or {}).get("responsible_authority"),
        "application_stage": stage,
        "status": status,
        "source_status": source_status,
        "authority_reference_hint": reference_hint,
        "application_date": application_date.isoformat() if application_date else None,
        "appointment_date": appointment.isoformat() if appointment else None,
        "submission_date": submission_date.isoformat() if submission_date else None,
        "next_deadline_at": deadline.isoformat() if deadline else None,
        "decision_date": decision_date.isoformat() if decision_date else None,
        "fee_amount": _number(payload.get("fee_amount")) if "fee_amount" in payload else (existing or {}).get("fee_amount"),
        "fee_currency": _text(payload.get("fee_currency"), 20) if "fee_currency" in payload else (existing or {}).get("fee_currency"),
        "payment_status": payment_status,
        "official_source_url": source_url,
        "official_source_note": _text(payload.get("official_source_note"), 1800) if "official_source_note" in payload else (existing or {}).get("official_source_note"),
        "result_summary": result_summary,
        "notes": _text(payload.get("notes"), 1800) if "notes" in payload else (existing or {}).get("notes"),
        "consent_to_store": True,
    }

    if not existing:
        row["profile_id"] = _owned_link(email, "relocation_user_profiles", payload.get("profile_id"))
        row["saved_route_id"] = _owned_link(email, "relocation_saved_routes", payload.get("saved_route_id"))
        row["evidence_pack_id"] = _owned_link(email, "relocation_evidence_packs", payload.get("evidence_pack_id"))
        row["route_version_id"] = _route_version(payload.get("route_version_id"))
        row["metadata"] = {
            "verified_account": True,
            "raw_files_stored": False,
            "full_authority_reference_stored": False,
            "source_page": _text(payload.get("source_page"), 240),
        }
    else:
        if "evidence_pack_id" in payload:
            row["evidence_pack_id"] = _owned_link(email, "relocation_evidence_packs", payload.get("evidence_pack_id"))
        if "saved_route_id" in payload:
            row["saved_route_id"] = _owned_link(email, "relocation_saved_routes", payload.get("saved_route_id"))
        if "route_version_id" in payload:
            row["route_version_id"] = _route_version(payload.get("route_version_id"))

    risk, _warnings = _risk_from_case({**(existing or {}), **row})
    row["risk_level"] = risk
    if risk in {"high", "critical"} and status == "active":
        row["status"] = "attention_required"
    return row, None


@user_bp.get("/options")
def options():
    return jsonify(
        {
            "ok": True,
            "route_categories": ROUTE_CATEGORIES,
            "application_stages": APPLICATION_STAGES,
            "case_statuses": CASE_STATUSES,
            "source_statuses": SOURCE_STATUSES,
            "payment_statuses": PAYMENT_STATUSES,
            "event_types": EVENT_TYPES,
            "event_statuses": EVENT_STATUSES,
            "terminal_stages": sorted(TERMINAL_STAGES),
            "storage_boundary": "Store application metadata, masked reference hints, dates, status, fees, source notes, and short event summaries only. Do not upload raw files or paste full authority correspondence or sensitive reference numbers.",
        }
    )


@user_bp.get("")
@user_bp.get("/")
def my_cases():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    try:
        response = (
            get_supabase()
            .table("relocation_application_cases")
            .select("*")
            .eq("email", email)
            .neq("status", "archived")
            .order("updated_at", desc=True)
            .limit(100)
            .execute()
        )
        rows = [_public_case(row) for row in (response.data or [])]
        return jsonify({"ok": True, "account_email": email, "case_count": len(rows), "application_cases": rows})
    except Exception as exc:
        return jsonify({"ok": False, "error": "application_cases_unavailable", "details": str(exc), "hint": "Apply supabase/migrations/028_application_case_manager.sql."}), 503


@user_bp.post("")
@user_bp.post("/")
def create_case():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    row, validation_error = _case_payload(email, payload)
    if validation_error:
        body, status = validation_error
        return jsonify(body), status
    assert row is not None
    row["case_ref"] = f"MRAPP-{_now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
    try:
        response = get_supabase().table("relocation_application_cases").insert(row).execute()
        stored = (response.data or [None])[0]
        if not stored:
            return jsonify({"ok": False, "error": "application_case_not_stored"}), 503
        _record_event(stored, "case_created", "Application case created", summary="Private application tracking started.", actor_reference=email)
        if stored.get("next_deadline_at"):
            _record_event(stored, "deadline_added", "Next application deadline recorded", due_at=stored.get("next_deadline_at"), status="pending", actor_reference=email)
        return jsonify({"ok": True, "application_case": _public_case(stored)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "application_case_create_failed", "details": str(exc), "hint": "Apply supabase/migrations/028_application_case_manager.sql."}), 503


@user_bp.get("/<case_ref>")
def case_detail(case_ref: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    try:
        case = _case_for_email(case_ref, email)
        if not case:
            return jsonify({"ok": False, "error": "application_case_not_found"}), 404
        events_response = (
            get_supabase()
            .table("relocation_application_case_events")
            .select("*")
            .eq("application_case_id", case.get("id"))
            .order("event_at", desc=True)
            .limit(150)
            .execute()
        )
        return jsonify({"ok": True, "application_case": _public_case(case), "events": [_public_event(row) for row in (events_response.data or [])]})
    except Exception as exc:
        return jsonify({"ok": False, "error": "application_case_detail_unavailable", "details": str(exc)}), 503


@user_bp.patch("/<case_ref>")
def update_case(case_ref: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        existing = _case_for_email(case_ref, email)
        if not existing:
            return jsonify({"ok": False, "error": "application_case_not_found"}), 404
        row, validation_error = _case_payload(email, payload, existing=existing)
        if validation_error:
            body, status = validation_error
            return jsonify(body), status
        assert row is not None
        response = (
            get_supabase()
            .table("relocation_application_cases")
            .update(row)
            .eq("id", existing.get("id"))
            .eq("email", email)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "application_case_not_found"}), 404
        old_stage = str(existing.get("application_stage") or "research")
        new_stage = str(updated.get("application_stage") or old_stage)
        if new_stage != old_stage:
            _record_event(updated, _event_type_for_stage(new_stage), f"Application stage changed to {new_stage.replace('_', ' ')}", summary=_text(payload.get("event_summary"), 1200), actor_reference=email, payload={"from": old_stage, "to": new_stage})
        if updated.get("next_deadline_at") and updated.get("next_deadline_at") != existing.get("next_deadline_at"):
            _record_event(updated, "deadline_added", "Next application deadline updated", due_at=updated.get("next_deadline_at"), status="pending", actor_reference=email)
        return jsonify({"ok": True, "application_case": _public_case(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "application_case_update_failed", "details": str(exc)}), 503


@user_bp.post("/<case_ref>/events")
def create_event(case_ref: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    forbidden = _forbidden(payload)
    if forbidden:
        return jsonify({"ok": False, "error": "raw_or_sensitive_application_field_not_allowed", "forbidden_fields": forbidden}), 400
    event_type = _text(payload.get("event_type"), 80) or "note"
    event_status = _text(payload.get("event_status"), 40) or "recorded"
    title = _text(payload.get("event_title"), 180)
    summary = _text(payload.get("event_summary"), 1600)
    due_at = _datetime(payload.get("due_at"))
    if event_type not in EVENT_TYPES:
        return jsonify({"ok": False, "error": "invalid_event_type", "allowed": EVENT_TYPES}), 400
    if event_status not in EVENT_STATUSES:
        return jsonify({"ok": False, "error": "invalid_event_status", "allowed": EVENT_STATUSES}), 400
    if not title:
        return jsonify({"ok": False, "error": "event_title_required"}), 400
    try:
        case = _case_for_email(case_ref, email)
        if not case:
            return jsonify({"ok": False, "error": "application_case_not_found"}), 404
        event = _record_event(case, event_type, title, summary=summary, due_at=due_at.isoformat() if due_at else None, actor_reference=email, status=event_status)
        if not event:
            return jsonify({"ok": False, "error": "application_case_event_not_stored"}), 503
        return jsonify({"ok": True, "event": _public_event(event)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "application_case_event_create_failed", "details": str(exc)}), 503


def _timeline_candidates(case: Dict[str, Any], email: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    source_page = "/applications"
    base = {
        "email": email,
        "target_country": case.get("target_country"),
        "route_or_goal": case.get("case_title"),
        "route_category": case.get("route_category"),
        "event_type": "task",
        "preferred_channel": "in_app",
        "consent_to_contact": True,
        "source_page": source_page,
    }
    for title, due, priority, kind in [
        ("Prepare for application appointment", case.get("appointment_date"), "critical", "appointment"),
        ("Complete next application deadline", case.get("next_deadline_at"), "critical", "deadline"),
    ]:
        parsed = _datetime(due)
        if not parsed:
            continue
        rows.append(
            {
                **base,
                "event_title": f"{title}: {case.get('case_title')}",
                "event_notes": f"Application case {case.get('case_ref')} · {kind}. Confirm the exact official instruction, time zone, evidence, fee, and submission channel.",
                "due_date": parsed.date().isoformat(),
                "reminder_date": (parsed.date() - timedelta(days=2)).isoformat(),
                "priority": priority,
                "metadata": {
                    "generated_by": "application_case_manager",
                    "application_case_id": case.get("id"),
                    "application_case_ref": case.get("case_ref"),
                    "application_event_kind": kind,
                    "official_confirmation_required": True,
                },
            }
        )
    return rows


def _existing_timeline_keys(case: Dict[str, Any], email: str) -> Set[Tuple[str, str]]:
    try:
        response = (
            get_supabase()
            .table("relocation_timeline_events")
            .select("event_title,due_date,metadata")
            .eq("email", email)
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )
        keys: Set[Tuple[str, str]] = set()
        for row in response.data or []:
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            if str(metadata.get("application_case_id") or "") != str(case.get("id") or ""):
                continue
            keys.add((str(row.get("event_title") or ""), str(row.get("due_date") or "")))
        return keys
    except Exception:
        return set()


@user_bp.post("/<case_ref>/timeline-tasks")
def create_timeline_tasks(case_ref: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    if payload.get("confirm_timeline_storage") is not True:
        return jsonify({"ok": False, "error": "timeline_storage_confirmation_required"}), 400
    try:
        case = _case_for_email(case_ref, email)
        if not case:
            return jsonify({"ok": False, "error": "application_case_not_found"}), 404
        candidates = _timeline_candidates(case, email)
        if not candidates:
            return jsonify({"ok": False, "error": "appointment_or_deadline_required_for_timeline_tasks"}), 400
        existing = _existing_timeline_keys(case, email)
        new_rows = [row for row in candidates if (str(row.get("event_title") or ""), str(row.get("due_date") or "")) not in existing]
        if new_rows:
            get_supabase().table("relocation_timeline_events").insert(new_rows).execute()
        duplicate_count = len(candidates) - len(new_rows)
        _record_event(case, "timeline_tasks_created", "Application timeline tasks processed", summary=f"{len(new_rows)} new tasks saved; {duplicate_count} existing tasks not duplicated.", actor_reference=email, payload={"created": len(new_rows), "duplicates": duplicate_count})
        return jsonify({"ok": True, "created_count": len(new_rows), "existing_count": duplicate_count, "timeline_tasks": new_rows, "safety_note": "Generated dates are reminders. Confirm exact authority deadlines, time zones, appointment instructions, and submission channels."})
    except Exception as exc:
        return jsonify({"ok": False, "error": "application_timeline_tasks_failed", "details": str(exc)}), 503
