from __future__ import annotations
from typing import Any, Iterable, Mapping

CONTRACT_VERSION="b19.11.5-v1"

def _bounded(value:Any)->float:
    try:return max(0.0,min(1.0,float(value)))
    except (TypeError,ValueError):return 0.0

def rank_employer(payload:Mapping[str,Any])->dict[str,Any]:
    disposition=str(payload.get("campaign_disposition") or "open").lower()
    if disposition=="excluded":
        return {"employer_id":payload.get("employer_id"),"score":0.0,"rankable":False,"reason_codes":["campaign_excluded"],"contract_version":CONTRACT_VERSION,"safety":_safety()}
    vacancy_fit=_bounded(payload.get("vacancy_fit"));evidence_quality=_bounded(payload.get("evidence_quality"));observed_outcome=_bounded(payload.get("observed_outcome_signal"));freshness=_bounded(payload.get("freshness"))
    campaign=1.0 if disposition=="priority" else (0.65 if disposition=="watch" else 0.4)
    score=round(100*(0.35*vacancy_fit+0.25*evidence_quality+0.15*observed_outcome+0.15*freshness+0.10*campaign),2)
    reasons=[]
    if vacancy_fit>=.7:reasons.append("strong_current_vacancy_fit")
    if evidence_quality>=.7:reasons.append("strong_supporting_evidence")
    if freshness>=.7:reasons.append("recent_opportunity_evidence")
    if observed_outcome>=.7:reasons.append("positive_recorded_outcome_pattern")
    if disposition=="priority":reasons.append("campaign_priority")
    return {"employer_id":payload.get("employer_id"),"score":score,"rankable":True,"reason_codes":reasons,"components":{"vacancy_fit":vacancy_fit,"evidence_quality":evidence_quality,"observed_outcome_signal":observed_outcome,"freshness":freshness,"campaign_signal":campaign},"contract_version":CONTRACT_VERSION,"safety":_safety()}

def rank_employers(items:Iterable[Mapping[str,Any]])->list[dict[str,Any]]:
    rows=[rank_employer(item) for item in items]
    return sorted(rows,key=lambda row:(row["rankable"],row["score"]),reverse=True)

def recommendation(row:Mapping[str,Any])->dict[str,Any]:
    ranked=rank_employer(row)
    if not ranked["rankable"]:action="do_not_prioritize"
    elif ranked["score"]>=75:action="prioritize_current_opportunities"
    elif ranked["score"]>=55:action="review_current_opportunities"
    else:action="monitor_for_better_fit"
    return {**ranked,"recommended_action":action,"explanation":"Recommendation is a prioritization aid based only on recorded campaign, vacancy, evidence, freshness and outcome signals; verify each vacancy before acting."}

def _safety()->dict[str,bool]:
    return {"ranking_is_not_employer_quality_rating":True,"correlation_not_causation":True,"historical_outcomes_do_not_predict_future_outcomes":True,"sponsorship_not_inferred":True,"relocation_support_not_inferred":True,"vacancy_verification_still_required":True,"automatic_application_submission":False}
