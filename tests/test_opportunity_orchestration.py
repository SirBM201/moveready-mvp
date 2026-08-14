from app.services.opportunity_orchestration import build_opportunity_view, next_best_action


def test_unknown_scores_are_not_zero():
    view = build_opportunity_view({"summary": "Test route"})
    assert view["dimensions"][0]["score"] is None
    assert view["dimensions"][0]["status"] == "needs_assessment"


def test_hard_blocker_has_priority():
    action = next_best_action({"hard_blocker": "Work authorization required", "language_readiness": 20, "missing_document": "passport"})
    assert action["type"] == "resolve_blocker"


def test_document_precedes_language_gap():
    action = next_best_action({"missing_document": "proof of funds", "language_readiness": 20})
    assert action["type"] == "document"


def test_known_funding_gap_routes_to_readiness():
    action = next_best_action({"known_funds_requirement": True, "financial_readiness": 70, "language_readiness": 95})
    assert action["workspace"] == "/readiness-tools"


def test_language_gap_routes_to_coach():
    action = next_best_action({"language_readiness": 55, "language_target_threshold": 80})
    assert action["workspace"] == "/language-coach"


def test_job_dimensions_remain_separate():
    view = build_opportunity_view({}, {"is_job": True, "career_match": 95, "application_viability": 20})
    values = {item["label"]: item["score"] for item in view["dimensions"]}
    assert values["Career Match"] == 95
    assert values["Application Viability"] == 20
