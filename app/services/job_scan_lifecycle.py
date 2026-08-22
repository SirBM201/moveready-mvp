from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping, Optional


STALE_SCAN_MINUTES = 30
STALE_SCAN_ERROR = "stale_scan_recovered"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def scan_run_is_stale(run: Mapping[str, Any], *, now: Optional[datetime] = None, stale_minutes: int = STALE_SCAN_MINUTES) -> bool:
    """Return True only for a running scan older than the recovery threshold."""
    if str(run.get("status") or "") != "running":
        return False
    started_at = _parse_timestamp(run.get("started_at"))
    if started_at is None:
        return True
    current = now or _utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return started_at <= current.astimezone(timezone.utc) - timedelta(minutes=stale_minutes)


def _latest_running_scan(watch_id: str, email: str) -> Optional[Dict[str, Any]]:
    from app.services.supabase_client import get_supabase

    rows = (
        get_supabase().table("relocation_job_scan_runs").select("*")
        .eq("watch_id", watch_id).eq("email", email).eq("status", "running")
        .order("started_at", desc=True).limit(1).execute()
    ).data or []
    return rows[0] if rows else None


def _recover_stale_scan(watch: Mapping[str, Any], run: Mapping[str, Any]) -> None:
    """Close an abandoned run and make its watch immediately eligible for a safe retry."""
    from app.services.supabase_client import get_supabase

    supabase = get_supabase()
    now_iso = _utcnow().isoformat()
    watch_id = str(watch.get("id") or "")
    email = str(watch.get("email") or "")
    failures = min(1000, int(watch.get("consecutive_failures") or 0) + 1)

    supabase.table("relocation_job_scan_runs").update({
        "status": "failed",
        "error_code": STALE_SCAN_ERROR,
        "error_summary": "The scan stopped without completing and was automatically released for retry.",
        "completed_at": now_iso,
    }).eq("id", run.get("id")).eq("status", "running").execute()

    supabase.table("relocation_job_watches").update({
        "last_scan_at": now_iso,
        "last_scan_status": "failed",
        "last_error": STALE_SCAN_ERROR,
        "consecutive_failures": failures,
        "next_scan_at": now_iso,
    }).eq("id", watch_id).eq("email", email).execute()


def install(job_automation_module: Any) -> None:
    """Guard scans against overlap and recover abandoned running scans before retrying."""
    original = getattr(job_automation_module, "_scan_watch", None)
    if original is None or getattr(original, "_moveready_scan_lifecycle_guard", False):
        return

    def guarded_scan_watch(watch: Dict[str, Any], *, trigger_type: str) -> Dict[str, Any]:
        watch_id = str(watch.get("id") or "")
        email = str(watch.get("email") or "")
        running = _latest_running_scan(watch_id, email)
        if running:
            if not scan_run_is_stale(running):
                return {
                    "watch_id": watch_id,
                    "status": "running",
                    "skipped": True,
                    "skip_reason": "scan_already_running",
                    "run_id": running.get("id"),
                }
            _recover_stale_scan(watch, running)
            # The stale run is now terminal. Continue directly into the normal scanner;
            # a successful retry resets failure state, while a real source failure is
            # recorded by the existing scan failure lifecycle.
        return original(watch, trigger_type=trigger_type)

    guarded_scan_watch._moveready_scan_lifecycle_guard = True
    job_automation_module._scan_watch = guarded_scan_watch
