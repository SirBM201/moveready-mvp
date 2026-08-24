from app.services.job_employer_ranking import rank_employer,rank_employers,recommendation

def test_evidence_and_fit_drive_rank_without_claim_inference():
 result=rank_employer({"employer_id":"e1","vacancy_fit":.9,"evidence_quality":.9,"observed_outcome_signal":.7,"freshness":.8,"campaign_disposition":"priority"})
 assert result["score"]>=75
 assert result["safety"]["correlation_not_causation"] is True
 assert result["safety"]["sponsorship_not_inferred"] is True

def test_campaign_exclusion_is_not_ranked():
 result=rank_employer({"employer_id":"e9","vacancy_fit":1,"evidence_quality":1,"campaign_disposition":"excluded"})
 assert result["rankable"] is False and result["score"]==0

def test_priority_is_only_small_component_not_override():
 weak=rank_employer({"employer_id":"weak","vacancy_fit":.1,"evidence_quality":.1,"freshness":.1,"campaign_disposition":"priority"})
 strong=rank_employer({"employer_id":"strong","vacancy_fit":.9,"evidence_quality":.9,"freshness":.9,"campaign_disposition":"open"})
 assert strong["score"]>weak["score"]

def test_portfolio_ranking_orders_evidence_score():
 rows=rank_employers([{"employer_id":"a","vacancy_fit":.2},{"employer_id":"b","vacancy_fit":.9,"evidence_quality":.9}])
 assert rows[0]["employer_id"]=="b"

def test_recommendation_is_actionable_but_requires_vacancy_verification():
 result=recommendation({"employer_id":"e1","vacancy_fit":1,"evidence_quality":1,"freshness":1,"campaign_disposition":"priority"})
 assert result["recommended_action"]=="prioritize_current_opportunities"
 assert result["safety"]["vacancy_verification_still_required"] is True
 assert "prioritization aid" in result["explanation"]
