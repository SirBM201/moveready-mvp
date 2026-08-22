from app.services.job_application_readiness import reconcile_readiness, vacancy_fingerprint


def test_fingerprint_is_stable_for_irrelevant_field_changes():
    a={"id":"1","status":"open","job_title":"Tech","country":"Canada","score":55}
    b={**a,"score":99}
    assert vacancy_fingerprint(a)==vacancy_fingerprint(b)


def test_fingerprint_changes_for_application_relevant_change():
    a={"status":"open","job_title":"Tech","country":"Canada","relocation_support_status":"confirmed"}
    b={**a,"relocation_support_status":"not_available"}
    assert vacancy_fingerprint(a)!=vacancy_fingerprint(b)


def test_changed_vacancy_invalidates_ready_to_apply():
    previous={"state":"ready_to_apply","vacancy_fingerprint":"old"}
    evaluation={"state":"review_required","issues":[]}
    result=reconcile_readiness(previous,evaluation,"new")
    assert result["invalidated"] is True
    assert result["state"]=="review_required"
    assert result["invalidation_reason"]=="vacancy_changed_after_user_confirmation"


def test_unchanged_vacancy_preserves_user_confirmation():
    previous={"state":"ready_to_apply","vacancy_fingerprint":"same"}
    evaluation={"state":"ready_for_review","issues":[]}
    result=reconcile_readiness(previous,evaluation,"same")
    assert result["invalidated"] is False
    assert result["state"]=="ready_to_apply"


def test_confirmed_application_is_not_undone_by_change():
    previous={"state":"applied","vacancy_fingerprint":"old"}
    evaluation={"state":"review_required","issues":[]}
    result=reconcile_readiness(previous,evaluation,"new")
    assert result["state"]=="applied"
    assert result["invalidated"] is False


def test_applied_job_can_become_closed_without_erasing_application_history():
    previous={"state":"applied","vacancy_fingerprint":"old"}
    evaluation={"state":"blocked","issues":[{"code":"vacancy_closed","blocking":True}]}
    result=reconcile_readiness(previous,evaluation,"new")
    assert result["state"]=="closed"
