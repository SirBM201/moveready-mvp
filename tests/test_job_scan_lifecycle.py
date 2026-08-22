from datetime import datetime, timezone

from app.services.job_scan_lifecycle import STALE_SCAN_MINUTES, scan_run_is_stale


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def test_running_scan_older_than_threshold_is_stale():
    assert scan_run_is_stale(
        {"status": "running", "started_at": "2026-08-22T11:29:59Z"},
        now=NOW,
    ) is True


def test_running_scan_at_threshold_is_stale():
    assert scan_run_is_stale(
        {"status": "running", "started_at": "2026-08-22T11:30:00+00:00"},
        now=NOW,
        stale_minutes=STALE_SCAN_MINUTES,
    ) is True


def test_recent_running_scan_is_not_stale():
    assert scan_run_is_stale(
        {"status": "running", "started_at": "2026-08-22T11:45:00Z"},
        now=NOW,
    ) is False


def test_terminal_scan_is_never_stale():
    assert scan_run_is_stale(
        {"status": "completed", "started_at": "2026-08-22T10:00:00Z"},
        now=NOW,
    ) is False
    assert scan_run_is_stale(
        {"status": "failed", "started_at": "2026-08-22T10:00:00Z"},
        now=NOW,
    ) is False


def test_running_scan_with_missing_or_invalid_start_time_is_recoverable():
    assert scan_run_is_stale({"status": "running", "started_at": None}, now=NOW) is True
    assert scan_run_is_stale({"status": "running", "started_at": "not-a-time"}, now=NOW) is True
