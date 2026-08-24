from __future__ import annotations

from typing import Any, Iterable, Mapping

CONTRACT_VERSION="b19.10.3-v1"


def _text(value: Any)->str:
    return str(value or "").strip()

def _values(job: Mapping[str,Any],keys: tuple[str,...])->list[str]:
    result=[]
    for key in keys:
        value=job.get(key)
        if isinstance(value,(list,tuple,set)): result.extend(_text(item) for item in value if _text(item))
        elif _text(value): result.append(_text(value))
    return result

def _matches(targets:list[str],values:list[str])->bool:
    if not targets:return True
    folded=[value.casefold() for value in values]
    return any(target.casefold() in value or value in target.casefold() for target in targets for value in folded)

def campaign_match(campaign:Mapping[str,Any],job:Mapping[str,Any])->dict[str,Any]:
    countries=[_text(x) for x in campaign.get("target_countries") or []]
    occupations=[_text(x) for x in campaign.get("target_occupations") or []]
    employers=[_text(x) for x in campaign.get("target_employers") or []]
    country_match=_matches(countries,_values(job,("country","location_country","country_code")))
    occupation_match=_matches(occupations,_values(job,("occupation","occupation_title","title")))
    employer_match=_matches(employers,_values(job,("company","company_name","employer")))
    matched=sum((country_match,occupation_match,employer_match));required=2 if employers else 2
    return {"contract_version":CONTRACT_VERSION,"matched":country_match and occupation_match and (employer_match if employers else True),"score":round((matched/3)*100),"dimensions":{"country":country_match,"occupation":occupation_match,"employer":employer_match},"safety":{"match_is_not_eligibility":True,"match_is_not_sponsorship_evidence":True,"match_is_not_application_authorization":True}}

def progress(campaign:Mapping[str,Any],vacancies:Iterable[Mapping[str,Any]],applications:Iterable[Mapping[str,Any]])->dict[str,Any]:
    vacancy_rows=list(vacancies);application_rows=list(applications)
    states={}
    for row in application_rows:
        state=_text(row.get("pipeline_state") or row.get("state") or "unknown").lower();states[state]=states.get(state,0)+1
    interviews=sum(states.get(key,0) for key in ("interview","interviewing"));offers=sum(states.get(key,0) for key in ("offer","offered","hired"));terminal=sum(states.get(key,0) for key in ("rejected","withdrawn","closed","hired"))
    return {"contract_version":CONTRACT_VERSION,"campaign_id":campaign.get("id"),"status":campaign.get("status"),"vacancies_associated":len(vacancy_rows),"applications_tracked":len(application_rows),"pipeline_states":states,"interviews":interviews,"offers_or_hires":offers,"terminal_outcomes":terminal,"safety":{"progress_is_descriptive":True,"employer_response_not_inferred":True}}
