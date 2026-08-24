from __future__ import annotations
from typing import Any,Iterable,Mapping
from app.services.job_search_campaign_progress import progress
from app.services.job_search_campaign_strategy import weekly_targets,adaptive_strategy
from app.services.job_search_campaign_action_plan import daily_action_plan

CONTRACT_VERSION="b19.10.6-v1"

def build_campaign_dashboard(*,campaign:Mapping[str,Any],vacancies:Iterable[Mapping[str,Any]],applications:Iterable[Mapping[str,Any]],analytics:Mapping[str,Any]|None=None,portfolio_actions:Iterable[Mapping[str,Any]]=(),target_overrides:Mapping[str,Any]|None=None,actual:Mapping[str,int]|None=None,limit:int=10)->dict[str,Any]:
    vacancy_rows=list(vacancies);application_rows=list(applications);analytics=dict(analytics or {})
    campaign_progress=progress(campaign,vacancy_rows,application_rows)
    targets=weekly_targets(campaign,target_overrides)
    observed=dict(actual or {"qualified_vacancies":len(vacancy_rows),"applications":len(application_rows),"followups":0})
    strategy=adaptive_strategy(campaign,analytics,targets,observed)
    action_plan=daily_action_plan(campaign,strategy,portfolio_actions,limit=limit)
    return {"contract_version":CONTRACT_VERSION,"campaign":dict(campaign),"progress":campaign_progress,"weekly_execution":{"targets":targets,"actual":observed,"status":strategy["execution"]},"adaptive_strategy":{"recommended_actions":strategy["recommended_actions"],"safety":strategy["safety"]},"action_center":action_plan,"analytics_context":{"applications_analyzed":analytics.get("applications_analyzed",0),"observed_leaders":analytics.get("observed_leaders",{}),"insufficient_evidence":analytics.get("insufficient_evidence",[])},"safety":{"dashboard_is_advisory":True,"historical_performance_is_not_causation":True,"automatic_application_submission":False,"automatic_external_contact":False,"automatic_campaign_retargeting":False,"eligibility_override_allowed":False,"sponsorship_inference_allowed":False}}
