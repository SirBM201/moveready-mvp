from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional

from app.services.job_application_followup import TERMINAL_LIFECYCLE_STATES, normalize, record_outcome
from app.services.job_application_lifecycle_reconciliation import reconcile_lifecycle_state

CONTRACT_VERSION = "b19.7.5-v1"
ACTIVE_STATUSES = {"scheduled", "due"}
OUTCOME_TO_STATE = {
    "acknowledged": "acknowledged", "under_review": "under_review", "assessment": "assessment",
    "interview": "interview", "offer": "offer", "hired": "hired", "rejected": "rejected",
    "withdrawn": "withdrawn", "closed": "closed",
}


def _dt(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def reconcile_due_status(followup: Mapping[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    current = normalize(followup.get("status"))
    if current not in ACTIVE_STATUSES:
        return {"ok": True, "changed": False, "status": current, "contract_version": CONTRACT_VERSION}
    due = _dt(followup.get("scheduled_for"))
    if due is None:
        return {"ok": False, "error": "valid_followup_schedule_required", "contract_version": CONTRACT_VERSION}
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    target = "due" if due <= clock else "scheduled"
    return {"ok": True, "changed": target != current, "status": target, "contract_version": CONTRACT_VERSION}


def active_duplicate(existing: Iterable[Mapping[str, Any]], *, lifecycle_id: str, action_type: str, exclude_id: Optional[str] = None) -> bool:
    action = normalize(action_type)
    for row in existing:
        if str(row.get("id") or "") == str(exclude_id or ""):
            continue
        if str(row.get("lifecycle_id") or "") == str(lifecycle_id) and normalize(row.get("action_type")) == action and normalize(row.get("status")) in ACTIVE_STATUSES:
            return True
    return False


def terminal_followup_updates(followups: Iterable[Mapping[str, Any]], lifecycle_state: str) -> Dict[str, str]:
    if normalize(lifecycle_state) not in TERMINAL_LIFECYCLE_STATES:
        return {}
    return {str(row["id"]): "superseded" for row in followups if row.get("id") and normalize(row.get("status")) in ACTIVE_STATUSES}


def reconcile_outcome(lifecycle: Mapping[str, Any], outcome: str, *, evidence: Optional[Mapping[str, Any]] = None, user_confirmed: bool = False) -> Dict[str, Any]:
    recorded = record_outcome(outcome, evidence=evidence)
    if not recorded["ok"]:
        return {**recorded, "contract_version": CONTRACT_VERSION}
    normalized = normalize(recorded["outcome"])
    target = OUTCOME_TO_STATE.get(normalized)
    if not target:
        return {"ok": True, "lifecycle_changed": False, "outcome": normalized, "contract_version": CONTRACT_VERSION}
    transition = reconcile_lifecycle_state(lifecycle, target_state=target, employer_evidence=evidence, user_confirmed=user_confirmed)
    return {"ok": bool(transition.get("ok")), "lifecycle_changed": bool(transition.get("ok")), "outcome": normalized, "transition": transition, "contract_version": CONTRACT_VERSION}
