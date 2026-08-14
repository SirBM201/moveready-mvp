from app.services.opportunity_finder import recommend_pathways


def test_work_goal_and_experience_prioritize_work():
    result = recommend_pathways({"main_goal":"work","work_experience_years":8,"target_country":"Canada","education_level":"OND","available_funds_amount":10000})
    assert result["recommendations"][0]["pathway"] == "work"
    assert result["recommendations"][0]["fit_score"] >= 70


def test_business_profile_surfaces_founder_routes():
    result = recommend_pathways({"main_goal":"startup","business_stage":"operating","available_funds_amount":15000})
    keys = [item["pathway"] for item in result["recommendations"][:3]]
    assert "startup" in keys
    assert "business" in keys


def test_finder_exposes_gaps_and_no_guarantee_language():
    result = recommend_pathways({"main_goal":"relocation"})
    assert result["profile_gaps"]
    assert "not eligibility" in result["safety_note"].lower()
