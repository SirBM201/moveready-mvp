from app.services.job_application_pattern_intelligence import detect_patterns


def app(i,state,source="official",country="Canada",occupation="Engineer",company="A"):
    return {"job_id":str(i),"pipeline_state":state,"readiness_state":"ready","source":source,"country":country,"occupation":occupation,"company":company}


def test_strong_observed_segment_produces_cautious_test_more_recommendation():
    rows=[app(1,"interview"),app(2,"interview"),app(3,"submitted"),app(4,"submitted")]
    result=detect_patterns(rows)
    rec=next(r for r in result["recommendations"] if r["dimension"]=="source")
    assert rec["type"]=="consider_more_of_observed_segment"
    assert rec["automatic_ranking_change"] is False


def test_repeated_no_progression_recommends_review_not_assumed_rejection_reason():
    rows=[app(1,"submitted"),app(2,"rejected"),app(3,"submitted")]
    result=detect_patterns(rows)
    rec=next(r for r in result["recommendations"] if r["dimension"]=="source")
    assert rec["type"]=="review_targeting_or_materials"
    assert "does not establish why" in rec["message"]
    assert result["safety"]["causal_rejection_reason_inferred"] is False


def test_insufficient_samples_are_reported_without_recommendation():
    result=detect_patterns([app(1,"interview"),app(2,"submitted")])
    assert result["recommendations"]==[]
    assert len(result["insufficient_evidence"])==4


def test_pattern_engine_never_changes_ranking_or_application_automatically():
    result=detect_patterns([app(1,"submitted"),app(2,"submitted"),app(3,"submitted")])
    assert result["safety"]["automatic_ranking_change"] is False
    assert result["safety"]["automatic_application_change"] is False
    assert result["safety"]["employer_intent_inferred"] is False
    assert result["safety"]["protected_attribute_inference_allowed"] is False
