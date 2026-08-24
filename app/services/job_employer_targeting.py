from __future__ import annotations
from typing import Any, Iterable, Mapping

CONTRACT_VERSION="b19.11.4-v1"
TARGET_TYPES=("priority","watch","excluded")

def normalize_target(payload:Mapping[str,Any])->dict[str,Any]:
    target_type=str(payload.get("target_type") or "watch").strip().lower()
    if target_type not in TARGET_TYPES: raise ValueError("unsupported_employer_target_type")
    employer_id=str(payload.get("employer_id") or "").strip()
    if not employer_id: raise ValueError("employer_id_required")
    return {"employer_id":employer_id,"target_type":target_type,"reason":str(payload.get("reason") or "").strip() or None,"source":str(payload.get("source") or "user").strip().lower(),"active":bool(payload.get("active",True))}

def campaign_employer_policy(targets:Iterable[Mapping[str,Any]])->dict[str,Any]:
    result={"priority":[],"watch":[],"excluded":[]}
    for raw in targets:
        row=normalize_target(raw)
        if row["active"] and row["employer_id"] not in result[row["target_type"]]:result[row["target_type"]].append(row["employer_id"])
    # exclusion is authoritative inside the campaign and cannot coexist with positive targeting
    excluded=set(result["excluded"])
    result["priority"]=[x for x in result["priority"] if x not in excluded]
    result["watch"]=[x for x in result["watch"] if x not in excluded and x not in result["priority"]]
    return {"contract_version":CONTRACT_VERSION,**result,"safety":{"exclusion_is_campaign_scope_only":True,"targeting_is_not_employer_endorsement":True,"targeting_is_not_sponsorship_evidence":True}}

def employer_campaign_fit(employer_id:str,targets:Iterable[Mapping[str,Any]])->dict[str,Any]:
    policy=campaign_employer_policy(targets)
    if employer_id in policy["excluded"]: disposition="excluded"
    elif employer_id in policy["priority"]: disposition="priority"
    elif employer_id in policy["watch"]: disposition="watch"
    else: disposition="open"
    return {"employer_id":employer_id,"disposition":disposition,"eligible_for_campaign_discovery":disposition!="excluded","priority_boost":disposition=="priority","watch_for_new_vacancies":disposition in ("priority","watch"),"safety":{"campaign_fit_is_not_job_eligibility":True,"automatic_application_submission":False,"sponsorship_not_inferred":True}}
