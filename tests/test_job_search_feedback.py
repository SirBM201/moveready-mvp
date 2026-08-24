from app.services.job_search_feedback import analytics_adjustment, build_feedback_profile, optimize_rank


def app(i,state,source="official",country="Canada",occupation="Engineer",company="A"):
    return {"job_id":str(i),"pipeline_state":state,"readiness_state":"ready","source":source,"country":country,"occupation":occupation,"company":company}


def test_strong_history_creates_small_bounded_positive_adjustment():
    history=[app(1,"interview"),app(2,"interview"),app(3,"submitted"),app(4,"submitted")]
    feedback=build_feedback_profile(history)
    result=analytics_adjustment(app(9,"preparing"),feedback)
    assert 0 < result["adjustment"] <= 8
    assert result["historical_signal_only"] is True


def test_repeated_no_progression_only_creates_small_penalty():
    history=[app(1,"submitted"),app(2,"rejected"),app(3,"submitted")]
    result=analytics_adjustment(app(9,"preparing"),build_feedback_profile(history))
    assert -4 <= result["adjustment"] < 0


def test_insufficient_history_does_not_change_ranking():
    feedback=build_feedback_profile([app(1,"interview"),app(2,"submitted")])
    assert analytics_adjustment(app(9,"preparing"),feedback)["adjustment"]==0


def test_analytics_never_overrides_ineligibility():
    history=[app(1,"interview"),app(2,"interview"),app(3,"interview")]
    result=optimize_rank(app(9,"preparing"),base_score=70,feedback=build_feedback_profile(history),eligible=False)
    assert result["analytics_adjustment"]==0
    assert result["optimized_score"]==70
    assert result["safety"]["analytics_cannot_create_eligibility"] is True


def test_analytics_never_overrides_invalid_vacancy_evidence():
    history=[app(1,"interview"),app(2,"interview"),app(3,"interview")]
    result=optimize_rank(app(9,"preparing"),base_score=70,feedback=build_feedback_profile(history),evidence_valid=False)
    assert result["analytics_adjustment"]==0
    assert result["safety"]["analytics_cannot_override_evidence"] is True
