from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Blueprint, jsonify

from app.services.account_identity import get_verified_session_email
from app.services.supabase_client import get_supabase

bp = Blueprint("account_outcomes", __name__)


def _rows(table: str, email: str, owner: str = "email", limit: int = 500) -> List[Dict[str, Any]]:
    try:
        return (get_supabase().table(table).select("*").eq(owner, email).order("created_at", desc=True).limit(limit).execute().data or [])
    except Exception:
        return []


def _counts(rows: List[Dict[str, Any]], field: str) -> Dict[str, int]:
    return dict(Counter(str(row.get(field) or "unknown").lower() for row in rows))


def _pct(part: int, whole: int) -> float:
    return round((part / whole) * 100, 1) if whole else 0.0


@bp.get("/outcomes")
def outcomes():
    email = get_verified_session_email()
    if not email:
        return jsonify({"ok": False, "error": "verified_session_required"}), 401

    applications = _rows("relocation_application_cases", email)
    jobs = _rows("relocation_job_applications", email)
    documents = _rows("relocation_user_document_inventory", email)
    evidence = _rows("relocation_evidence_packs", email)
    timeline = _rows("relocation_timeline_events", email)
    handoffs = _rows("relocation_service_handoffs", email)

    app_stage = _counts(applications, "application_stage")
    job_status = _counts(jobs, "status")
    doc_status = _counts(documents, "status")
    evidence_status = _counts(evidence, "status")
    timeline_status = _counts(timeline, "status")

    app_decisions = sum(app_stage.get(key, 0) for key in ("approved", "refused", "withdrawn", "decision_received"))
    approvals = app_stage.get("approved", 0)
    job_positive = sum(job_status.get(key, 0) for key in ("interview", "offer", "hired", "accepted"))
    docs_ready = sum(doc_status.get(key, 0) for key in ("available", "ready", "verified"))
    evidence_ready = sum(evidence_status.get(key, 0) for key in ("ready", "submitted"))
    tasks_done = sum(timeline_status.get(key, 0) for key in ("done", "completed"))

    return jsonify({
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {"application_cases": len(applications), "job_applications": len(jobs), "documents": len(documents), "evidence_packs": len(evidence), "timeline_tasks": len(timeline), "service_handoffs": len(handoffs)},
        "rates": {"application_approval_rate": _pct(approvals, app_decisions), "job_positive_progress_rate": _pct(job_positive, len(jobs)), "document_ready_rate": _pct(docs_ready, len(documents)), "evidence_ready_rate": _pct(evidence_ready, len(evidence)), "timeline_completion_rate": _pct(tasks_done, len(timeline))},
        "breakdowns": {"application_stage": app_stage, "job_status": job_status, "document_status": doc_status, "evidence_status": evidence_status, "timeline_status": timeline_status},
        "interpretation": {
            "application_rate_basis": f"{approvals} approved outcome(s) across {app_decisions} recorded decision-stage case(s).",
            "job_rate_basis": f"{job_positive} job application(s) reached interview/offer/hired/accepted status across {len(jobs)} tracked applications.",
            "data_quality": "Rates use only statuses recorded in your MoveReady account. Missing or stale status updates can change the result."
        },
        "safety_note": "These are private progress analytics, not predictions of visa, admission, employment, permanent residence, citizenship, border entry, provider performance, or future success."
    })
