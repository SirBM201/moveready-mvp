from __future__ import annotations

from typing import Any, Mapping

CONTRACT_VERSION = "b19.10.4-v1"
DEFAULT_WEEKLY_TARGETS = {
    "light": {"qualified_vacancies": 5, "applications": 2, "followups": 1},
    "standard": {"qualified_vacancies": 10, "applications": 5, "followups": 2},
    "intensive": {"qualified_vacancies": 20, "applications": 10, "followups": 4},
}


def weekly_targets(campaign: Mapping[str, Any], overrides: Mapping[str, Any] | None = None) -> dict[str, int]:
    intensity = str(campaign.get("search_intensity") or "standard").strip().lower()
    targets = dict(DEFAULT_WEEKLY_TARGETS.get(intensity, DEFAULT_WEEKLY_TARGETS["standard"]))
    for key, value in (overrides or {}).items():
        if key in targets:
            try: targets[key] = max(0, min(100, int(value)))
            except (TypeError, ValueError): pass
    return targets


def execution_status(targets: Mapping[str, int], actual: Mapping[str, int]) -> dict[str, Any]:
    rows={};total_target=0;total_done=0
    for key,target in targets.items():
        done=max(0,int(actual.get(key) or 0));target=max(0,int(target));total_target+=target;total_done+=min(done,target)
        rows[key]={"target":target,"actual":done,"remaining":max(0,target-done),"completion_percent":100 if target==0 else min(100,round(done/target*100))}
    return {"metrics":rows,"overall_completion_percent":100 if total_target==0 else round(total_done/total_target*100)}


def adaptive_strategy(campaign: Mapping[str, Any], performance: Mapping[str, Any], targets: Mapping[str, int], actual: Mapping[str, int]) -> dict[str, Any]:
    execution=execution_status(targets,actual);actions=[]
    leaders=performance.get("observed_leaders") if isinstance(performance.get("observed_leaders"),Mapping) else {}
    for dimension in ("source","country","occupation","employer"):
        leader=leaders.get(dimension)
        if isinstance(leader,Mapping) and leader.get("sample_sufficient") and leader.get("signal")=="strong_observed_performance":
            actions.append({"type":"test_more_observed_segment","dimension":dimension,"value":leader.get("value"),"reason":"strong_observed_progression","automatic_change":False})
    app_metric=execution["metrics"].get("applications",{})
    vacancy_metric=execution["metrics"].get("qualified_vacancies",{})
    if vacancy_metric.get("remaining",0)>0: actions.append({"type":"discover_more_qualified_vacancies","remaining":vacancy_metric["remaining"],"automatic_change":False})
    if app_metric.get("remaining",0)>0: actions.append({"type":"prepare_or_submit_user_approved_applications","remaining":app_metric["remaining"],"automatic_submission":False})
    return {"contract_version":CONTRACT_VERSION,"campaign_id":campaign.get("id"),"weekly_targets":dict(targets),"execution":execution,"recommended_actions":actions,"safety":{"strategy_is_advisory":True,"historical_performance_is_not_causation":True,"eligibility_override_allowed":False,"sponsorship_inference_allowed":False,"automatic_application_submission":False,"automatic_campaign_retargeting":False}}
