from __future__ import annotations

from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.job_search_campaign import CONTRACT_VERSION, CAMPAIGN_STATUSES, validate_campaign
from app.services.supabase_client import get_supabase

bp=Blueprint("job_search_campaigns",__name__)
CAMPAIGN_TABLE="relocation_job_search_campaigns"
VACANCY_TABLE="relocation_job_search_campaign_vacancies"
JOB_TABLE="relocation_jobs"

def _now(): return datetime.now(timezone.utc).isoformat()
def _account():
    email=get_verified_session_email()
    return (email,None) if email else (None,(jsonify({"ok":False,"error":"verified_session_required"}),401))
def _payload():
    value=request.get_json(silent=True);return value if isinstance(value,dict) else {}
def _campaign(campaign_id,email): return get_supabase().table(CAMPAIGN_TABLE).select("*").eq("id",campaign_id).eq("email",email).maybe_single().execute().data

def _persistable(normalized):
    return {key:normalized.get(key) for key in ("name","status","target_countries","target_occupations","target_employers","work_authorized_countries","sponsorship_required","relocation_support_preferred","search_intensity","notes")}

@bp.post("/campaigns")
def create_campaign():
    email,error=_account()
    if error:return error
    try: validation=validate_campaign(_payload())
    except ValueError as exc:return jsonify({"ok":False,"error":str(exc),"contract_version":CONTRACT_VERSION}),400
    if not validation["ok"]:return jsonify(validation),400
    now=_now();row={**_persistable(validation["campaign"]),"email":email,"contract_version":CONTRACT_VERSION,"created_at":now,"updated_at":now}
    created=(get_supabase().table(CAMPAIGN_TABLE).insert(row).execute().data or [None])[0]
    return jsonify({"ok":True,"campaign":created,"warnings":validation["warnings"],"contract_version":CONTRACT_VERSION}),201

@bp.get("/campaigns")
def list_campaigns():
    email,error=_account()
    if error:return error
    status=str(request.args.get("status") or "").strip().lower();query=get_supabase().table(CAMPAIGN_TABLE).select("*").eq("email",email)
    if status:
        if status not in CAMPAIGN_STATUSES:return jsonify({"ok":False,"error":"unsupported_campaign_status"}),400
        query=query.eq("status",status)
    rows=query.order("updated_at",desc=True).execute().data or []
    return jsonify({"ok":True,"count":len(rows),"items":rows,"contract_version":CONTRACT_VERSION})

@bp.get("/campaigns/<campaign_id>")
def get_campaign(campaign_id):
    email,error=_account()
    if error:return error
    row=_campaign(campaign_id,email)
    if not row:return jsonify({"ok":False,"error":"job_search_campaign_not_found"}),404
    vacancies=get_supabase().table(VACANCY_TABLE).select("*").eq("campaign_id",campaign_id).eq("email",email).order("created_at",desc=True).execute().data or []
    return jsonify({"ok":True,"campaign":row,"vacancies":vacancies,"contract_version":CONTRACT_VERSION})

@bp.patch("/campaigns/<campaign_id>")
def update_campaign(campaign_id):
    email,error=_account()
    if error:return error
    current=_campaign(campaign_id,email)
    if not current:return jsonify({"ok":False,"error":"job_search_campaign_not_found"}),404
    merged={**current,**_payload()}
    try: validation=validate_campaign(merged)
    except ValueError as exc:return jsonify({"ok":False,"error":str(exc),"contract_version":CONTRACT_VERSION}),400
    if not validation["ok"]:return jsonify(validation),400
    update={**_persistable(validation["campaign"]),"contract_version":CONTRACT_VERSION,"updated_at":_now()}
    updated=(get_supabase().table(CAMPAIGN_TABLE).update(update).eq("id",campaign_id).eq("email",email).execute().data or [None])[0]
    return jsonify({"ok":True,"campaign":updated,"warnings":validation["warnings"],"contract_version":CONTRACT_VERSION})

@bp.delete("/campaigns/<campaign_id>")
def delete_campaign(campaign_id):
    email,error=_account()
    if error:return error
    current=_campaign(campaign_id,email)
    if not current:return jsonify({"ok":False,"error":"job_search_campaign_not_found"}),404
    get_supabase().table(CAMPAIGN_TABLE).delete().eq("id",campaign_id).eq("email",email).execute()
    return jsonify({"ok":True,"deleted":True,"campaign_id":campaign_id})

@bp.post("/campaigns/<campaign_id>/vacancies")
def associate_vacancy(campaign_id):
    email,error=_account()
    if error:return error
    if not _campaign(campaign_id,email):return jsonify({"ok":False,"error":"job_search_campaign_not_found"}),404
    body=_payload();job_id=str(body.get("job_id") or "").strip()
    if not job_id:return jsonify({"ok":False,"error":"job_id_required"}),400
    job=get_supabase().table(JOB_TABLE).select("id").eq("id",job_id).maybe_single().execute().data
    if not job:return jsonify({"ok":False,"error":"job_not_found"}),404
    existing=get_supabase().table(VACANCY_TABLE).select("*").eq("campaign_id",campaign_id).eq("job_id",job_id).eq("email",email).maybe_single().execute().data
    if existing:return jsonify({"ok":True,"created":False,"association":existing})
    row={"campaign_id":campaign_id,"email":email,"job_id":job_id,"association_reason":str(body.get("association_reason") or "").strip() or None,"user_confirmed":True,"created_at":_now()}
    created=(get_supabase().table(VACANCY_TABLE).insert(row).execute().data or [None])[0]
    return jsonify({"ok":True,"created":True,"association":created,"safety":{"vacancy_claims_verified_by_association":False,"application_submitted":False}}),201

@bp.delete("/campaigns/<campaign_id>/vacancies/<job_id>")
def remove_vacancy(campaign_id,job_id):
    email,error=_account()
    if error:return error
    if not _campaign(campaign_id,email):return jsonify({"ok":False,"error":"job_search_campaign_not_found"}),404
    get_supabase().table(VACANCY_TABLE).delete().eq("campaign_id",campaign_id).eq("job_id",job_id).eq("email",email).execute()
    return jsonify({"ok":True,"removed":True,"campaign_id":campaign_id,"job_id":job_id})
