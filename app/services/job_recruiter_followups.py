from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "b19.12.3-v1"
TERMINAL_EVENT_TYPES = {"declined_contact", "relationship_inactive"}


def _day(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def follow_up_status(recruiter: Mapping[str, Any], events: Iterable[Mapping[str, Any]] = (), *, today: date | None = None) -> dict[str, Any]:
    now = today or datetime.now(timezone.utc).date()
    rows = list(events)
    terminal = any(str(row.get("event_type") or "") in TERMINAL_EVENT_TYPES for row in rows)
    due_on = _day(recruiter.get("follow_up_date"))
    due = bool(due_on and due_on <= now and not terminal)
    status = str(recruiter.get("connection_status") or "not_contacted")
    if terminal or status == "inactive":
        action = "none_relationship_inactive"
    elif due:
        action = "review_follow_up"
    elif status == "responded":
        action = "review_response_and_next_step"
    elif status == "not_contacted":
        action = "consider_user_initiated_outreach"
    else:
        action = "monitor_recorded_relationship"
    return {
        "contract_version": CONTRACT_VERSION,
        "due": due,
        "due_on": due_on.isoformat() if due_on else None,
        "recommended_action": action,
        "event_count": len(rows),
        "safety": {
            "automatic_message": False,
            "silence_is_not_rejection": True,
            "response_is_not_offer": True,
            "user_controls_follow_up": True,
        },
    }
