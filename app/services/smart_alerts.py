from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


CONTRACT_VERSION = "b14-v1"
PRIORITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

SMART_ALERT_DEFAULTS: Dict[str, Any] = {
    "jobs_enabled": True,
    "application_followups_enabled": True,
    "language_reminders_enabled": False,
    "evidence_refresh_enabled": True,
    "critical_only": False,
    "document_expiry_lead_days": 180,
    "language_inactive_days": 7,
    "evidence_refresh_days": 30,
}

BOOLEAN_FIELDS = {
    "jobs_enabled",
    "application_followups_enabled",
    "language_reminders_enabled",
    "evidence_refresh_enabled",
    "critical_only",
}

INTEGER_RANGES = {
    "document_expiry_lead_days": (30, 365),
    "language_inactive_days": (1, 30),
    "evidence_refresh_days": (7, 180),
}


class SmartAlertPreferenceError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_preferences(value: Any) -> Dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    result = dict(SMART_ALERT_DEFAULTS)
    for field in BOOLEAN_FIELDS:
        if field in source:
            result[field] = _bool(source.get(field))
    for field, (minimum, maximum) in INTEGER_RANGES.items():
        try:
            number = int(source.get(field, result[field]))
        except (TypeError, ValueError):
            number = int(result[field])
        result[field] = max(minimum, min(number, maximum))
    return result


def preferences_from_payload(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise SmartAlertPreferenceError("smart_alert_preferences_must_be_an_object")
    unsupported = sorted(set(value) - BOOLEAN_FIELDS - set(INTEGER_RANGES))
    if unsupported:
        raise SmartAlertPreferenceError("unsupported_smart_alert_preference")
    for field, (minimum, maximum) in INTEGER_RANGES.items():
        if field not in value:
            continue
        try:
            number = int(value[field])
        except (TypeError, ValueError) as exc:
            raise SmartAlertPreferenceError(f"invalid_{field}") from exc
        if number < minimum or number > maximum:
            raise SmartAlertPreferenceError(f"{field}_out_of_range")
    return normalize_preferences(value)


def parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def stable_key(category: str, source: str, record_id: Any, marker: Any) -> str:
    raw = "|".join(str(item or "") for item in (category, source, record_id, marker))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def alert(
    *,
    category: str,
    source: str,
    record_id: Any,
    marker: Any,
    priority: str,
    title: str,
    summary: str,
    href: str,
    due_at: Any = None,
    detected_at: Any = None,
    official_url: Any = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    safe_priority = priority if priority in PRIORITY_RANK else "medium"
    return {
        "key": stable_key(category, source, record_id, marker),
        "category": category,
        "source": source,
        "priority": safe_priority,
        "title": str(title or "Review alert")[:180],
        "summary": str(summary or "Open the underlying workspace and verify the current record.")[:700],
        "href": href,
        "due_at": due_at,
        "detected_at": detected_at,
        "official_url": official_url,
        "metadata": metadata or {},
    }


def dedupe_and_rank(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("key") or "")
        if not key:
            continue
        current = deduped.get(key)
        if not current:
            deduped[key] = row
            continue
        candidate_rank = PRIORITY_RANK.get(str(row.get("priority") or "medium"), 2)
        current_rank = PRIORITY_RANK.get(str(current.get("priority") or "medium"), 2)
        if candidate_rank > current_rank:
            deduped[key] = row
            continue
        if candidate_rank == current_rank and str(row.get("detected_at") or "") > str(current.get("detected_at") or ""):
            deduped[key] = row

    def sort_key(item: Dict[str, Any]) -> Any:
        priority = PRIORITY_RANK.get(str(item.get("priority") or "medium"), 2)
        due = parse_datetime(item.get("due_at"))
        detected = parse_datetime(item.get("detected_at"))
        # Higher priority first, then the nearest deadline, then the newest
        # detection. A bounded ISO key avoids platform-specific timestamp
        # overflow for alerts without a due date.
        due_key = due.isoformat() if due else "9999-12-31T23:59:59+00:00"
        detected_key = -(detected.timestamp()) if detected else 0.0
        return (-priority, due_key, detected_key, str(item.get("key") or ""))

    ranked = list(deduped.values())
    ranked.sort(key=sort_key)
    return ranked
