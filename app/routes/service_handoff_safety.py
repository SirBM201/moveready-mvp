from __future__ import annotations

from typing import Any, Dict, Optional, Set

from flask import jsonify, request

from app.routes.service_handoffs import CASE_PRIORITIES, CASE_STATUSES, HANDOFF_STATUSES, _now_iso, _public_case, _public_handoff, _record_handoff_event, _text
from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access


ADMIN_HANDOFF_TRANSITIONS: Dict[str, Set[str]] = {
    "draft": {"pending_user_consent", "cancelled", "blocked"},
    "pending_user_consent": {"cancelled", "blocked", "disputed"},
    "consent_confirmed": {"ready_to_share", "cancelled", "blocked", "disputed"},
    "ready_to_share": {"cancelled", "blocked", "disputed"},
    "shared": {"provider_acknowledged", "in_progress", "blocked", "disputed"},
    "provider_acknowledged": {"in_progress", "completed", "blocked", "disputed"},
    "in_progress": {"completed", "blocked", "disputed"},
    "blocked": {"pending_user_consent", "cancelled", "disputed"},
    "disputed": {"in_progress", "completed", "cancelled", "blocked"},
    "completed": set(),
    "cancelled": set(),
}

TERMINAL_CASE_STATUSES = {"resolved", "rejected", "closed"}
ACTIVE_CASE_STATUSES = {"open", "reviewing", "waiting_user", "waiting_provider", "escalated"}


def _handoff_by_id(handoff_id: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_service_handoffs")
        .select("*")
        .eq("id", handoff_id)
        .maybe_single()
        .execute()
    )
    return response.data


def _case_by_id(case_id: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_support_cases")
        .select("*")
        .eq("id", case_id)
        .maybe_single()
        .execute()
    )
    return response.data


def _consent_evidence_present(handoff: Dict[str, Any]) -> bool:
    payload = handoff.get("consent_payload") if isinstance(handoff.get("consent_payload"), dict) else {}
    shared_fields = handoff.get("shared_fields") if isinstance(handoff.get("shared_fields"), list) else []
    return bool(
        handoff.get("user_consent_confirmed")
        and handoff.get("consented_at")
        and _text(handoff.get("consent_version"), 120)
        and payload.get("confirmed") is True
        and shared_fields
    )


def _delivery_evidence_present(handoff: Dict[str, Any]) -> bool:
    return bool(
        handoff.get("shared_at")
        and _text(handoff.get("delivery_channel"), 80)
        and _text(handoff.get("delivery_reference"), 300)
    )


@require_admin_access
def safe_update_handoff_status(handoff_id: str):
    payload = request.get_json(silent=True) or {}
    target_status = _text(payload.get("status"), 40)
    if target_status not in HANDOFF_STATUSES:
        return jsonify({"ok": False, "error": "invalid_handoff_status", "allowed_statuses": sorted(HANDOFF_STATUSES)}), 400
    if target_status == "shared":
        return jsonify({"ok": False, "error": "use_mark_shared_endpoint_for_shared_status"}), 400
    if target_status == "consent_confirmed":
        return jsonify({"ok": False, "error": "user_consent_endpoint_required_for_consent_confirmed"}), 400

    try:
        handoff = _handoff_by_id(handoff_id)
        if not handoff:
            return jsonify({"ok": False, "error": "handoff_not_found"}), 404

        current_status = str(handoff.get("status") or "draft")
        if target_status == current_status:
            return jsonify({"ok": True, "service_handoff": _public_handoff(handoff), "unchanged": True})

        allowed = ADMIN_HANDOFF_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            return jsonify(
                {
                    "ok": False,
                    "error": "invalid_handoff_transition",
                    "current_status": current_status,
                    "requested_status": target_status,
                    "allowed_next_statuses": sorted(allowed),
                }
            ), 409

        if target_status == "ready_to_share" and not _consent_evidence_present(handoff):
            return jsonify({"ok": False, "error": "auditable_user_consent_required_before_ready_to_share"}), 409

        if target_status in {"provider_acknowledged", "in_progress", "completed"}:
            if not _consent_evidence_present(handoff):
                return jsonify({"ok": False, "error": "auditable_user_consent_required"}), 409
            if not _delivery_evidence_present(handoff):
                return jsonify({"ok": False, "error": "handoff_delivery_evidence_required"}), 409

        updates: Dict[str, Any] = {"status": target_status}
        if target_status == "provider_acknowledged":
            updates["provider_acknowledged_at"] = _now_iso()
        elif target_status == "completed":
            updates["completed_at"] = _now_iso()

        response = (
            get_supabase()
            .table("relocation_service_handoffs")
            .update(updates)
            .eq("id", handoff_id)
            .execute()
        )
        updated = (response.data or [handoff | updates])[0]
        _record_handoff_event(
            updated,
            "handoff_status_updated",
            actor_type="admin",
            actor_reference=_text(payload.get("admin_owner"), 180) or "MoveReady admin",
            payload={"from_status": current_status, "to_status": target_status},
        )
        return jsonify({"ok": True, "service_handoff": _public_handoff(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "handoff_update_failed", "details": str(exc)}), 503


@require_admin_access
def safe_update_support_case(case_id: str):
    payload = request.get_json(silent=True) or {}
    target_status = _text(payload.get("status"), 40)
    priority = _text(payload.get("priority"), 40)

    if target_status and target_status not in CASE_STATUSES:
        return jsonify({"ok": False, "error": "invalid_case_status", "allowed_statuses": sorted(CASE_STATUSES)}), 400
    if priority and priority not in CASE_PRIORITIES:
        return jsonify({"ok": False, "error": "invalid_case_priority", "allowed_priorities": sorted(CASE_PRIORITIES)}), 400

    try:
        support_case = _case_by_id(case_id)
        if not support_case:
            return jsonify({"ok": False, "error": "support_case_not_found"}), 404

        updates: Dict[str, Any] = {}
        current_status = str(support_case.get("status") or "open")
        resolution_summary = (
            _text(payload.get("resolution_summary"), 2000)
            if "resolution_summary" in payload
            else _text(support_case.get("resolution_summary"), 2000)
        )

        if target_status:
            if current_status in TERMINAL_CASE_STATUSES and target_status in ACTIVE_CASE_STATUSES:
                updates["resolved_at"] = None
            if target_status in TERMINAL_CASE_STATUSES:
                if not resolution_summary:
                    return jsonify(
                        {
                            "ok": False,
                            "error": "resolution_summary_required_for_terminal_case_status",
                            "requested_status": target_status,
                        }
                    ), 400
                updates["resolved_at"] = _now_iso()
                updates["resolution_summary"] = resolution_summary
            updates["status"] = target_status

        if priority:
            updates["priority"] = priority
        if "assigned_to" in payload:
            updates["assigned_to"] = _text(payload.get("assigned_to"), 180)
        if "resolution_summary" in payload and target_status not in TERMINAL_CASE_STATUSES:
            updates["resolution_summary"] = resolution_summary

        if not updates:
            return jsonify({"ok": False, "error": "no_update_fields"}), 400

        response = (
            get_supabase()
            .table("relocation_support_cases")
            .update(updates)
            .eq("id", case_id)
            .execute()
        )
        updated = (response.data or [support_case | updates])[0]
        public = _public_case(updated) | {
            "email": updated.get("email"),
            "phone": updated.get("phone"),
            "assigned_to": updated.get("assigned_to"),
        }
        return jsonify({"ok": True, "support_case": public})
    except Exception as exc:
        return jsonify({"ok": False, "error": "support_case_update_failed", "details": str(exc)}), 503
