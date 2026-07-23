from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from app.routes import application_cases
from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access


bp = Blueprint("application_cases_admin", __name__)


def _text(value: Any, limit: int = 500) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


def _bounded_limit(value: Any, default: int = 100, maximum: int = 300) -> int:
    try:
        return max(1, min(int(value), maximum))
    except (TypeError, ValueError):
        return default


def _case_by_id(case_id: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_application_cases")
        .select("*")
        .eq("id", case_id)
        .maybe_single()
        .execute()
    )
    return response.data


def _admin_case(row: Dict[str, Any]) -> Dict[str, Any]:
    public = application_cases._public_case(row)
    return {
        **public,
        "email": row.get("email"),
        "metadata": row.get("metadata") or {},
        "consent_to_store": bool(row.get("consent_to_store")),
    }


@bp.get("/application-cases")
@require_admin_access
def list_cases():
    status = _text(request.args.get("status"), 40)
    stage = _text(request.args.get("application_stage"), 80)
    risk = _text(request.args.get("risk_level"), 40)
    source_status = _text(request.args.get("source_status"), 40)
    email = _text(request.args.get("email"), 255)
    target_country = _text(request.args.get("target_country"), 120)
    limit = _bounded_limit(request.args.get("limit"))

    if status and status not in application_cases.CASE_STATUSES:
        return jsonify({"ok": False, "error": "invalid_case_status", "allowed": application_cases.CASE_STATUSES}), 400
    if stage and stage not in application_cases.APPLICATION_STAGES:
        return jsonify({"ok": False, "error": "invalid_application_stage", "allowed": application_cases.APPLICATION_STAGES}), 400
    if risk and risk not in application_cases.RISK_LEVELS:
        return jsonify({"ok": False, "error": "invalid_risk_level", "allowed": application_cases.RISK_LEVELS}), 400
    if source_status and source_status not in application_cases.SOURCE_STATUSES:
        return jsonify({"ok": False, "error": "invalid_source_status", "allowed": application_cases.SOURCE_STATUSES}), 400

    try:
        query = (
            get_supabase()
            .table("relocation_application_cases")
            .select("*")
            .order("updated_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if stage:
            query = query.eq("application_stage", stage)
        if risk:
            query = query.eq("risk_level", risk)
        if source_status:
            query = query.eq("source_status", source_status)
        if email:
            query = query.eq("email", email.lower())
        if target_country:
            query = query.eq("target_country", target_country)
        response = query.execute()
        rows = [_admin_case(row) for row in (response.data or [])]
        attention = [
            row
            for row in rows
            if row.get("status") == "attention_required"
            or row.get("risk_level") in {"high", "critical"}
            or row.get("source_status") in {"review_required", "stale", "unavailable"}
            or (row.get("hours_until_deadline") is not None and float(row.get("hours_until_deadline")) <= 336)
        ]
        return jsonify(
            {
                "ok": True,
                "case_count": len(rows),
                "attention_count": len(attention),
                "application_cases": rows,
                "attention_cases": attention,
                "privacy_note": "Admin case views expose application metadata and masked reference hints only. Do not request raw documents through this workspace.",
            }
        )
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "error": "admin_application_cases_unavailable",
                "details": str(exc),
                "hint": "Apply supabase/migrations/028_application_case_manager.sql.",
            }
        ), 503


@bp.get("/application-cases/<case_id>")
@require_admin_access
def case_detail(case_id: str):
    try:
        case = _case_by_id(case_id)
        if not case:
            return jsonify({"ok": False, "error": "application_case_not_found"}), 404
        events_response = (
            get_supabase()
            .table("relocation_application_case_events")
            .select("*")
            .eq("application_case_id", case_id)
            .order("event_at", desc=True)
            .limit(250)
            .execute()
        )
        return jsonify(
            {
                "ok": True,
                "application_case": _admin_case(case),
                "events": [application_cases._public_event(row) for row in (events_response.data or [])],
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": "admin_application_case_detail_unavailable", "details": str(exc)}), 503


@bp.patch("/application-cases/<case_id>")
@require_admin_access
def update_case(case_id: str):
    payload = request.get_json(silent=True) or {}
    forbidden = application_cases._forbidden(payload)
    if forbidden:
        return jsonify({"ok": False, "error": "raw_or_sensitive_application_field_not_allowed", "forbidden_fields": forbidden}), 400

    try:
        existing = _case_by_id(case_id)
        if not existing:
            return jsonify({"ok": False, "error": "application_case_not_found"}), 404

        normalized_payload = dict(payload)
        normalized_payload.setdefault("case_title", existing.get("case_title"))
        normalized_payload.setdefault("route_category", existing.get("route_category"))
        normalized_payload.setdefault("application_stage", existing.get("application_stage"))
        normalized_payload.setdefault("status", existing.get("status"))
        normalized_payload.setdefault("source_status", existing.get("source_status"))
        normalized_payload.setdefault("payment_status", existing.get("payment_status"))

        row, validation_error = application_cases._case_payload(
            str(existing.get("email") or "").strip().lower(),
            normalized_payload,
            existing=existing,
        )
        if validation_error:
            body, status = validation_error
            return jsonify(body), status
        assert row is not None

        response = (
            get_supabase()
            .table("relocation_application_cases")
            .update(row)
            .eq("id", case_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "application_case_not_found"}), 404

        admin_owner = _text(payload.get("admin_owner"), 180) or "MoveReady admin"
        old_stage = str(existing.get("application_stage") or "research")
        new_stage = str(updated.get("application_stage") or old_stage)
        old_status = str(existing.get("status") or "active")
        new_status = str(updated.get("status") or old_status)

        if new_stage != old_stage:
            application_cases._record_event(
                updated,
                application_cases._event_type_for_stage(new_stage),
                f"Application stage changed to {new_stage.replace('_', ' ')}",
                summary=_text(payload.get("event_summary"), 1600),
                actor_type="admin",
                actor_reference=admin_owner,
                payload={"from": old_stage, "to": new_stage},
            )
        elif new_status != old_status:
            application_cases._record_event(
                updated,
                "status_changed" if new_status != "archived" else "case_archived",
                f"Case status changed to {new_status.replace('_', ' ')}",
                summary=_text(payload.get("event_summary"), 1600),
                actor_type="admin",
                actor_reference=admin_owner,
                payload={"from": old_status, "to": new_status},
            )
        else:
            application_cases._record_event(
                updated,
                "note",
                "Application case reviewed by MoveReady admin",
                summary=_text(payload.get("event_summary"), 1600) or "Case metadata or source review fields were updated.",
                actor_type="admin",
                actor_reference=admin_owner,
            )

        return jsonify({"ok": True, "application_case": _admin_case(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "admin_application_case_update_failed", "details": str(exc)}), 503


@bp.post("/application-cases/<case_id>/events")
@require_admin_access
def add_event(case_id: str):
    payload = request.get_json(silent=True) or {}
    forbidden = application_cases._forbidden(payload)
    if forbidden:
        return jsonify({"ok": False, "error": "raw_or_sensitive_application_field_not_allowed", "forbidden_fields": forbidden}), 400

    event_type = _text(payload.get("event_type"), 80) or "note"
    event_status = _text(payload.get("event_status"), 40) or "recorded"
    title = _text(payload.get("event_title"), 180)
    summary = _text(payload.get("event_summary"), 1600)
    due_at = application_cases._datetime(payload.get("due_at"))
    actor_type = _text(payload.get("actor_type"), 40) or "admin"
    admin_owner = _text(payload.get("admin_owner"), 180) or "MoveReady admin"

    if event_type not in application_cases.EVENT_TYPES:
        return jsonify({"ok": False, "error": "invalid_event_type", "allowed": application_cases.EVENT_TYPES}), 400
    if event_status not in application_cases.EVENT_STATUSES:
        return jsonify({"ok": False, "error": "invalid_event_status", "allowed": application_cases.EVENT_STATUSES}), 400
    if actor_type not in {"admin", "provider", "system", "authority"}:
        return jsonify({"ok": False, "error": "invalid_admin_event_actor_type"}), 400
    if not title:
        return jsonify({"ok": False, "error": "event_title_required"}), 400

    try:
        case = _case_by_id(case_id)
        if not case:
            return jsonify({"ok": False, "error": "application_case_not_found"}), 404
        event = application_cases._record_event(
            case,
            event_type,
            title,
            summary=summary,
            due_at=due_at.isoformat() if due_at else None,
            actor_type=actor_type,
            actor_reference=admin_owner,
            status=event_status,
        )
        if not event:
            return jsonify({"ok": False, "error": "application_case_event_not_stored"}), 503
        return jsonify({"ok": True, "event": application_cases._public_event(event)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "admin_application_case_event_failed", "details": str(exc)}), 503


@bp.get("/application-cases/deadlines/due")
@require_admin_access
def due_deadlines():
    try:
        hours = max(1, min(int(request.args.get("hours") or 336), 2160))
        limit = _bounded_limit(request.args.get("limit"), default=150, maximum=300)
    except (TypeError, ValueError):
        hours = 336
        limit = 150

    cutoff = datetime.now(timezone.utc).timestamp() + (hours * 3600)
    try:
        response = (
            get_supabase()
            .table("relocation_application_cases")
            .select("*")
            .in_("status", ["active", "attention_required"])
            .order("updated_at", desc=True)
            .limit(1000)
            .execute()
        )
        rows = []
        for row in response.data or []:
            deadline = application_cases._datetime(row.get("next_deadline_at"))
            if not deadline:
                continue
            if deadline.timestamp() <= cutoff:
                rows.append(_admin_case(row))
        rows.sort(key=lambda item: item.get("next_deadline_at") or "9999")
        rows = rows[:limit]
        return jsonify(
            {
                "ok": True,
                "window_hours": hours,
                "case_count": len(rows),
                "application_cases": rows,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": "application_case_deadlines_unavailable", "details": str(exc)}), 503
