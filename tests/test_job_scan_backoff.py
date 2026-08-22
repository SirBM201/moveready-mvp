from datetime import datetime, timezone

from app.services.job_scan_backoff import (
    MAX_BACKOFF_MINUTES,
    PERSISTENT_FAILURE_THRESHOLD,
    backoff_state,
    persistent_failure,
    retry_delay_minutes,
)


def test_retry_backoff_progresses_and_is_bounded():
    assert retry_delay_minutes(1) == 30
    assert retry_delay_minutes(2) == 120
    assert retry_delay_minutes(3) == 360
    assert retry_delay_minutes(4) == 1440
    assert retry_delay_minutes(5) == MAX_BACKOFF_MINUTES
    assert retry_delay_minutes(99) == MAX_BACKOFF_MINUTES


def test_persistent_failure_starts_at_four_consecutive_failures():
    assert not persistent_failure(PERSISTENT_FAILURE_THRESHOLD - 1)
    assert persistent_failure(PERSISTENT_FAILURE_THRESHOLD)
    assert persistent_failure(PERSISTENT_FAILURE_THRESHOLD + 10)


def test_backoff_state_returns_retry_time_and_failure_metadata():
    now = datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc)
    state = backoff_state({"consecutive_failures": 3}, now=now)
    assert state["consecutive_failures"] == 3
    assert state["retry_delay_minutes"] == 360
    assert state["retry_at"] == "2026-08-22T16:00:00+00:00"
    assert state["persistent_failure"] is False


def test_persistent_failure_uses_long_cooldown_after_threshold():
    now = datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc)
    state = backoff_state({"consecutive_failures": 5}, now=now)
    assert state["retry_delay_minutes"] == 4320
    assert state["retry_at"] == "2026-08-25T10:00:00+00:00"
    assert state["persistent_failure"] is True
