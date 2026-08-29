from __future__ import annotations

from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "b19.8.5-v1"


def _priority(score: int) -> str:
    if score >= 95: return "critical"
    if score >= 80: return "high"
    if score >= 50: return "medium"
    return "low"


def portfolio_action(item: Mapping[str, Any]) -> dict[str, Any] | None:
    action = item.get("next_action") if isinstance(item.get("next_action"), Mapping) else {}
    action_type = str(action.get("type") or "none")
    if action_type == "none": return None
    score = int(item.get("priority_score") or 0)
    deadline = item.get("deadline") if isinstance(item.get("deadline"), Mapping) else {}
    reconciliation = item.get("reconciliation") if isinstance(item.get("reconciliation"), Mapping) else {}
    labels = {
        "complete_followup": "Complete due job follow-up",
        "reconcile_terminal_followups": "Clean up completed application follow-ups",
        "review_stale_vacancy": "Review stale vacancy before continuing",
        "resolve_readiness_gap": "Resolve the next readiness gap",
        "complete_readiness": "Complete application readiness",
        "generate_application_draft": "Prepare vacancy-specific application draft",
        "review_and_prepare_handoff": "Review application materials for handoff",
        "submit_manually_and_confirm": "Submit application manually and confirm",
        "wait_for_followup": "Review scheduled follow-up",
        "schedule_followup": "Schedule the next application follow-up",
        "review_application": "Review application status",
    }
    title = str(item.get("title") or "Job application")
    company = str(item.get("company") or "").strip()
    summary = f"{labels.get(action_type, 'Review application action')} for {title}"
    if company: summary += f" at {company}"
    summary += "."
    if deadline.get("level") in {"overdue", "critical", "urgent"}:
        summary += f" Timing is {deadline.get('level')}."
    if reconciliation.get("requires_write_reconciliation"):
        summary += " Portfolio reconciliation is required."
    return {
        "kind": "job_application_portfolio",
        "id": item.get("job_id"),
        "job_id": item.get("job_id"),
        "title": labels.get(action_type, "Review job application"),
        "summary": summary,
        "priority": _priority(score),
        "score": score,
        "href": action.get("href") or f"/jobs/execution?jobId={item.get('job_id')}",
        "status": item.get("pipeline_state"),
        "due_at": deadline.get("at"),
        "hours_until_due": deadline.get("hours_remaining"),
        "metadata": {"action_type": action_type, "gap_code": action.get("gap_code"), "blocking": bool(action.get("blocking")), "deadline_level": deadline.get("level"), "reconciliation_required": bool(reconciliation.get("requires_write_reconciliation"))},
        "source": "b19.8_application_portfolio",
    }


def build_portfolio_action_feed(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    actions = [action for item in items if (action := portfolio_action(item)) is not None]
    return sorted(actions, key=lambda row: (-int(row.get("score") or 0), float(row.get("hours_until_due")) if row.get("hours_until_due") is not None else 999999, str(row.get("job_id") or "")))


def what_should_i_do_next(items: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    actions = build_portfolio_action_feed(items)
    if not actions: return None
    return {**actions[0], "reason": "Highest-ranked application action across your active job portfolio", "contract_version": CONTRACT_VERSION}
