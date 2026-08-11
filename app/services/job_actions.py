from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional


ACTION_WINDOW_DAYS = 14


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _priority(days_until_due: int) -> str:
    if days_until_due <= 0:
        return "critical"
    if days_until_due <= 3:
        return "high"
    return "medium"


def _score(days_until_due: int) -> int:
    if days_until_due < 0:
        return 140 + min(abs(days_until_due), 30)
    if days_until_due == 0:
        return 130
    if days_until_due <= 3:
        return 105 - days_until_due
    return 75 - min(days_until_due, ACTION_WINDOW_DAYS)


def _within_action_window(value: Any, today: date) -> tuple[Optional[date], Optional[int]]:
    due_date = _parse_date(value)
    if not due_date:
        return None, None
    days_until_due = (due_date - today).days
    if days_until_due > ACTION_WINDOW_DAYS:
        return due_date, None
    return due_date, days_until_due


def build_job_actions(
    applications: Iterable[Dict[str, Any]],
    recruiters: Iterable[Dict[str, Any]],
    *,
    today: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Build a read-only priority queue from existing private Jobs records."""

    current_date = today or date.today()
    actions: List[Dict[str, Any]] = []

    for row in applications:
        status = str(row.get("status") or "saved")
        if status == "rejected":
            continue
        due_date, days_until_due = _within_action_window(row.get("follow_up_date"), current_date)
        if due_date is None or days_until_due is None:
            continue
        company = str(row.get("company_name") or "the employer").strip()
        title = str(row.get("job_title") or "Job application").strip()
        actions.append({
            "kind": "job_application_follow_up",
            "id": row.get("id"),
            "title": title,
            "summary": f"Follow up with {company} and record the outcome in Applications.",
            "priority": _priority(days_until_due),
            "status": status,
            "due_at": due_date.isoformat(),
            "days_until_due": days_until_due,
            "score": _score(days_until_due),
            "href": "/jobs/applications",
            "created_at": row.get("created_at"),
            "metadata": {"company_name": company},
        })

    for row in recruiters:
        status = str(row.get("connection_status") or "not_contacted")
        if status == "inactive":
            continue
        due_date, days_until_due = _within_action_window(row.get("follow_up_date"), current_date)
        if due_date is None or days_until_due is None:
            continue
        recruiter_name = str(row.get("recruiter_name") or "Recruiter").strip()
        organization = str(row.get("recruitment_company") or "the recruiter contact").strip()
        actions.append({
            "kind": "job_recruiter_follow_up",
            "id": row.get("id"),
            "title": recruiter_name,
            "summary": f"Follow up with {recruiter_name} at {organization} and record the response.",
            "priority": _priority(days_until_due),
            "status": status,
            "due_at": due_date.isoformat(),
            "days_until_due": days_until_due,
            "score": _score(days_until_due),
            "href": "/jobs/recruiters",
            "created_at": row.get("created_at"),
            "metadata": {"recruitment_company": row.get("recruitment_company")},
        })

    actions.sort(
        key=lambda item: (
            int(item.get("score") or 0),
            str(item.get("due_at") or ""),
            str(item.get("created_at") or ""),
        ),
        reverse=True,
    )
    return actions


def count_job_actions(actions: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"overdue": 0, "due_today": 0, "upcoming": 0, "total": 0}
    for item in actions:
        days_until_due = int(item.get("days_until_due") or 0)
        counts["total"] += 1
        if days_until_due < 0:
            counts["overdue"] += 1
        elif days_until_due == 0:
            counts["due_today"] += 1
        else:
            counts["upcoming"] += 1
    return counts
