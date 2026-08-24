from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

CONTRACT_VERSION="b19.11.3-v1"
TERMINAL_STATES={"rejected","withdrawn","hired","closed"}

def _iso(value:Any)->str|None:
    if value is None:return None
    if isinstance(value,datetime):return value.astimezone(timezone.utc).isoformat()
    text=str(value).strip();return text or None

def employer_timeline(*,employer:Mapping[str,Any],vacancies:Iterable[Mapping[str,Any]]=(),applications:Iterable[Mapping[str,Any]]=(),interactions:Iterable[Mapping[str,Any]]=())->dict[str,Any]:
    events=[]
    for row in vacancies:
        events.append({"event_type":"vacancy_observed","occurred_at":_iso(row.get("observed_at") or row.get("created_at")),"job_id":row.get("job_id") or row.get("id"),"title":row.get("title"),"evidence_url":row.get("source_url") or row.get("evidence_url"),"source":"vacancy"})
    for row in applications:
        events.append({"event_type":"application_state","occurred_at":_iso(row.get("occurred_at") or row.get("updated_at") or row.get("created_at")),"job_id":row.get("job_id"),"application_id":row.get("application_id") or row.get("id"),"state":row.get("state") or row.get("status"),"source":"application_lifecycle"})
    for row in interactions:
        events.append({"event_type":str(row.get("interaction_type") or "interaction"),"occurred_at":_iso(row.get("occurred_at") or row.get("created_at")),"job_id":row.get("job_id"),"application_id":row.get("application_id"),"direction":row.get("direction"),"channel":row.get("channel"),"summary":row.get("summary"),"evidence_url":row.get("evidence_url"),"source":"recorded_interaction"})
    events.sort(key=lambda x:(x.get("occurred_at") is None,x.get("occurred_at") or ""),reverse=True)
    return {"contract_version":CONTRACT_VERSION,"employer_id":employer.get("id"),"canonical_key":employer.get("canonical_key"),"events":events,"event_count":len(events),"safety":{"recorded_history_only":True,"unrecorded_contact_not_inferred":True,"employer_intent_not_inferred":True,"sponsorship_not_inferred":True}}

def opportunity_history(vacancies:Iterable[Mapping[str,Any]],applications:Iterable[Mapping[str,Any]])->dict[str,Any]:
    vacancy_rows=list(vacancies);application_rows=list(applications)
    states={};terminal=0
    for row in application_rows:
        state=str(row.get("state") or row.get("status") or "unknown").lower();states[state]=states.get(state,0)+1
        if state in TERMINAL_STATES:terminal+=1
    return {"vacancies_observed":len(vacancy_rows),"applications_recorded":len(application_rows),"application_states":states,"terminal_outcomes":terminal,"safety":{"counts_are_descriptive":True,"success_rate_not_inferred_without_denominator_contract":True}}
