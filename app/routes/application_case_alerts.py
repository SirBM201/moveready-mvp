from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from flask import Blueprint, jsonify, request

from app.routes import account_auth, application_cases
from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access


user_bp = Blueprint("application_case_alerts", __name__)
admin_bp = Blueprint("application_case_alerts_admin", __name__)

ALERT_STATUSES = {"open", "dismissed", "resolved", "expired"}
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _text(value: Any, limit: int = 500) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


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


def _public_alert(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "application_case_id": row.get("application_case_id"),
        "alert_type": row.get("alert_type"),
        "severity": row.get("severity"),
        "status": row.get("status"),
        "title": row.get("title"),
        "summary": row.get("summary"),
        "due_at": row.get("due_at"),
        "first_detected_at": row.get("first_detected_at"),
        "last_detected_at": row.get("last_detected_at"),
        "resolved_at": row.get("resolved_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "metadata": row.get("metadata") or {},
    }


def _alert_key(case_id: str, category: str, marker: str) -> str:
    safe_marker = marker.replace(" ", "_")[:120]
    return f"application:{case_id}:{category}:{safe_marker}"[:240]


def _candidate(alert_type: str, severity: str, title: str, summary: str, *, key: str, due_at: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "alert_type": alert_type,
        "severity": severity,
        "title": title,
        "summary": summary,
        "alert_key": key,
        "due_at": due_at,
        "metadata": {"generated_by": "application_case_daily_scan", **(metadata or {})},
    }


def _candidates_for_case(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    case_id = str(case.get("id") or "")
    case_ref = str(case.get("case_ref") or "Application case")
    case_title = str(case.get("case_title") or case_ref)
    stage = str(case.get("application_stage") or "research")
    source_status = str(case.get("source_status") or "review_required")
    payment_status = str(case.get("payment_status") or "not_recorded")
    deadline = application_cases._datetime(case.get("next_deadline_at"))
    appointment = application_cases._datetime(case.get("appointment_date"))
    rows: List[Dict[str, Any]] = []

    if deadline:
        hours = (deadline - _now()).total_seconds() / 3600
        marker = deadline.isoformat()
        if hours < 0:
            rows.append(
                _candidate(
                    "deadline_overdue",
                    "critical",
                    f"Deadline overdue: {case_title}",
                    "The recorded application deadline has passed. Confirm the authority's exact deadline, time zone, channel, and whether any remedy remains available.",
                    key=_alert_key(case_id, "deadline", marker),
                    due_at=deadline.isoformat(),
                    metadata={"case_ref": case_ref, "hours_until_deadline": round(hours, 1)},
                )
            )
        elif hours <= 72:
            rows.append(
                _candidate(
                    "deadline_due_72h",
                    "critical",
                    f"Deadline within 72 hours: {case_title}",
                    "An application deadline is within 72 hours. Confirm the official notice, time zone, required evidence, payment, and submission channel immediately.",
                    key=_alert_key(case_id, "deadline", marker),
                    due_at=deadline.isoformat(),
                    metadata={"case_ref": case_ref, "hours_until_deadline": round(hours, 1)},
                )
            )
        elif hours <= 336:
            rows.append(
                _candidate(
                    "deadline_due_14d",
                    "high",
                    f"Deadline within 14 days: {case_title}",
                    "An application deadline is approaching. Review the current official source, evidence pack, payment status, and submission plan.",
                    key=_alert_key(case_id, "deadline", marker),
                    due_at=deadline.isoformat(),
                    metadata={"case_ref": case_ref, "hours_until_deadline": round(hours, 1)},
                )
            )

    if appointment:
        hours = (appointment - _now()).total_seconds() / 3600
        if -24 <= hours <= 168:
            severity = "critical" if hours <= 24 else "high"
            rows.append(
                _candidate(
                    "appointment_due_7d",
                    severity,
                    f"Appointment requires attention: {case_title}",
                    "Confirm the appointment notice, location, time zone, travel time, originals, translations, payment, biometrics, and rescheduling rules.",
                    key=_alert_key(case_id, "appointment", appointment.isoformat()),
                    due_at=appointment.isoformat(),
                    metadata={"case_ref": case_ref, "hours_until_appointment": round(hours, 1)},
                )
            )

    if stage == "additional_documents_requested":
        marker = str(case.get("updated_at") or case.get("submission_date") or "current")[:10]
        rows.append(
            _candidate(
                "additional_documents_requested",
                "critical",
                f"Additional documents requested: {case_title}",
                "Review the authority's exact request, deadline, permitted format, translation or legalization rule, and submission channel. Do not send unrequested documents.",
                key=_alert_key(case_id, "additional_documents", marker),
                due_at=deadline.isoformat() if deadline else None,
                metadata={"case_ref": case_ref},
            )
        )

    if source_status in {"stale", "unavailable"}:
        rows.append(
            _candidate(
                "source_stale_or_unavailable",
                "high" if source_status == "stale" else "critical",
                f"Official source needs urgent verification: {case_title}",
                "The stored official source is stale or unavailable. Do not rely on the recorded rule, fee, appointment, or deadline until a current authority source is confirmed.",
                key=_alert_key(case_id, "source", source_status),
                metadata={"case_ref": case_ref, "source_status": source_status},
            )
        )
    elif source_status == "review_required" and stage in {"appointment_booked", "submitted", "biometrics_completed", "interview_scheduled", "additional_documents_requested", "decision_pending"}:
        rows.append(
            _candidate(
                "source_review_required",
                "high",
                f"Verify the active case source: {case_title}",
                "This active application case has not recorded a verified official instruction or tracking source.",
                key=_alert_key(case_id, "source", "review_required"),
                metadata={"case_ref": case_ref},
            )
        )

    if payment_status in {"pending", "disputed"}:
        rows.append(
            _candidate(
                "payment_attention",
                "high" if payment_status == "pending" else "critical",
                f"Application payment {payment_status}: {case_title}",
                "Confirm the payment recipient, amount, currency, reference, receipt, refund rule, and dispute path through the official authority or approved payment channel.",
                key=_alert_key(case_id, "payment", payment_status),
                metadata={"case_ref": case_ref, "payment_status": payment_status},
            )
        )

    if stage == "refused":
        marker = str(case.get("decision_date") or case.get("updated_at") or "current")[:10]
        rows.append(
            _candidate(
                "refusal_followup",
                "critical",
                f"Refusal follow-up required: {case_title}",
                "Preserve the written decision, record the actual reason, check review or appeal deadlines, and use refusal-repair or qualified legal advice before a new substantive application.",
                key=_alert_key(case_id, "refusal", marker),
                metadata={"case_ref": case_ref},
            )
        )
    elif stage == "approved" and case.get("status") != "completed":
        marker = str(case.get("decision_date") or case.get("updated_at") or "current")[:10]
        rows.append(
            _candidate(
                "decision_followup",
                "medium",
                f"Complete approval follow-up: {case_title}",
                "Record post-decision conditions, permit collection, travel window, registration, insurance, accommodation, and settlement deadlines before closing the case.",
                key=_alert_key(case_id, "decision", marker),
                metadata={"case_ref": case_ref},
            )
        )

    return rows


def _existing_alert(key: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_application_case_alerts")
        .select("*")
        .eq("alert_key", key)
        .maybe_single()
        .execute()
    )
    return response.data


def _upsert_alert(case: Dict[str, Any], candidate: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    existing = _existing_alert(candidate["alert_key"])
    now = _now_iso()
    if existing:
        previous_rank = SEVERITY_RANK.get(str(existing.get("severity") or "medium"), 1)
        new_rank = SEVERITY_RANK.get(candidate["severity"], 1)
        previous_status = str(existing.get("status") or "open")
        status = previous_status
        resolved_at = existing.get("resolved_at")
        if previous_status in {"resolved", "expired"} or new_rank > previous_rank:
            status = "open"
            resolved_at = None
        updates = {
            "alert_type": candidate["alert_type"],
            "severity": candidate["severity"],
            "title": candidate["title"],
            "summary": candidate["summary"],
            "due_at": candidate.get("due_at"),
            "last_detected_at": now,
            "status": status,
            "resolved_at": resolved_at,
            "metadata": candidate.get("metadata") or {},
        }
        response = (
            get_supabase()
            .table("relocation_application_case_alerts")
            .update(updates)
            .eq("id", existing.get("id"))
            .execute()
        )
        return (response.data or [existing])[0], "updated"

    row = {
        "application_case_id": case.get("id"),
        "email": str(case.get("email") or "").strip().lower(),
        "alert_key": candidate["alert_key"],
        "alert_type": candidate["alert_type"],
        "severity": candidate["severity"],
        "status": "open",
        "title": candidate["title"],
        "summary": candidate["summary"],
        "due_at": candidate.get("due_at"),
        "first_detected_at": now,
        "last_detected_at": now,
        "metadata": candidate.get("metadata") or {},
    }
    response = get_supabase().table("relocation_application_case_alerts").insert(row).execute()
    return (response.data or [None])[0], "created"


def _resolve_obsolete(case: Dict[str, Any], active_keys: Set[str]) -> int:
    try:
        response = (
            get_supabase()
            .table("relocation_application_case_alerts")
            .select("*")
            .eq("application_case_id", case.get("id"))
            .in_("status", ["open", "dismissed"])
            .execute()
        )
        resolved = 0
        for row in response.data or []:
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            if metadata.get("generated_by") != "application_case_daily_scan":
                continue
            if str(row.get("alert_key") or "") in active_keys:
                continue
            get_supabase().table("relocation_application_case_alerts").update(
                {"status": "resolved", "resolved_at": _now_iso()}
            ).eq("id", row.get("id")).execute()
            resolved += 1
        return resolved
    except Exception:
        return 0


def scan_application_cases() -> Dict[str, Any]:
    response = (
        get_supabase()
        .table("relocation_application_cases")
        .select("*")
        .in_("status", ["active", "attention_required", "completed"])
        .order("updated_at", desc=True)
        .limit(2000)
        .execute()
    )
    created = 0
    updated = 0
    resolved = 0
    errors: List[Dict[str, str]] = []
    case_results: List[Dict[str, Any]] = []

    for case in response.data or []:
        if case.get("status") == "completed" and case.get("application_stage") != "approved":
            candidates: List[Dict[str, Any]] = []
        else:
            candidates = _candidates_for_case(case)
        active_keys = {item["alert_key"] for item in candidates}
        case_created = 0
        case_updated = 0
        try:
            for candidate in candidates:
                _row, action = _upsert_alert(case, candidate)
                if action == "created":
                    created += 1
                    case_created += 1
                else:
                    updated += 1
                    case_updated += 1
            case_resolved = _resolve_obsolete(case, active_keys)
            resolved += case_resolved
            case_results.append(
                {
                    "case_ref": case.get("case_ref"),
                    "active_alert_count": len(candidates),
                    "created": case_created,
                    "updated": case_updated,
                    "resolved": case_resolved,
                }
            )
        except Exception as exc:
            errors.append({"case_ref": str(case.get("case_ref") or case.get("id")), "error": str(exc)[:800]})

    return {
        "status": "completed_with_errors" if errors else "completed",
        "case_count": len(response.data or []),
        "alerts_created": created,
        "alerts_updated": updated,
        "alerts_resolved": resolved,
        "errors": errors,
        "case_results": case_results,
        "generated_at": _now_iso(),
    }


@user_bp.get("/alerts")
def my_alerts():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    include_dismissed = str(request.args.get("include_dismissed") or "").lower() in {"1", "true", "yes"}
    try:
        query = (
            get_supabase()
            .table("relocation_application_case_alerts")
            .select("*")
            .eq("email", email)
            .order("updated_at", desc=True)
            .limit(200)
        )
        if not include_dismissed:
            query = query.eq("status", "open")
        response = query.execute()
        rows = [_public_alert(row) for row in (response.data or [])]
        return jsonify({"ok": True, "account_email": email, "alert_count": len(rows), "application_alerts": rows})
    except Exception as exc:
        return jsonify({"ok": False, "error": "application_case_alerts_unavailable", "details": str(exc), "hint": "Apply supabase/migrations/029_application_case_alerts.sql."}), 503


@user_bp.patch("/alerts/<alert_id>")
def update_my_alert(alert_id: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    status = _text(payload.get("status"), 40)
    if status not in {"dismissed", "open"}:
        return jsonify({"ok": False, "error": "user_alert_status_must_be_open_or_dismissed"}), 400
    try:
        response = (
            get_supabase()
            .table("relocation_application_case_alerts")
            .update({"status": status, "resolved_at": None})
            .eq("id", alert_id)
            .eq("email", email)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "application_alert_not_found"}), 404
        return jsonify({"ok": True, "application_alert": _public_alert(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "application_alert_update_failed", "details": str(exc)}), 503


@admin_bp.get("/application-case-alerts")
@require_admin_access
def admin_alerts():
    status = _text(request.args.get("status"), 40)
    severity = _text(request.args.get("severity"), 40)
    email = _text(request.args.get("email"), 255)
    try:
        limit = max(1, min(int(request.args.get("limit") or 250), 500))
    except (TypeError, ValueError):
        limit = 250
    if status and status not in ALERT_STATUSES:
        return jsonify({"ok": False, "error": "invalid_alert_status", "allowed": sorted(ALERT_STATUSES)}), 400
    if severity and severity not in SEVERITY_RANK:
        return jsonify({"ok": False, "error": "invalid_alert_severity", "allowed": sorted(SEVERITY_RANK)}), 400
    try:
        query = (
            get_supabase()
            .table("relocation_application_case_alerts")
            .select("*")
            .order("updated_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if severity:
            query = query.eq("severity", severity)
        if email:
            query = query.eq("email", email.lower())
        response = query.execute()
        rows = [{**_public_alert(row), "email": row.get("email")} for row in (response.data or [])]
        return jsonify({"ok": True, "alert_count": len(rows), "application_alerts": rows})
    except Exception as exc:
        return jsonify({"ok": False, "error": "admin_application_alerts_unavailable", "details": str(exc), "hint": "Apply supabase/migrations/029_application_case_alerts.sql."}), 503


@admin_bp.patch("/application-case-alerts/<alert_id>")
@require_admin_access
def update_admin_alert(alert_id: str):
    payload = request.get_json(silent=True) or {}
    status = _text(payload.get("status"), 40)
    if status not in ALERT_STATUSES:
        return jsonify({"ok": False, "error": "invalid_alert_status", "allowed": sorted(ALERT_STATUSES)}), 400
    updates: Dict[str, Any] = {"status": status}
    if status in {"resolved", "expired"}:
        updates["resolved_at"] = _now_iso()
    else:
        updates["resolved_at"] = None
    try:
        response = get_supabase().table("relocation_application_case_alerts").update(updates).eq("id", alert_id).execute()
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "application_alert_not_found"}), 404
        return jsonify({"ok": True, "application_alert": {**_public_alert(updated), "email": updated.get("email")}})
    except Exception as exc:
        return jsonify({"ok": False, "error": "admin_application_alert_update_failed", "details": str(exc)}), 503


@admin_bp.post("/application-cases/alerts/scan")
@require_admin_access
def scan_due_alerts():
    try:
        result = scan_application_cases()
        return jsonify({"ok": True, **result}), 200 if not result.get("errors") else 207
    except Exception as exc:
        return jsonify({"ok": False, "status": "failed", "error": "application_case_alert_scan_failed", "details": str(exc)}), 503
