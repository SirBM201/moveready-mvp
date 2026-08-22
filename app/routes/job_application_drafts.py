from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.job_application_drafts import CONTRACT_VERSION, build_application_draft, source_fingerprint
from app.services.job_visibility import job_is_visible_to_account
from app.services.supabase_client import get_supabase

bp = Blueprint("job_application_drafts", __name__)
DRAFT_TABLE = "relocation_job_application_drafts"
READINESS_TABLE = "relocation_job_application_readiness"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _account() -> Tuple[Optional[str], Optional[Tuple[Any, int]]]:
    email = get_verified_session_email()
    return (email, None) if email else (None, (jsonify({"ok": False, "error": "verified_session_required"}), 401))


def _job(job_id: str, email: str) -> Optional[Dict[str, Any]]:
    row = get_supabase().table("relocation_jobs").select("*").eq("id", job_id).maybe_single().execute().data
    return row if job_is_visible_to_account(row, email) else None


def _readiness(job_id: str, email: str) -> Optional[Dict[str, Any]]:
    return get_supabase().table(READINESS_TABLE).select("*").eq("job_id", job_id).eq("email", email).maybe_single().execute().data


def _profile(email: str) -> Dict[str, Any]:
    return get_supabase().table("relocation_job_search_profiles").select("*").eq("email", email).maybe_single().execute().data or {}


def _asset(asset_id: Any, email: str) -> Optional[Dict[str, Any]]:
    if not asset_id:
        return None
    return get_supabase().table("relocation_job_resume_assets").select("id,email,document_type,title,version,is_active,updated_at").eq("id", str(asset_id)).eq("email", email).maybe_single().execute().data


def _materials(readiness: Dict[str, Any], email: str) -> Dict[str, Any]:
    cv = _asset(readiness.get("cv_id"), email)
    cover = _asset(readiness.get("cover_letter_id"), email)
    return {
        "cv_id": readiness.get("cv_id"),
        "cv_valid": bool(cv and cv.get("is_active") and cv.get("document_type") in {"executive_resume", "ats_resume"}),
        "cv": cv,
        "cover_letter_id": readiness.get("cover_letter_id"),
        "cover_letter_valid": bool(cover and cover.get("is_active") and cover.get("document_type") == "cover_letter") if readiness.get("cover_letter_id") else None,
        "cover_letter": cover,
        "application_answers_ready": bool(readiness.get("application_answers_ready")),
    }


def _mark_stale(job_id: str, email: str, current_fingerprint: str) -> int:
    rows = get_supabase().table(DRAFT_TABLE).select("id,source_fingerprint,status").eq("job_id", job_id).eq("email", email).execute().data or []
    count = 0
    for row in rows:
        if row.get("status") in {"draft", "reviewed", "approved"} and row.get("source_fingerprint") != current_fingerprint:
            get_supabase().table(DRAFT_TABLE).update({"status": "stale", "stale_at": _now(), "updated_at": _now()}).eq("id", row["id"]).eq("email", email).execute()
            count += 1
    return count


@bp.post("/jobs/<job_id>/application-drafts")
def generate_draft(job_id: str):
    email, error = _account()
    if error:
        return error
    job = _job(job_id, email)
    if not job:
        return jsonify({"ok": False, "error": "job_not_found"}), 404
    readiness = _readiness(job_id, email)
    if not readiness:
        return jsonify({"ok": False, "error": "readiness_record_required"}), 409
    materials = _materials(readiness, email)
    profile = _profile(email)
    package = build_application_draft(job, profile, materials, readiness=readiness)
    if not package.get("ok"):
        return jsonify(package), 409
    _mark_stale(job_id, email, package["source_fingerprint"])
    row = {
        "email": email,
        "job_id": job_id,
        "readiness_id": readiness.get("id"),
        "status": "draft",
        "contract_version": CONTRACT_VERSION,
        "source_fingerprint": package["source_fingerprint"],
        "tailoring_brief": package["brief"],
        "cv_draft": package["cv_draft"],
        "cover_letter_draft": package["cover_letter_draft"],
        "application_answers": package["application_answers"],
        "safety": package["safety"],
        "updated_at": _now(),
    }
    created = get_supabase().table(DRAFT_TABLE).insert(row).execute().data or []
    return jsonify({"ok": True, "draft": created[0] if created else row}), 201


@bp.get("/jobs/<job_id>/application-drafts")
def list_drafts(job_id: str):
    email, error = _account()
    if error:
        return error
    job = _job(job_id, email)
    if not job:
        return jsonify({"ok": False, "error": "job_not_found"}), 404
    readiness = _readiness(job_id, email) or {}
    current = source_fingerprint(job, _profile(email), _materials(readiness, email))
    stale_count = _mark_stale(job_id, email, current)
    rows = get_supabase().table(DRAFT_TABLE).select("*").eq("job_id", job_id).eq("email", email).order("created_at", desc=True).execute().data or []
    return jsonify({"ok": True, "count": len(rows), "stale_marked": stale_count, "items": rows, "contract_version": CONTRACT_VERSION})


@bp.post("/application-drafts/<draft_id>/review")
def review_draft(draft_id: str):
    email, error = _account()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    action = str(body.get("action") or "reviewed").strip().lower()
    if action not in {"reviewed", "approved"}:
        return jsonify({"ok": False, "error": "invalid_draft_review_action"}), 400
    row = get_supabase().table(DRAFT_TABLE).select("*").eq("id", draft_id).eq("email", email).maybe_single().execute().data
    if not row:
        return jsonify({"ok": False, "error": "draft_not_found"}), 404
    if row.get("status") in {"stale", "superseded"}:
        return jsonify({"ok": False, "error": "stale_draft_cannot_be_approved"}), 409
    now = _now()
    patch = {"status": action, "updated_at": now, "reviewed_at": row.get("reviewed_at") or now}
    if action == "approved":
        patch["approved_at"] = now
    updated = get_supabase().table(DRAFT_TABLE).update(patch).eq("id", draft_id).eq("email", email).execute().data or []
    return jsonify({"ok": True, "draft": updated[0] if updated else {**row, **patch}})
