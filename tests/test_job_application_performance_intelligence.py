from app.services.job_application_performance_intelligence import dimension_intelligence, performance_overview


def app(job_id,state,source="official",country="Canada",occupation="Engineer",company="A"):
    return {"job_id":job_id,"pipeline_state":state,"readiness_state":"ready","source":source,"country":country,"occupation":occupation,"company":company}


def test_small_samples_do_not_generate_strength_claims():
    result=dimension_intelligence([app("1","interview"),app("2","submitted")],"source")
    assert result["rows"][0]["signal"]=="insufficient_sample"
    assert result["rows"][0]["sample_sufficient"] is False


def test_observed_progression_can_create_strong_signal_after_minimum_sample():
    rows=[app("1","interview"),app("2","interview"),app("3","submitted"),app("4","submitted")]
    result=dimension_intelligence(rows,"source")
    assert result["rows"][0]["signal"]=="strong_observed_performance"
    assert result["rows"][0]["rates"]["interview_per_submission"]==0.5


def test_no_progression_is_descriptive_not_causal():
    rows=[app("1","submitted"),app("2","rejected"),app("3","submitted")]
    result=dimension_intelligence(rows,"employer")
    assert result["rows"][0]["signal"]=="no_observed_progression_yet"
    assert result["rows"][0]["interpretation"]=="observed_user_application_history_only"


def test_overview_covers_all_four_dimensions_and_blocks_unsafe_claims():
    rows=[app("1","interview"),app("2","submitted"),app("3","submitted")]
    result=performance_overview(rows)
    assert set(result["dimensions"])=={"source","country","occupation","employer"}
    assert result["safety"]["causal_claims_allowed"] is False
    assert result["safety"]["employer_quality_claims_allowed"] is False
    assert result["safety"]["discrimination_inference_allowed"] is False
    assert result["safety"]["ranking_modified"] is False
