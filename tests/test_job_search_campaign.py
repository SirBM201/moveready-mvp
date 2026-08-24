from app.services.job_search_campaign import campaign_contract, normalize_campaign, validate_campaign

def campaign(**overrides):
    row={"name":"Canada PET Production Campaign","target_countries":["Canada"],"target_occupations":["Production Supervisor","Injection Moulding Technician"],"sponsorship_required":True,"search_intensity":"intensive"};row.update(overrides);return row

def test_campaign_normalizes_targets_and_defaults():
    result=normalize_campaign(campaign(target_countries=["Canada","Canada","  "]));assert result["target_countries"]==["Canada"];assert result["status"]=="draft";assert result["search_intensity"]=="intensive"
def test_campaign_requires_country_and_occupation_targets():
    result=validate_campaign(campaign(target_countries=[],target_occupations=[]));assert result["ok"] is False;assert "target_country_required" in result["errors"];assert "target_occupation_required" in result["errors"]
def test_campaign_does_not_treat_targeting_as_immigration_entitlement():
    result=campaign_contract(campaign());assert result["safety"]["campaign_does_not_create_work_authorization"] is True;assert result["safety"]["campaign_does_not_guarantee_sponsorship"] is True;assert result["safety"]["vacancy_evidence_still_required"] is True;assert result["safety"]["automatic_application_submission"] is False
def test_work_authorized_target_with_sponsorship_requirement_gets_warning():
    result=validate_campaign(campaign(work_authorized_countries=["Canada"]));assert "sponsorship_requirement_may_not_apply_to_all_work_authorized_targets" in result["warnings"]
def _raises(message,**overrides):
    try:normalize_campaign(campaign(**overrides))
    except ValueError as exc:assert message in str(exc);return
    raise AssertionError(f"expected ValueError containing {message}")
def test_invalid_status_and_intensity_are_rejected():
    _raises("unsupported_campaign_status",status="running");_raises("unsupported_search_intensity",search_intensity="maximum")
