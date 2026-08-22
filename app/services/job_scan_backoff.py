from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping


# Failed scheduled scans progressively cool down instead of repeatedly hammering
# an unhealthy employer/ATS source. Manual user scans remain available because
# the user scan endpoints intentionally do not gate on next_scan_at.
BACKOFF_MINUTES = {
    1: 30,
    2: 120,
    3: 360,
    4: 1440,
}
MAX_BACKOFF_MINUTES = 4320  # 72 hours for persistent failures (5+)
PERSISTENT_FAILURE_THRESHOLD = 4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def retry_delay_minutes(consecutive_failures: int) -> int:
    failures = max(1, int(consecutive_failures or 1))
    return BACKOFF_MINUTES.get(failures, MAX_BACKOFF_MINUTES)


def persistent_failure(consecutive_failures: int) -> bool:
    return int(consecutive_failures or 0) >= PERSISTENT_FAILURE_THRESHOLD


def backoff_state(watch: Mapping[str, Any], *, now: datetime | None = None) -> Dict[str, Any]:
    failures = max(1, int(watch.get("consecutive_failures") or 1))
    delay = retry_delay_minutes(failures)
    current = now or _utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    retry_at = current.astimezone(timezone.utc) + timedelta(minutes=delay)
    return {
        "consecutive_failures": failures,
        "retry_delay_minutes": delay,
        "retry_at": retry_at.isoformat(),
        "persistent_failure": persistent_failure(failures),
    }


def _latest_watch(watch_id: str, email: str) -> Dict[str, Any]:
    from app.services.supabase_client import get_supabase

    row = (
        get_supabase().table("relocation_job_watches").select("*")
        .eq("id", watch_id).eq("email", email).maybe_single().execute()
    ).data
    return row or {}


def _apply_failure_backoff(watch: Mapping[str, Any]) -> Dict[str, Any]:
    from app.services.supabase_client import get_supabase

    state = backoff_state(watch)
    watch_id = str(watch.get("id") or "")
    email = str(watch.get("email") or "")
    get_supabase().table("relocation_job_watches").update({
        "next_scan_at": state["retry_at"],
    }).eq("id", watch_id).eq("email", email).execute()
    return state


def install(job_automation_module: Any) -> None:
    """Apply bounded retry backoff after source failures.

    Successful scans keep the normal cadence and reset consecutive_failures in the
    existing scanner. Failed scans get a bounded cooldown. At the persistent-failure
    threshold an operational source_failed alert is emitted once per failure tier;
    the watch is not silently disabled, so a user can still retry it manually.
    """
    original = getattr(job_automation_module, "_scan_watch", None)
    if original is None or getattr(original, "_moveready_scan_backoff", False):
        return

    def scan_with_backoff(watch: Dict[str, Any], *, trigger_type: str) -> Dict[str, Any]:
        result = original(watch, trigger_type=trigger_type)
        if str(result.get("status") or "") != "failed":
            return result

        watch_id = str(watch.get("id") or "")
        email = str(watch.get("email") or "")
        current = _latest_watch(watch_id, email) or watch
        state = _apply_failure_backoff(current)
        result = {**result, **state}

        if state["persistent_failure"]:
            company_name = job_automation_module._company_name(current.get("company_id"), email)
            failures = state["consecutive_failures"]
            # One alert for entry into persistent failure, then one for each later
            # failure count. Alert reconciliation collapses these to the newest live
            # operational incident for the watch.
            job_automation_module._create_alert(
                email=email,
                watch_id=watch_id,
                job_id=None,
                alert_type="source_failed",
                severity="warning",
                title=f"Persistent source issue: {company_name}",
                summary=(
                    f"The official source has failed {failures} consecutive scans. "
                    f"Automatic retry is delayed for {state['retry_delay_minutes']} minutes. "
                    "Saved vacancies remain unchanged; verify the source URL if the problem continues."
                ),
                source_url=current.get("source_url"),
                marker=f"persistent-failure-{failures}",
            )
        return result

    scan_with_backoff._moveready_scan_backoff = True
    job_automation_module._scan_watch = scan_with_backoff
