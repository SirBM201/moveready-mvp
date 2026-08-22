from app.services.job_application_handoff import approve_package, build_controlled_handoff, build_package_review


def _draft(status="reviewed"):
    return {
        "id": "draft-1",
        "job_id": "job-1",
        "status": status,
        "cv_draft": {"target_title": "Technician"},
        "cover_letter_draft": {"opening": "Application"},
        "application_answers": {"status": "not_required_or_not_detected"},
    }


def test_review_blocks_stale_package():
    result = build_package_review(_draft("stale"), {"state": "ready_to_apply"})
    assert result["ok"] is False
    assert "application_draft_is_stale" in result["blockers"]


def test_approval_requires_explicit_user_confirmation():
    result = approve_package(_draft(), {"state": "ready_to_apply"}, user_confirmed=False)
    assert result["approved"] is False
    assert result["blockers"] == ["explicit_user_approval_required"]


def test_approved_package_still_cannot_auto_submit():
    result = approve_package(_draft(), {"state": "ready_to_apply"}, user_confirmed=True)
    assert result["approved"] is True
    assert result["submission_allowed"] is False


def test_handoff_requires_persisted_approved_status():
    result = build_controlled_handoff(_draft("reviewed"), {"source_url": "https://example.com/job"}, approved=True)
    assert result["ok"] is False
    assert result["error"] == "approved_application_package_required"


def test_handoff_returns_destination_without_submitting():
    result = build_controlled_handoff(_draft("approved"), {"source_url": "https://example.com/job"}, approved=True)
    assert result["ok"] is True
    assert result["destination_url"] == "https://example.com/job"
    assert result["safety"]["user_must_trigger_submission"] is True
    assert result["safety"]["auto_submit_allowed"] is False
