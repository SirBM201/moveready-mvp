from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from flask import Blueprint, jsonify, request
from app.services.account_identity import get_verified_session_email
from app.services.job_application_readiness import CONTRACT_VERSION, READINESS_STATES, evaluate_application_readiness, reconcile_readiness, transition_readiness, vacancy_fingerprint
from app.services.job_visibility import job_is_visible_to_account
from app.services.supabase_client import get_supabase

bp = Blueprint("job_application_readiness", __name__)
TABLE = "relocation_job_application_readiness"
def _now(): return datetime.now(timezone.utc).isoformat()
def _account() -> Tuple[Optional[str], Optional[Tuple[Any,int]]]:
    email=get_verified_session_email(); return (email,None) if email else (None,(jsonify({"ok":False,"error":"verified_session_required"}),401))
def _payload():
    value=request.get_json(silent=True); return value if isinstance(value,dict) else {}
def _job(job_id,email):
    row=get_supabase().table("relocation_jobs").select("*").eq("id",job_id).maybe_single().execute().data
    return row if job_is_visible_to_account(row,email) else None
def _record(job_id,email): return get_supabase().table(TABLE).select("*").eq("job_id",job_id).eq("email",email).maybe_single().execute().data
def _materials(row):
    row=row or {}; return {"cv_id":row.get("cv_id"),"cover_letter_id":row.get("cover_letter_id"),"application_answers_ready":bool(row.get("application_answers_ready"))}
def _profile(email):
    row=get_supabase().table("relocation_job_search_profiles").select("*").eq("email",email).maybe_single().execute().data or {}
    row["work_authorization"]=row.get("work_authorization_status") or row.get("work_authorization"); return row
def _evaluation(job,email,record):
    existing=dict(record or {}); existing["requirements_verified"]=bool(existing.get("requirements_verified")); existing["submission_confirmed"]=bool(existing.get("submission_confirmed_at"))
    if existing.get("application_started_at") and not existing.get("status"): existing["status"]="application_started"
    if existing.get("submission_confirmed_at"): existing["status"]="applied"
    vacancy=dict(job); vacancy["requirements_verified"]=existing["requirements_verified"]
    return evaluate_application_readiness(vacancy,profile=_profile(email),materials=_materials(record),existing_application=existing)
def _persist(job_id,email,evaluation,extra=None):
    row={"email":email,"job_id":job_id,"state":evaluation["state"],"issues":evaluation["issues"],"blocking_issue_count":evaluation["blocking_issue_count"],"contract_version":CONTRACT_VERSION,"updated_at":_now()}; row.update(extra or {})
    response=get_supabase().table(TABLE).upsert(row,on_conflict="email,job_id").execute(); return (response.data or [None])[0] or _record(job_id,email) or row
def _reconcile(job,email,record=None):
    record=record if record is not None else _record(str(job["id"]),email); evaluation=_evaluation(job,email,record); fp=vacancy_fingerprint(job); rec=reconcile_readiness(record,evaluation,fp); now=_now()
    evaluation={**evaluation,"state":rec["state"]}
    extra={"vacancy_fingerprint":fp,"last_reconciled_at":now,"reconciliation_count":int((record or {}).get("reconciliation_count") or 0)+1}
    if rec["vacancy_changed"]: extra["vacancy_changed_at"]=now
    if rec["invalidated"]: extra.update({"previous_state":rec["previous_state"],"invalidated_at":now,"invalidation_reason":rec["invalidation_reason"],"user_confirmed_ready_at":None})
    persisted=_persist(str(job["id"]),email,evaluation,extra); return evaluation,persisted,rec

@bp.get("/jobs/<job_id>/readiness")
def get_readiness(job_id):
    email,error=_account()
    if error:return error
    job=_job(job_id,email)
    if not job:return jsonify({"ok":False,"error":"job_not_found"}),404
    evaluation,persisted,rec=_reconcile(job,email)
    return jsonify({"ok":True,"job_id":job_id,"readiness":evaluation,"record":persisted,"reconciliation":rec})

@bp.patch("/jobs/<job_id>/readiness/materials")
def update_materials(job_id):
    email,error=_account()
    if error:return error
    job=_job(job_id,email)
    if not job:return jsonify({"ok":False,"error":"job_not_found"}),404
    body=_payload(); extra={}
    for field in ("cv_id","cover_letter_id"):
        if field in body:
            asset_id=str(body.get(field) or "").strip() or None
            if asset_id:
                owned=get_supabase().table("relocation_job_resume_assets").select("id").eq("id",asset_id).eq("email",email).maybe_single().execute().data
                if not owned:return jsonify({"ok":False,"error":"resume_asset_not_owned","field":field}),400
            extra[field]=asset_id
    for field in ("application_answers_ready","requirements_verified"):
        if field in body:extra[field]=bool(body.get(field))
    current=_record(job_id,email) or {}; merged={**current,**extra}; evaluation=_evaluation(job,email,merged); fp=vacancy_fingerprint(job); rec=reconcile_readiness(merged,evaluation,fp); evaluation={**evaluation,"state":rec["state"]}; extra.update({"vacancy_fingerprint":fp,"last_reconciled_at":_now(),"reconciliation_count":int(current.get("reconciliation_count") or 0)+1}); persisted=_persist(job_id,email,evaluation,extra)
    return jsonify({"ok":True,"job_id":job_id,"readiness":evaluation,"record":persisted,"reconciliation":rec})

@bp.post("/jobs/<job_id>/readiness/transition")
def transition(job_id):
    email,error=_account()
    if error:return error
    job=_job(job_id,email)
    if not job:return jsonify({"ok":False,"error":"job_not_found"}),404
    body=_payload(); target=str(body.get("target_state") or "").strip().lower()
    if target not in READINESS_STATES:return jsonify({"ok":False,"error":"invalid_readiness_state"}),400
    evaluation,record,rec=_reconcile(job,email); current=str(record.get("state") or evaluation["state"])
    result=transition_readiness(current,target,user_confirmed=bool(body.get("user_confirmed")))
    if not result["ok"]:return jsonify({"ok":False,**result,"readiness":evaluation,"reconciliation":rec}),409
    extra={"state":target}; now=_now()
    if target=="ready_to_apply":extra["user_confirmed_ready_at"]=now
    elif target=="application_started":extra["application_started_at"]=now
    elif target=="applied":extra["submission_confirmed_at"]=now
    elif target=="closed":extra["closed_at"]=now
    persisted=_persist(job_id,email,{**evaluation,"state":target},extra); return jsonify({"ok":True,"job_id":job_id,"transition":result,"record":persisted})

@bp.post("/jobs/<job_id>/readiness/reconcile")
def reconcile_one(job_id):
    email,error=_account()
    if error:return error
    job=_job(job_id,email)
    if not job:return jsonify({"ok":False,"error":"job_not_found"}),404
    evaluation,persisted,rec=_reconcile(job,email); return jsonify({"ok":True,"job_id":job_id,"readiness":evaluation,"record":persisted,"reconciliation":rec})

@bp.get("/readiness")
def list_readiness():
    email,error=_account()
    if error:return error
    state=str(request.args.get("state") or "").strip().lower(); query=get_supabase().table(TABLE).select("*").eq("email",email)
    if state:
        if state not in READINESS_STATES:return jsonify({"ok":False,"error":"invalid_readiness_state"}),400
        query=query.eq("state",state)
    rows=query.order("updated_at",desc=True).execute().data or []; visible=[]
    for row in rows:
        job=_job(str(row.get("job_id") or ""),email)
        if job:
            evaluation,persisted,rec=_reconcile(job,email,row); visible.append({"record":persisted,"job":job,"readiness":evaluation,"reconciliation":rec})
    return jsonify({"ok":True,"count":len(visible),"items":visible,"contract_version":CONTRACT_VERSION})
