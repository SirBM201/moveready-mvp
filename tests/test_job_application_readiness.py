from app.services.job_application_readiness import evaluate_application_readiness, transition_readiness


def healthy_vacancy(**overrides):
    row = {
        "status": "open",
        "source_status": "verified",
        "relocation_support_status": "confirmed",
        "requirements_verified": True,
    }
    row.update(overrides)
    return row


def test_unknown_work_rights_are_review_required_not_assumed_eligible():
    result = evaluate_application_readiness(
        healthy_vacancy(relocation_support_status="unknown"),
        profile={},
        materials={"cv_ready": True},
    )
    assert result["state"] == "review_required"
    assert "work_rights_verification_required" in {x["code"] for x in result["issues"]}
    assert result["safety"]["auto_submit_allowed"] is False


def test_missing_cv_requires_materials():
    result = evaluate_application_readiness(healthy_vacancy(), materials={})
    assert result["state"] == "materials_required"
    assert "cv_required" in {x["code"] for x in result["issues"]}


def test_closed_vacancy_is_blocked():
    result = evaluate_application_readiness(healthy_vacancy(status="closed"), materials={"cv_ready": True})
    assert result["state"] == "blocked"
    assert result["blocking_issue_count"] >= 1


def test_no_sponsorship_without_authorization_is_blocked():
    result = evaluate_application_readiness(
        healthy_vacancy(relocation_support_status="no"),
        profile={"work_authorization": "not_authorized"},
        materials={"cv_ready": True},
    )
    assert result["state"] == "blocked"


def test_verified_vacancy_and_materials_reach_human_review_boundary():
    result = evaluate_application_readiness(
        healthy_vacancy(),
        profile={"work_authorization": "not_authorized"},
        materials={"cv_ready": True},
    )
    assert result["state"] == "ready_for_review"
    assert result["can_mark_ready"] is True
    assert result["can_start_application"] is False


def test_submission_is_never_inferred_from_status_alone():
    result = evaluate_application_readiness(
        healthy_vacancy(),
        materials={"cv_ready": True},
        existing_application={"status": "applied", "submission_confirmed": False},
    )
    assert result["state"] != "applied"


def test_confirmed_submission_can_be_recorded_as_applied():
    result = evaluate_application_readiness(
        healthy_vacancy(),
        materials={"cv_ready": True},
        existing_application={"status": "applied", "submission_confirmed": True},
    )
    assert result["state"] == "applied"
    assert result["terminal"] is True


def test_controlled_transition_requires_user_confirmation():
    denied = transition_readiness("ready_for_review", "ready_to_apply", user_confirmed=False)
    assert denied["ok"] is False
    assert denied["error"] == "user_confirmation_required"
    allowed = transition_readiness("ready_for_review", "ready_to_apply", user_confirmed=True)
    assert allowed == {"ok": True, "state": "ready_to_apply", "previous_state": "ready_for_review"}


def test_cannot_jump_directly_from_discovered_to_applied():
    result = transition_readiness("discovered", "applied", user_confirmed=True)
    assert result["ok"] is False
    assert result["error"] == "invalid_readiness_transition"
