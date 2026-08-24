from __future__ import annotations
from typing import Any,Iterable,Mapping
from app.services.job_employer_history import employer_timeline,opportunity_history
from app.services.job_employer_ranking import recommendation
from app.services.job_employer_targeting import employer_campaign_fit

CONTRACT_VERSION="b19.11.6-v1"

def build_employer_dashboard(*,employer:Mapping[str,Any],vacancies:Iterable[Mapping[str,Any]]=(),applications:Iterable[Mapping[str,Any]]=(),interactions:Iterable[Mapping[str,Any]]=(),campaign_targets:Iterable[Mapping[str,Any]]=(),ranking_inputs:Mapping[str,Any]|None=None)->dict[str,Any]:
    vacancy_rows=list(vacancies);application_rows=list(applications);interaction_rows=list(interactions);target_rows=list(campaign_targets)
    employer_id=str(employer.get("id") or "")
    return {"contract_version":CONTRACT_VERSION,"employer":dict(employer),"opportunity_history":opportunity_history(vacancy_rows,application_rows),"timeline":employer_timeline(employer=employer,vacancies=vacancy_rows,applications=application_rows,interactions=interaction_rows),"campaign_fit":employer_campaign_fit(employer_id,target_rows),"recommendation":recommendation({"employer_id":employer_id,**dict(ranking_inputs or {})}),"safety":{"dashboard_is_descriptive_and_advisory":True,"canonical_identity_is_not_employer_verification":True,"sponsorship_not_inferred":True,"relocation_support_not_inferred":True,"employer_intent_not_inferred":True,"historical_outcomes_do_not_predict_future_outcomes":True,"automatic_application_submission":False}}
