from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.job_visibility import job_is_visible_to_account
from app.services.supabase_client import get_supabase

bp = Blueprint("job_application_handoffs", __name__)
HANDOFF_TABLE = "relocation_job_application_handoffs"
EVENT_TABLE = "relocation_job_application_handoff_events"
DRAFT_TABLE = "relocation_job_application_drafts"
CONTRACT_VERSION = "b19.6-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _account() -> Tuple[Optional[str], Optional[Tuple[Any, int]]]:
    email = get_verified_session_email()
    return (email, None) if email else (None, (jsonify({"ok": False, "error": "verified_session_required"}), 401))


def _job(job_id: str, email: str) -> Optional[Dict[str, Any]]:
    row = get_supabase().table("relocation_jobs").select("*").eq("id", job_id).maybe_single().execute().data
    return row if job_is_visible_to_account(row, email) else None


def _event(handoff_id: str, email: str, event_type: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    get_supabase().table(EVENT_TABLE).insert({
        "handoff_id": handoff_id,
        "email": email,
        "event_type": event_type,
        "metadata": metadata or {},
    }).execute()


@bp.post("/application-drafts/<draft_id>/handoff")
def prepare_handoff(draft_id: str):
    email, error = _account()
    if error:
        return error
    draft = get_supabase().table(DRAFT_TABLE).select("*").eq("id", draft_id).eq("email", email).maybe_single().execute().data
    if not draft:
        return jsonify({"ok": False, "error": "draft_not_found"}), 404
    if draft.get("status") != "approved":
        return jsonify({"ok": False, "error": "approved_draft_required"}), 409
    job = _job(str(draft.get("job_id")), email)
    if not job:
        return jsonify({"ok": False, "error": "job_not_found"}), 404
    existing = get_supabase().table(HANDOFF_TABLE).select("*").eq("draft_id", draft_id).eq("email", email).maybe_single().execute().data
    if existing:
        return jsonify({"ok": True, "handoff": existing, "created": False, "contract_version": CONTRACT_VERSION})
    destination_url = job.get("application_url") or job.get("source_url") or job.get("url")
    snapshot = {
        "draft_id": draft_id,
        "job_id": draft.get("job_id"),
        "source_fingerprint": draft.get("source_fingerprint"),
        "cv_draft": draft.get("cv_draft") or {},
        "cover_letter_draft": draft.get("cover_letter_draft") or {},
        "application_answers": draft.get("application_answers") or {},
    }
    safety = {
        "autonomous_submission": False,
        "user_action_required": True,
        "destination_is_external": bool(destination_url),
        "notice": "MoveReady prepares the approved package only. The user controls and completes any employer submission.",
    }
    rows = get_supabase().table(HANDOFF_TABLE).insert({
        "email": email,
        "job_id": draft.get("job_id"),
        "draft_id": draft_id,
        "status": "prepared",
        "contract_version": CONTRACT_VERSION,
        "destination_url": destination_url,
        "package_snapshot": snapshot,
        "safety": safety,
        "updated_at": _now(),
    }).execute().data or []
    handoff = rows[0] if rows else None
    if not handoff:
        return jsonify({"ok": False, "error": "handoff_create_failed"}), 500
    _event(handoff["id"], email, "prepared", {"destination_available": bool(destination_url)})
    return jsonify({"ok": True, "handoff": handoff, "created": True, "contract_version": CONTRACT_VERSION}), 201


@bp.get("/jobs/<job_id>/application-handoffs")
def list_handoffs(job_id: str):
    email, error = _account()
    if error:
        return error
    if not _job(job_id, email):
        return jsonify({"ok": False, "error": "job_not_found"}), 404
    rows = get_supabase().table(HANDOFF_TABLE).select("*").eq("job_id", job_id).eq("email", email).order("created_at", desc=True).execute().data or []
    return jsonify({"ok": True, "count": len(rows), "items": rows, "contract_version": CONTRACT_VERSION})


@bp.get("/application-handoffs/<handoff_id>")
def get_handoff(handoff_id: str):
    email, error = _account()
    if error:
        return error
    row = get_supabase().table(HANDOFF_TABLE).select("*").eq("id", handoff_id).eq("email", email).maybe_single().execute().data
    if not row:
        return jsonify({"ok": False, "error": "handoff_not_found"}), 404
    events = get_supabase().table(EVENT_TABLE).select("*").eq("handoff_id", handoff_id).eq("email", email).order("created_at").execute().data or []
    return jsonify({"ok": True, "handoff": row, "events": events, "contract_version": CONTRACT_VERSION})


@bp.post("/application-handoffs/<handoff_id>/status")
def update_handoff_status(handoff_id: str):
    email, error = _account()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    action = str(body.get("action") or "").strip().lower()
    if action not in {"opened", "submitted_manual", "withdrawn"}:
        return jsonify({"ok": False, "error": "invalid_handoff_action"}), 400
    row = get_supabase().table(HANDOFF_TABLE).select("*").eq("id", handoff_id).eq("email", email).maybe_single().execute().data
    if not row:
        return jsonify({"ok": False, "error": "handoff_not_found"}), 404
    if row.get("status") == "withdrawn":
        return jsonify({"ok": False, "error": "withdrawn_handoff_is_terminal"}), 409
    if action == "submitted_manual" and row.get("status") not in {"prepared", "opened"}:
        return jsonify({"ok": False, "error": "invalid_handoff_transition"}), 409
    now = _now()
    patch: Dict[str, Any] = {"status": action, "updated_at": now}
    if action == "opened":
        patch["opened_at"] = row.get("opened_at") or now
    elif action == "submitted_manual":
        patch["submitted_manual_at"] = now
    elif action == "withdrawn":
        patch["withdrawn_at"] = now
    updated = get_supabase().table(HANDOFF_TABLE).update(patch).eq("id", handoff_id).eq("email", email).execute().data or []
    _event(handoff_id, email, action, {"user_confirmed": True})
    return jsonify({"ok": True, "handoff": updated[0] if updated else {**row, **patch}, "contract_version": CONTRACT_VERSION})
