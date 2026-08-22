from app.services.job_alert_reconciliation import reconcile_job_alert_payload


def test_reconciliation_hides_dismissed_archived_and_duplicate_alerts():
    payload = {
        "jobs": [
            {"id": "active-1", "status": "open", "canonical_identity": "husky|assembly"},
            {"id": "active-2", "status": "open", "canonical_identity": "husky|quality"},
            {"id": "old-1", "status": "archived", "canonical_identity": "husky|assembly"},
        ],
        "watches": [],
        "alerts": [
            {"id": "new", "job_id": "active-1", "alert_type": "new_match", "status": "unread", "created_at": "2026-08-21T02:00:00Z"},
            {"id": "older-duplicate", "job_id": "active-1", "alert_type": "new_match", "status": "unread", "created_at": "2026-08-21T01:00:00Z"},
            {"id": "quality", "job_id": "active-2", "alert_type": "new_match", "status": "read", "created_at": "2026-08-21T02:00:00Z"},
            {"id": "archived", "job_id": "old-1", "alert_type": "new_match", "status": "unread", "created_at": "2026-08-21T02:00:00Z"},
            {"id": "dismissed", "job_id": "active-2", "alert_type": "new_match", "status": "dismissed", "created_at": "2026-08-21T03:00:00Z"},
            {"id": "scan", "job_id": None, "alert_type": "scan_failed", "status": "unread", "created_at": "2026-08-21T04:00:00Z"},
        ],
        "counts": {"unread_alerts": 99},
    }
    result = reconcile_job_alert_payload(payload)
    assert [row["id"] for row in result["alerts"]] == ["scan", "quality", "new"]
    assert result["counts"]["unread_alerts"] == 2
    assert result["counts"]["unread_match_alerts"] == 1
    assert result["counts"]["unread_scan_issues"] == 1
    assert result["counts"]["active_source_failures"] == 1


def test_newer_changed_alert_supersedes_older_new_match_for_same_canonical_vacancy():
    payload = {"jobs": [{"id": "job-1", "status": "open", "canonical_identity": "husky|manufacturing-technician"}], "alerts": [
        {"id": "new-match", "job_id": "job-1", "alert_type": "new_match", "status": "unread", "created_at": "2026-08-22T07:43:00Z"},
        {"id": "changed", "job_id": "job-1", "alert_type": "job_changed", "status": "unread", "created_at": "2026-08-22T08:11:00Z"}], "counts": {}}
    result = reconcile_job_alert_payload(payload)
    assert [row["id"] for row in result["alerts"]] == ["changed"]
    assert result["counts"]["unread_match_alerts"] == 1


def test_actionable_alerts_without_canonical_identity_dedupe_by_job_id():
    payload = {"jobs": [{"id": "legacy-job", "status": "open", "canonical_identity": None}], "alerts": [
        {"id": "older", "job_id": "legacy-job", "alert_type": "new_match", "status": "unread", "created_at": "2026-08-22T08:00:00Z"},
        {"id": "newer", "job_id": "legacy-job", "alert_type": "closing_soon", "status": "unread", "created_at": "2026-08-22T09:00:00Z"}], "counts": {}}
    result = reconcile_job_alert_payload(payload)
    assert [row["id"] for row in result["alerts"]] == ["newer"]


def test_job_closed_alert_is_not_live_for_active_vacancy():
    payload = {"jobs": [{"id": "job-1", "status": "open", "canonical_identity": "x"}], "alerts": [{"id": "closed", "job_id": "job-1", "alert_type": "job_closed", "status": "unread"}], "counts": {}}
    result = reconcile_job_alert_payload(payload)
    assert result["alerts"] == []


def test_successful_scan_supersedes_older_failure_alert():
    payload = {
        "jobs": [],
        "watches": [{"id": "watch-1", "last_scan_status": "completed", "last_scan_at": "2026-08-22T10:00:00Z"}],
        "alerts": [{"id": "failed", "watch_id": "watch-1", "job_id": None, "alert_type": "scan_failed", "status": "unread", "created_at": "2026-08-22T09:00:00Z"}],
        "counts": {},
    }
    result = reconcile_job_alert_payload(payload)
    assert result["alerts"] == []
    assert result["counts"]["unread_scan_issues"] == 0
    assert result["counts"]["active_source_failures"] == 0


def test_failure_after_last_success_remains_live():
    payload = {
        "jobs": [],
        "watches": [{"id": "watch-1", "last_scan_status": "failed", "last_scan_at": "2026-08-22T11:00:00Z"}],
        "alerts": [{"id": "failed", "watch_id": "watch-1", "job_id": None, "alert_type": "scan_failed", "status": "unread", "created_at": "2026-08-22T11:00:01Z"}],
        "counts": {},
    }
    result = reconcile_job_alert_payload(payload)
    assert [row["id"] for row in result["alerts"]] == ["failed"]
    assert result["counts"]["active_source_failures"] == 1


def test_repeated_failures_collapse_to_newest_incident_per_watch():
    payload = {
        "jobs": [],
        "watches": [{"id": "watch-1", "last_scan_status": "failed", "last_scan_at": "2026-08-22T12:00:00Z"}],
        "alerts": [
            {"id": "old", "watch_id": "watch-1", "job_id": None, "alert_type": "scan_failed", "status": "unread", "created_at": "2026-08-22T10:00:00Z"},
            {"id": "new", "watch_id": "watch-1", "job_id": None, "alert_type": "source_error", "status": "unread", "created_at": "2026-08-22T12:00:00Z"},
        ],
        "counts": {},
    }
    result = reconcile_job_alert_payload(payload)
    assert [row["id"] for row in result["alerts"]] == ["new"]
    assert result["counts"]["unread_scan_issues"] == 1
    assert result["counts"]["active_source_failures"] == 1
