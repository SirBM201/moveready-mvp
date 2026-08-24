from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.job_application_performance_intelligence import MIN_SAMPLE_FOR_SIGNAL, SUPPORTED_DIMENSIONS, dimension_intelligence

CONTRACT_VERSION = "b19.9.4-v1"


def _recommendation(dimension: str, row: Mapping[str, Any]) -> dict[str, Any] | None:
    signal=str(row.get("signal") or "")
    value=str(row.get("value") or "unknown")
    applications=int(row.get("applications") or 0)
    rates=row.get("rates") if isinstance(row.get("rates"), Mapping) else {}
    evidence={"dimension":dimension,"value":value,"applications":applications,"interview_per_submission":rates.get("interview_per_submission",0),"offer_per_submission":rates.get("offer_per_submission",0),"hire_per_submission":rates.get("hire_per_submission",0),"signal":signal}
    if signal=="strong_observed_performance":
        return {"type":"consider_more_of_observed_segment","dimension":dimension,"value":value,"confidence":"moderate","message":f"Your recorded applications for {dimension} '{value}' have shown comparatively strong progression. Consider testing more suitable vacancies in this segment while keeping normal eligibility and vacancy-quality checks.","evidence":evidence,"automatic_ranking_change":False}
    if signal=="no_observed_progression_yet":
        return {"type":"review_targeting_or_materials","dimension":dimension,"value":value,"confidence":"low","message":f"Your recorded applications for {dimension} '{value}' have not yet produced interview progression. Review fit, eligibility and application materials before increasing volume; this does not establish why employers did not progress the applications.","evidence":evidence,"automatic_ranking_change":False}
    return None


def detect_patterns(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows=list(items);recommendations=[];insufficient=[]
    for dimension in SUPPORTED_DIMENSIONS:
        result=dimension_intelligence(rows,dimension)
        for row in result["rows"]:
            if not row.get("sample_sufficient"):
                insufficient.append({"dimension":dimension,"value":row.get("value"),"applications":row.get("applications"),"minimum_required":MIN_SAMPLE_FOR_SIGNAL})
                continue
            rec=_recommendation(dimension,row)
            if rec:recommendations.append(rec)
    recommendations.sort(key=lambda row:(0 if row["type"]=="consider_more_of_observed_segment" else 1,-int(row["evidence"]["applications"]),row["dimension"],row["value"].lower()))
    return {"contract_version":CONTRACT_VERSION,"applications_analyzed":len(rows),"recommendations":recommendations,"insufficient_evidence":insufficient,"safety":{"evidence_based_only":True,"causal_rejection_reason_inferred":False,"employer_intent_inferred":False,"protected_attribute_inference_allowed":False,"automatic_ranking_change":False,"automatic_application_change":False}}
