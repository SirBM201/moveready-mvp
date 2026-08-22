from datetime import datetime, timezone

from app.services.job_source_health import classify_source_health

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def test_completed_source_is_healthy_and_recovery_verified():
    state = classify_source_health({"is_active": True, "last_scan_status": "completed", "consecutive_failures": 0, "last_error": None}, now=NOW)
    assert state["source_health"] == "healthy"
    assert state["automatic_recovery_verified"] is True
    assert state["degraded"] is False


def test_single_failure_is_degraded_with_retry_window():
    state = classify_source_health({"is_active": True, "last_scan_status": "failed", "consecutive_failures": 1, "last_error": "official_source_timeout", "next_scan_at": "2026-08-22T12:30:00+00:00"}, now=NOW)
    assert state["source_health"] == "degraded"
    assert state["retry_in_minutes"] == 30
    assert state["automatic_recovery_verified"] is False


def test_four_failures_are_persistent():
    state = classify_source_health({"is_active": True, "last_scan_status": "failed", "consecutive_failures": 4, "last_error": "official_source_access_blocked_http_403", "next_scan_at": "2026-08-23T12:00:00+00:00"}, now=NOW)
    assert state["source_health"] == "persistent_failure"
    assert state["persistent_failure"] is True
    assert state["retry_in_minutes"] == 1440


def test_success_after_persistent_failure_fully_clears_health_state():
    before = classify_source_health({"is_active": True, "last_scan_status": "failed", "consecutive_failures": 5, "last_error": "official_source_network_error"}, now=NOW)
    after = classify_source_health({"is_active": True, "last_scan_status": "completed", "consecutive_failures": 0, "last_error": None}, now=NOW)
    assert before["source_health"] == "persistent_failure"
    assert after["source_health"] == "healthy"
    assert after["last_error"] is None
    assert after["automatic_recovery_verified"] is True


def test_running_and_paused_have_distinct_health_states():
    running = classify_source_health({"is_active": True, "last_scan_status": "running", "consecutive_failures": 0}, now=NOW)
    paused = classify_source_health({"is_active": False, "last_scan_status": "completed", "consecutive_failures": 0}, now=NOW)
    assert running["source_health"] == "checking"
    assert paused["source_health"] == "paused"
