from app.services.job_application_readiness import evaluate_application_readiness, validate_promotion


def base_vacancy(**overrides):
    value={"status":"open","source_status":"healthy","requirements_verified":True,"relocation_support_status":"confirmed","cover_letter_required":False,"application_questions_required":False}
    value.update(overrides); return value


def test_valid_bound_cv_reaches_ready_for_review():
    result=evaluate_application_readiness(base_vacancy(),materials={"cv_id":"cv-1","cv_valid":True})
    assert result["contract_version"] == "b19.4-v1"
    assert result["state"] == "ready_for_review"
    assert result["pre_application_valid"] is True


def test_missing_cv_requires_materials():
    result=evaluate_application_readiness(base_vacancy(),materials={})
    assert result["state"] == "materials_required"
    assert "cv_required" in {i["code"] for i in result["issues"]}


def test_invalid_cv_cannot_satisfy_material_requirement():
    result=evaluate_application_readiness(base_vacancy(),materials={"cv_id":"cv-1","cv_valid":False})
    assert result["state"] == "materials_required"
    assert "cv_invalid" in {i["code"] for i in result["issues"]}


def test_required_cover_letter_must_be_valid_bound_asset():
    result=evaluate_application_readiness(base_vacancy(cover_letter_required=True),materials={"cv_id":"cv-1","cv_valid":True,"cover_letter_id":"cover-1","cover_letter_valid":False})
    assert result["state"] == "materials_required"
    assert "cover_letter_invalid" in {i["code"] for i in result["issues"]}


def test_application_answers_are_part_of_material_gate():
    result=evaluate_application_readiness(base_vacancy(application_questions_required=True),materials={"cv_id":"cv-1","cv_valid":True,"application_answers_ready":False})
    assert result["state"] == "materials_required"
    assert "application_answers_required" in {i["code"] for i in result["issues"]}


def test_ready_promotion_requires_clean_pre_application_evaluation():
    blocked=evaluate_application_readiness(base_vacancy(),materials={"cv_id":"cv-1","cv_valid":False})
    result=validate_promotion(blocked,"ready_to_apply")
    assert result["ok"] is False
    assert result["error"] == "pre_application_validation_failed"


def test_clean_review_can_be_promoted_to_ready_to_apply():
    ready=evaluate_application_readiness(base_vacancy(),materials={"cv_id":"cv-1","cv_valid":True})
    assert validate_promotion(ready,"ready_to_apply")["ok"] is True
