from app.services.job_application_drafts import build_application_draft, source_fingerprint


def vacancy(**overrides):
    row={"id":"job-1","job_title":"Production Supervisor","company_name":"Example Plastics","requirements":["Injection moulding experience","Team leadership"],"updated_at":"2026-08-22T12:00:00Z"}
    row.update(overrides); return row


def profile():
    return {"skills":["Injection moulding","Shift leadership"],"achievements":["Reduced startup time"],"experience_summary":["Supervised production shifts"],"updated_at":"2026-08-22T10:00:00Z"}


def materials(**overrides):
    row={"cv_id":"cv-1","cv_valid":True,"cv":{"updated_at":"2026-08-22T11:00:00Z"}}
    row.update(overrides); return row


def test_draft_requires_safe_readiness_boundary():
    result=build_application_draft(vacancy(),profile(),materials(),readiness={"state":"blocked"})
    assert result["ok"] is False
    assert result["error"] == "vacancy_not_ready_for_drafting"


def test_draft_requires_valid_bound_cv():
    result=build_application_draft(vacancy(),profile(),materials(cv_valid=False),readiness={"state":"ready_for_review"})
    assert result["ok"] is False
    assert result["error"] == "valid_bound_cv_required"


def test_tailoring_uses_verified_candidate_evidence_and_requirements():
    result=build_application_draft(vacancy(),profile(),materials(),readiness={"state":"ready_for_review"})
    assert result["ok"] is True
    assert result["contract_version"] == "b19.5-v1"
    assert "Reduced startup time" in result["cv_draft"]["evidence_to_prioritize"]
    assert "Injection moulding experience" in result["cv_draft"]["requirements_to_address"]
    assert result["cv_draft"]["fabrication_prohibited"] is True


def test_application_questions_remain_user_reviewed():
    result=build_application_draft(vacancy(application_questions_required=True),profile(),materials(),readiness={"state":"ready_to_apply"})
    assert result["application_answers"]["status"] == "needs_employer_questions"
    assert result["safety"]["user_review_required"] is True
    assert result["safety"]["auto_submit_allowed"] is False


def test_source_fingerprint_changes_when_vacancy_changes():
    first=source_fingerprint(vacancy(),profile(),materials())
    second=source_fingerprint(vacancy(updated_at="2026-08-22T13:00:00Z"),profile(),materials())
    assert first != second
