from __future__ import annotations
from typing import Any,Mapping
from app.services.job_employer_intelligence import same_employer

CONTRACT_VERSION="b19.11.2-v1"

def resolve_employer(vacancy:Mapping[str,Any],candidate:Mapping[str,Any])->dict[str,Any]:
    vacancy_employer={"name":vacancy.get("company_name") or vacancy.get("company") or vacancy.get("employer"),"domain":vacancy.get("company_domain") or vacancy.get("employer_domain") or vacancy.get("company_url"),"country":vacancy.get("country") or vacancy.get("location_country")}
    comparison=same_employer(vacancy_employer,candidate)
    if not comparison["matched"]:
        return {"contract_version":CONTRACT_VERSION,"resolved":False,"reason":"identity_not_safely_resolved","review_required":True,"safety":{"fuzzy_auto_merge":False,"claims_inherited":False}}
    basis=comparison["basis"]
    return {"contract_version":CONTRACT_VERSION,"resolved":True,"resolution_basis":basis,"resolution_confidence":"high","canonical_key":comparison["right"]["canonical_key"],"review_required":False,"safety":{"identity_link_only":True,"claims_inherited":False,"sponsorship_inferred":False,"relocation_support_inferred":False,"employer_verified_by_link":False}}

def domain_verification_update(*,domain:str|None,evidence_url:str|None,observed_at:str|None)->dict[str,Any]:
    verified=bool(domain and evidence_url and observed_at)
    return {"domain_verified":verified,"domain_evidence_url":evidence_url if verified else None,"domain_evidence_observed_at":observed_at if verified else None,"safety":{"domain_verified_means_domain_relationship_only":True,"employer_legitimacy_not_guaranteed":True}}
