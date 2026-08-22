from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from app.services.job_application_lifecycle import CONTRACT_VERSION, EMPLOYER_EVIDENCE_STATES, TERMINAL_STATES, normalize_state, transition_application_lifecycle

RECONCILIATION_VERSION = "b19.7.3-v1"
EVIDENCE_TYPES = {"email", "employer_portal", "recruiter_message", "assessment_invite", "interview_invite", "offer_document", "rejection_notice", "user_recorded"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def validate_employer_evidence(target_state: str, evidence: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    target = normalize_state(target_state)
    payload = dict(evidence or {})
    if target not in EMPLOYER_EVIDENCE_STATES:
        return {"ok": True, "evidence": payload, "required": False}
    evidence_type = normalize_state(payload.get("type"))
    summary = _text(payload.get("summary"))
    observed_at = _text(payload.get("observed_at"))
    if evidence_type not in EVIDENCE_TYPES:
        return {"ok": False, "error": "invalid_employer_evidence_type", "allowed_types": sorted(EVIDENCE_TYPES)}
    if not summary:
        return {"ok": False, "error": "employer_evidence_summary_required"}
    if not observed_at:
        return {"ok": False, "error": "employer_evidence_observed_at_required"}
    payload["type"] = evidence_type
    payload["summary"] = summary
    payload["observed_at"] = observed_at
    return {"ok": True, "evidence": payload, "required": True}


def reconcile_lifecycle_state(lifecycle: Mapping[str, Any], *, target_state: str, employer_evidence: Optional[Mapping[str, Any]] = None, user_confirmed: bool = False) -> Dict[str, Any]:
    current = normalize_state(lifecycle.get("state"))
    target = normalize_state(target_state)
    if current in TERMINAL_STATES:
        return {"ok": False, "error": "application_lifecycle_is_terminal", "state": current, "contract_version": CONTRACT_VERSION, "reconciliation_version": RECONCILIATION_VERSION}
    evidence_result = validate_employer_evidence(target, employer_evidence)
    if not evidence_result["ok"]:
        return {**evidence_result, "state": current, "target_state": target, "contract_version": CONTRACT_VERSION, "reconciliation_version": RECONCILIATION_VERSION}
    transition = transition_application_lifecycle(current, target, employer_evidence=evidence_result["evidence"], user_confirmed=user_confirmed)
    transition["reconciliation_version"] = RECONCILIATION_VERSION
    if not transition["ok"]:
        return transition
    transition["integrity"] = {
        "evidence_validated": bool(evidence_result["required"]),
        "terminal_state_locked": target in TERMINAL_STATES,
        "autonomous_employer_status_detection": False,
        "status_claim_is_evidence_bound": target in EMPLOYER_EVIDENCE_STATES,
    }
    return transition


def build_reconciliation_event(result: Mapping[str, Any], evidence: Mapping[str, Any], *, source: str = "verified_account") -> Dict[str, Any]:
    return {
        "previous_state": result.get("previous_state"),
        "state": result.get("state"),
        "evidence": dict(evidence or {}),
        "metadata": {
            "source": source,
            "reconciliation_version": RECONCILIATION_VERSION,
            "evidence_validated": bool((result.get("integrity") or {}).get("evidence_validated")),
            "autonomous_employer_status_detection": False,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
