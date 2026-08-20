from app.services.job_alert_reconciliation import reconcile_job_alert_payload


def test_reconciliation_hides_dismissed_archived_and_duplicate_alerts():
    payload = {
        "jobs": [
            {"id": "active-1", "status": "open", "canonical_identity": "husky|assembly"},
            {"id": "active-2", "status": "open", "canonical_identity": "husky|quality"},
            {"id": "old-1", "status": "archived", "canonical_identity": "husky|assembly"},
        ],
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

    assert [row["id"] for row in result["alerts"]] == ["scan", "new", "quality"]
    assert result["counts"]["unread_alerts"] == 2


def test_job_closed_alert_is_not_live_for_active_vacancy():
    payload = {
        "jobs": [{"id": "job-1", "status": "open", "canonical_identity": "x"}],
        "alerts": [{"id": "closed", "job_id": "job-1", "alert_type": "job_closed", "status": "unread"}],
        "counts": {},
    }

    result = reconcile_job_alert_payload(payload)
    assert result["alerts"] == []
    assert result["counts"]["unread_alerts"] == 0
