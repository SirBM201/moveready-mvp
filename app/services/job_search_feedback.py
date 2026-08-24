from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.job_application_performance_intelligence import SUPPORTED_DIMENSIONS, dimension_intelligence

CONTRACT_VERSION = "b19.9.5-v1"
MAX_ANALYTICS_BOOST = 8
MAX_ANALYTICS_PENALTY = 4


def build_feedback_profile(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows=list(items);signals={}
    for dimension in SUPPORTED_DIMENSIONS:
        result=dimension_intelligence(rows,dimension)
        signals[dimension]={str(row.get("value") or "unknown"): {"signal":row.get("signal"),"applications":row.get("applications"),"sample_sufficient":row.get("sample_sufficient")} for row in result["rows"]}
    return {"contract_version":CONTRACT_VERSION,"signals":signals,"applications_analyzed":len(rows),"policy":{"max_positive_adjustment":MAX_ANALYTICS_BOOST,"max_negative_adjustment":MAX_ANALYTICS_PENALTY,"eligibility_override_allowed":False,"sponsorship_override_allowed":False,"vacancy_evidence_override_allowed":False}}


def _value(job: Mapping[str, Any], dimension: str) -> str:
    aliases={"source":("source","source_name","provider"),"country":("country","country_code","location_country"),"occupation":("occupation","occupation_title","title"),"employer":("company","company_name")}
    for key in aliases[dimension]:
        value=str(job.get(key) or "").strip()
        if value:return value
    return "unknown"


def analytics_adjustment(job: Mapping[str, Any], feedback: Mapping[str, Any]) -> dict[str, Any]:
    total=0;reasons=[];signals=feedback.get("signals") if isinstance(feedback.get("signals"),Mapping) else {}
    for dimension in SUPPORTED_DIMENSIONS:
        value=_value(job,dimension);entry=(signals.get(dimension) or {}).get(value) if isinstance(signals.get(dimension),Mapping) else None
        if not isinstance(entry,Mapping) or not entry.get("sample_sufficient"):continue
        signal=entry.get("signal")
        if signal=="strong_observed_performance":delta=2
        elif signal=="some_observed_progression":delta=1
        elif signal=="no_observed_progression_yet":delta=-1
        else:continue
        total+=delta;reasons.append({"dimension":dimension,"value":value,"signal":signal,"delta":delta,"applications":entry.get("applications")})
    total=max(-MAX_ANALYTICS_PENALTY,min(MAX_ANALYTICS_BOOST,total))
    return {"contract_version":CONTRACT_VERSION,"adjustment":total,"reasons":reasons,"bounded":True,"historical_signal_only":True}


def optimize_rank(job: Mapping[str, Any], *, base_score: int | float, feedback: Mapping[str, Any], eligible: bool=True, evidence_valid: bool=True) -> dict[str, Any]:
    base=float(base_score);analytics=analytics_adjustment(job,feedback)
    if not eligible or not evidence_valid:
        applied=0
    else:
        applied=int(analytics["adjustment"])
    return {"contract_version":CONTRACT_VERSION,"base_score":base,"analytics_adjustment":applied,"optimized_score":base+applied,"analytics_reasons":analytics["reasons"],"gates":{"eligible":eligible,"evidence_valid":evidence_valid},"safety":{"analytics_cannot_create_eligibility":True,"analytics_cannot_create_sponsorship":True,"analytics_cannot_override_evidence":True,"user_history_is_not_employer_intent":True}}
