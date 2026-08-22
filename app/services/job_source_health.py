from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from app.services.job_scan_backoff import PERSISTENT_FAILURE_THRESHOLD
from app.services.job_scan_lifecycle import _parse_timestamp


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _minutes_until(value: Any, *, now: Optional[datetime] = None) -> Optional[int]:
    target = _parse_timestamp(value)
    if target is None:
        return None
    current = now or _utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    seconds = (target - current.astimezone(timezone.utc)).total_seconds()
    return max(0, int((seconds + 59) // 60))


def classify_source_health(watch: Mapping[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Derive a stable, user-facing health state from persisted scan lifecycle fields."""
    status = str(watch.get("last_scan_status") or "").strip().casefold()
    failures = max(0, int(watch.get("consecutive_failures") or 0))
    last_error = str(watch.get("last_error") or "").strip() or None
    retry_in = _minutes_until(watch.get("next_scan_at"), now=now)

    if not watch.get("is_active", True):
        health = "paused"
    elif status == "running":
        health = "checking"
    elif status == "completed" and failures == 0:
        health = "healthy"
    elif failures >= PERSISTENT_FAILURE_THRESHOLD:
        health = "persistent_failure"
    elif failures > 0 or status == "failed":
        health = "degraded"
    else:
        health = "unknown"

    return {
        "source_health": health,
        "healthy": health == "healthy",
        "degraded": health in {"degraded", "persistent_failure"},
        "persistent_failure": health == "persistent_failure",
        "checking": health == "checking",
        "consecutive_failures": failures,
        "last_error": last_error,
        "retry_in_minutes": retry_in if health in {"degraded", "persistent_failure"} else None,
        "automatic_recovery_verified": health == "healthy" and status == "completed" and failures == 0 and last_error is None,
    }


def enrich_watch(watch: Mapping[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    return {**dict(watch), **classify_source_health(watch, now=now)}


def install(job_automation_module: Any) -> None:
    """Expose source-health state through the existing public watch serializer."""
    original = getattr(job_automation_module, "_public_watch", None)
    if original is None or getattr(original, "_moveready_source_health", False):
        return

    def public_watch_with_health(row: Dict[str, Any], companies: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        public = original(row, companies)
        return {**public, **classify_source_health(row)}

    public_watch_with_health._moveready_source_health = True
    job_automation_module._public_watch = public_watch_with_health
