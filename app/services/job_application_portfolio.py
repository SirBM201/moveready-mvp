from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "b19.8.1-v1"
TERMINAL_STATES = frozenset({"hired", "rejected", "withdrawn"})
ACTIVE_FOLLOWUP_STATES = frozenset({"scheduled", "due"})


def _iso(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _parse(value: Any) -> datetime | None:
    text = _iso(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest(rows: Iterable[Mapping[str, Any]], *keys: str) -> Mapping[str, Any] | None:
    items = list(rows)
    if not items:
        return None
    def score(row: Mapping[str, Any]) -> datetime:
        for key in keys:
            parsed = _parse(row.get(key))
            if parsed:
                return parsed
        return datetime.min.replace(tzinfo=timezone.utc)
    return max(items, key=score)


def _readiness_state(row: Mapping[str, Any] | None) -> str:
    return str((row or {}).get("state") or (row or {}).get("readiness_state") or "not_started")


def _lifecycle_state(row: Mapping[str, Any] | None) -> str | None:
    value = str((row or {}).get("state") or "").strip()
    return value or None


def pipeline_state(*, readiness: Mapping[str, Any] | None, draft: Mapping[str, Any] | None,
                   handoff: Mapping[str, Any] | None, lifecycle: Mapping[str, Any] | None) -> str:
    lifecycle_value = _lifecycle_state(lifecycle)
    if lifecycle_value:
        return lifecycle_value
    if handoff:
        status = str(handoff.get("status") or "").strip().lower()
        if status in {"submitted", "submitted_manual", "confirmed_submitted"} or handoff.get("submitted_manual_at"):
            return "submitted"
        return "handoff_ready"
    if draft:
        return "draft_ready"
    readiness_value = _readiness_state(readiness)
    if readiness_value in {"ready", "application_ready", "ready_to_apply"}:
        return "ready_to_apply"
    return "preparing"


def next_action(*, pipeline: str, readiness: Mapping[str, Any] | None,
                followups: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    active = [row for row in followups if str(row.get("status") or "") in ACTIVE_FOLLOWUP_STATES]
    due = [row for row in active if str(row.get("status") or "") == "due"]
    if due:
        row = _latest(due, "scheduled_for", "updated_at") or due[0]
        return {"type": "complete_followup", "urgency": "due", "followup_id": row.get("id"), "scheduled_for": row.get("scheduled_for")}
    scheduled = _latest(active, "scheduled_for", "updated_at") if active else None
    if pipeline in TERMINAL_STATES:
        return {"type": "none", "urgency": "none"}
    if scheduled:
        return {"type": "wait_for_followup", "urgency": "scheduled", "followup_id": scheduled.get("id"), "scheduled_for": scheduled.get("scheduled_for")}
    if pipeline == "preparing":
        return {"type": "complete_readiness", "urgency": "normal", "readiness_state": _readiness_state(readiness)}
    if pipeline == "ready_to_apply":
        return {"type": "generate_application_draft", "urgency": "normal"}
    if pipeline == "draft_ready":
        return {"type": "review_and_prepare_handoff", "urgency": "normal"}
    if pipeline == "handoff_ready":
        return {"type": "submit_manually_and_confirm", "urgency": "high"}
    if pipeline in {"submitted", "under_review", "interview", "offer"}:
        return {"type": "schedule_followup", "urgency": "normal"}
    return {"type": "review_application", "urgency": "normal"}


def priority_score(*, pipeline: str, action: Mapping[str, Any], vacancy: Mapping[str, Any] | None = None) -> int:
    if pipeline in TERMINAL_STATES:
        return 0
    urgency = str(action.get("urgency") or "normal")
    score = {"due": 100, "high": 80, "normal": 50, "scheduled": 25, "none": 0}.get(urgency, 50)
    if pipeline == "offer":
        score = max(score, 90)
    elif pipeline == "interview":
        score = max(score, 85)
    elif pipeline == "handoff_ready":
        score = max(score, 80)
    if vacancy and vacancy.get("is_stale"):
        score = min(score, 20)
    return score


def build_portfolio_item(*, job: Mapping[str, Any], readiness: Mapping[str, Any] | None = None,
                         drafts: Iterable[Mapping[str, Any]] = (), handoffs: Iterable[Mapping[str, Any]] = (),
                         lifecycles: Iterable[Mapping[str, Any]] = (), followups: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    job_id = job.get("id") or job.get("job_id")
    draft = _latest(drafts, "updated_at", "created_at")
    handoff = _latest(handoffs, "updated_at", "created_at")
    lifecycle = _latest(lifecycles, "state_changed_at", "updated_at", "created_at")
    owned_followups = list(followups)
    state = pipeline_state(readiness=readiness, draft=draft, handoff=handoff, lifecycle=lifecycle)
    action = next_action(pipeline=state, readiness=readiness, followups=owned_followups)
    return {
        "contract_version": CONTRACT_VERSION,
        "job_id": job_id,
        "title": job.get("title"),
        "company": job.get("company") or job.get("company_name"),
        "location": job.get("location"),
        "pipeline_state": state,
        "terminal": state in TERMINAL_STATES,
        "readiness_state": _readiness_state(readiness),
        "draft_id": (draft or {}).get("id"),
        "handoff_id": (handoff or {}).get("id"),
        "lifecycle_id": (lifecycle or {}).get("id"),
        "next_action": action,
        "priority_score": priority_score(pipeline=state, action=action, vacancy=job),
        "active_followup_count": sum(1 for row in owned_followups if str(row.get("status") or "") in ACTIVE_FOLLOWUP_STATES),
        "due_followup_count": sum(1 for row in owned_followups if str(row.get("status") or "") == "due"),
        "safety": {"read_model_only": True, "auto_submit_allowed": False, "auto_contact_employer": False},
    }


def sort_portfolio(items: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(items, key=lambda row: (-int(row.get("priority_score") or 0), str(row.get("title") or "").lower()))
