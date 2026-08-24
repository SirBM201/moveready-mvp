from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "b19.8.3-v1"
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


def deadline_intelligence(*, job: Mapping[str, Any], followups: Iterable[Mapping[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    candidates: list[tuple[str, datetime, str | None]] = []
    for key in ("application_deadline", "deadline", "closing_at", "expires_at"):
        parsed = _parse(job.get(key))
        if parsed:
            candidates.append(("vacancy_deadline", parsed, None)); break
    for row in followups:
        if str(row.get("status") or "") not in ACTIVE_FOLLOWUP_STATES:
            continue
        parsed = _parse(row.get("scheduled_for"))
        if parsed:
            candidates.append(("followup", parsed, str(row.get("id") or "") or None))
    if not candidates:
        return {"level": "none", "hours_remaining": None, "source": None, "at": None, "followup_id": None}
    source, target, followup_id = min(candidates, key=lambda item: item[1])
    hours = (target - now).total_seconds() / 3600
    if hours < 0:
        level = "overdue"
    elif hours <= 24:
        level = "critical"
    elif hours <= 72:
        level = "urgent"
    elif hours <= 168:
        level = "soon"
    else:
        level = "normal"
    return {"level": level, "hours_remaining": round(hours, 1), "source": source, "at": target.isoformat(), "followup_id": followup_id}


def reconcile_portfolio_state(*, pipeline: str, job: Mapping[str, Any], followups: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    active = [row for row in followups if str(row.get("status") or "") in ACTIVE_FOLLOWUP_STATES]
    if pipeline in TERMINAL_STATES and active:
        issues.append("terminal_application_has_active_followups")
    if job.get("is_stale") and pipeline in {"preparing", "ready_to_apply", "draft_ready", "handoff_ready"}:
        issues.append("pre_submission_vacancy_is_stale")
    return {"consistent": not issues, "issues": issues, "requires_write_reconciliation": bool(issues), "write_performed": False}


def next_action(*, pipeline: str, readiness: Mapping[str, Any] | None,
                followups: Iterable[Mapping[str, Any]], deadline: Mapping[str, Any] | None = None,
                reconciliation: Mapping[str, Any] | None = None) -> dict[str, Any]:
    active = [row for row in followups if str(row.get("status") or "") in ACTIVE_FOLLOWUP_STATES]
    due = [row for row in active if str(row.get("status") or "") == "due"]
    if pipeline in TERMINAL_STATES:
        if reconciliation and reconciliation.get("requires_write_reconciliation"):
            return {"type": "reconcile_terminal_followups", "urgency": "high"}
        return {"type": "none", "urgency": "none"}
    if due:
        row = _latest(due, "scheduled_for", "updated_at") or due[0]
        return {"type": "complete_followup", "urgency": "due", "followup_id": row.get("id"), "scheduled_for": row.get("scheduled_for")}
    if reconciliation and "pre_submission_vacancy_is_stale" in reconciliation.get("issues", []):
        return {"type": "review_stale_vacancy", "urgency": "high"}
    scheduled = _latest(active, "scheduled_for", "updated_at") if active else None
    if scheduled:
        return {"type": "wait_for_followup", "urgency": "scheduled", "followup_id": scheduled.get("id"), "scheduled_for": scheduled.get("scheduled_for")}
    deadline_level = str((deadline or {}).get("level") or "none")
    urgency = "high" if deadline_level in {"overdue", "critical", "urgent"} else "normal"
    if pipeline == "preparing":
        return {"type": "complete_readiness", "urgency": urgency, "readiness_state": _readiness_state(readiness)}
    if pipeline == "ready_to_apply":
        return {"type": "generate_application_draft", "urgency": urgency}
    if pipeline == "draft_ready":
        return {"type": "review_and_prepare_handoff", "urgency": urgency}
    if pipeline == "handoff_ready":
        return {"type": "submit_manually_and_confirm", "urgency": "high"}
    if pipeline in {"submitted", "under_review", "interview", "offer"}:
        return {"type": "schedule_followup", "urgency": urgency}
    return {"type": "review_application", "urgency": urgency}


def priority_score(*, pipeline: str, action: Mapping[str, Any], vacancy: Mapping[str, Any] | None = None,
                   deadline: Mapping[str, Any] | None = None) -> int:
    if pipeline in TERMINAL_STATES and action.get("type") == "none":
        return 0
    urgency = str(action.get("urgency") or "normal")
    score = {"due": 100, "high": 80, "normal": 50, "scheduled": 25, "none": 0}.get(urgency, 50)
    deadline_level = str((deadline or {}).get("level") or "none")
    score = max(score, {"overdue": 100, "critical": 95, "urgent": 85, "soon": 65}.get(deadline_level, 0))
    if pipeline == "offer": score = max(score, 90)
    elif pipeline == "interview": score = max(score, 85)
    elif pipeline == "handoff_ready": score = max(score, 80)
    if vacancy and vacancy.get("is_stale") and pipeline not in {"submitted", "under_review", "interview", "offer"}:
        score = min(score, 80 if action.get("type") == "review_stale_vacancy" else 20)
    return score


def build_portfolio_item(*, job: Mapping[str, Any], readiness: Mapping[str, Any] | None = None,
                         drafts: Iterable[Mapping[str, Any]] = (), handoffs: Iterable[Mapping[str, Any]] = (),
                         lifecycles: Iterable[Mapping[str, Any]] = (), followups: Iterable[Mapping[str, Any]] = (),
                         now: datetime | None = None) -> dict[str, Any]:
    job_id = job.get("id") or job.get("job_id")
    draft = _latest(drafts, "updated_at", "created_at")
    handoff = _latest(handoffs, "updated_at", "created_at")
    lifecycle = _latest(lifecycles, "state_changed_at", "updated_at", "created_at")
    owned_followups = list(followups)
    state = pipeline_state(readiness=readiness, draft=draft, handoff=handoff, lifecycle=lifecycle)
    deadline = deadline_intelligence(job=job, followups=owned_followups, now=now)
    reconciliation = reconcile_portfolio_state(pipeline=state, job=job, followups=owned_followups)
    action = next_action(pipeline=state, readiness=readiness, followups=owned_followups, deadline=deadline, reconciliation=reconciliation)
    return {
        "contract_version": CONTRACT_VERSION, "job_id": job_id, "title": job.get("title"),
        "company": job.get("company") or job.get("company_name"), "location": job.get("location"),
        "pipeline_state": state, "terminal": state in TERMINAL_STATES, "readiness_state": _readiness_state(readiness),
        "draft_id": (draft or {}).get("id"), "handoff_id": (handoff or {}).get("id"), "lifecycle_id": (lifecycle or {}).get("id"),
        "deadline": deadline, "reconciliation": reconciliation, "next_action": action,
        "priority_score": priority_score(pipeline=state, action=action, vacancy=job, deadline=deadline),
        "active_followup_count": sum(1 for row in owned_followups if str(row.get("status") or "") in ACTIVE_FOLLOWUP_STATES),
        "due_followup_count": sum(1 for row in owned_followups if str(row.get("status") or "") == "due"),
        "safety": {"read_model_only": True, "auto_submit_allowed": False, "auto_contact_employer": False, "reconciliation_writes_performed": False},
    }


def sort_portfolio(items: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(items, key=lambda row: (-int(row.get("priority_score") or 0), str(row.get("title") or "").lower()))
