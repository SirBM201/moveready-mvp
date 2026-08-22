from __future__ import annotations

from typing import Any, Dict, Mapping

CONTRACT_VERSION = "b19.6-v1"
APPROVABLE_DRAFT_STATES = {"reviewed", "approved"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_package_review(draft: Mapping[str, Any], readiness: Mapping[str, Any]) -> Dict[str, Any]:
    draft_status = _text(draft.get("status")).lower()
    readiness_state = _text(readiness.get("state")).lower()
    blockers = []
    if draft_status in {"stale", "superseded"}:
        blockers.append("application_draft_is_stale")
    if readiness_state not in {"ready_for_review", "ready_to_apply", "application_started"}:
        blockers.append("vacancy_readiness_requires_reconciliation")
    if not draft.get("cv_draft"):
        blockers.append("tailored_cv_missing")
    if not draft.get("cover_letter_draft"):
        blockers.append("cover_letter_missing")
    return {
        "ok": not blockers,
        "contract_version": CONTRACT_VERSION,
        "draft_status": draft_status,
        "readiness_state": readiness_state,
        "blockers": blockers,
        "requires_explicit_user_approval": True,
        "auto_submit_allowed": False,
    }


def approve_package(draft: Mapping[str, Any], readiness: Mapping[str, Any], *, user_confirmed: bool) -> Dict[str, Any]:
    review = build_package_review(draft, readiness)
    if not review["ok"]:
        return {**review, "approved": False}
    if not user_confirmed:
        return {**review, "ok": False, "approved": False, "blockers": ["explicit_user_approval_required"]}
    return {
        **review,
        "approved": True,
        "next_state": "approved",
        "handoff_allowed": True,
        "submission_allowed": False,
    }


def build_controlled_handoff(draft: Mapping[str, Any], vacancy: Mapping[str, Any], *, approved: bool) -> Dict[str, Any]:
    if not approved or _text(draft.get("status")).lower() != "approved":
        return {
            "ok": False,
            "error": "approved_application_package_required",
            "contract_version": CONTRACT_VERSION,
        }
    source_url = _text(vacancy.get("source_url") or vacancy.get("application_url") or vacancy.get("url"))
    if not source_url:
        return {
            "ok": False,
            "error": "official_application_destination_required",
            "contract_version": CONTRACT_VERSION,
        }
    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "handoff_type": "user_controlled_external_application",
        "destination_url": source_url,
        "package": {
            "draft_id": draft.get("id"),
            "job_id": draft.get("job_id"),
            "cv_draft": draft.get("cv_draft"),
            "cover_letter_draft": draft.get("cover_letter_draft"),
            "application_answers": draft.get("application_answers"),
        },
        "safety": {
            "user_must_open_destination": True,
            "user_must_review_final_employer_form": True,
            "user_must_trigger_submission": True,
            "credentials_must_not_be_collected_for_auto_submission": True,
            "auto_submit_allowed": False,
        },
    }
