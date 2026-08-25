from __future__ import annotations
from datetime import datetime,timezone
from flask import Blueprint,jsonify,request
from app.services.account_identity import get_verified_session_email
from app.services.job_employer_dashboard import build_employer_dashboard
from app.services.supabase_client import get_supabase

bp=Blueprint("job_employers",__name__)
EMPLOYERS="relocation_job_employers";LINKS="relocation_job_employer_vacancies";JOBS="relocation_jobs";LIFECYCLES="relocation_job_application_lifecycles";INTERACTIONS="relocation_job_employer_interactions";TARGETS="relocation_job_campaign_employer_targets";CAMPAIGNS="relocation_job_search_campaigns"
TARGET_TYPES={"priority","watch","excluded"}

def _now():return datetime.now(timezone.utc).isoformat()
def _account():
 email=get_verified_session_email();return (email,None) if email else (None,(jsonify({"ok":False,"error":"verified_session_required"}),401))
def _employer(employer_id):return get_supabase().table(EMPLOYERS).select("*").eq("id",employer_id).maybe_single().execute().data

@bp.get("/employers")
def list_employers():
 email,error=_account()
 if error:return error
 rows=get_supabase().table(EMPLOYERS).select("*").order("canonical_name").execute().data or []
 targets=get_supabase().table(TARGETS).select("*").eq("email",email).eq("active",True).execute().data or []
 by_employer={}
 for target in targets:by_employer.setdefault(target.get("employer_id"),[]).append(target)
 items=[{**row,"campaign_targets":by_employer.get(row.get("id"),[])} for row in rows]
 return jsonify({"ok":True,"count":len(items),"items":items,"identity_warning":"Canonical identity is not verification, sponsorship evidence or employer interest."})

@bp.post("/campaigns/<campaign_id>/employers/<employer_id>/target")
def set_campaign_target(campaign_id,employer_id):
 email,error=_account()
 if error:return error
 body=request.get_json(silent=True) or {};target_type=str(body.get("target_type") or "").strip().lower()
 if target_type not in TARGET_TYPES|{"remove"}:return jsonify({"ok":False,"error":"unsupported_target_type"}),400
 db=get_supabase();campaign=db.table(CAMPAIGNS).select("id").eq("id",campaign_id).eq("email",email).maybe_single().execute().data
 if not campaign:return jsonify({"ok":False,"error":"job_search_campaign_not_found"}),404
 if not _employer(employer_id):return jsonify({"ok":False,"error":"employer_not_found"}),404
 existing=db.table(TARGETS).select("*").eq("campaign_id",campaign_id).eq("employer_id",employer_id).eq("email",email).maybe_single().execute().data
 if target_type=="remove":
  if existing:db.table(TARGETS).update({"active":False,"updated_at":_now()}).eq("id",existing["id"]).eq("email",email).execute()
  return jsonify({"ok":True,"removed":True,"campaign_id":campaign_id,"employer_id":employer_id})
 row={"campaign_id":campaign_id,"employer_id":employer_id,"email":email,"target_type":target_type,"reason":str(body.get("reason") or "").strip() or None,"source":"user","active":True,"updated_at":_now()}
 if existing:saved=(db.table(TARGETS).update(row).eq("id",existing["id"]).eq("email",email).execute().data or [row])[0]
 else:saved=(db.table(TARGETS).insert({**row,"created_at":_now()}).execute().data or [row])[0]
 return jsonify({"ok":True,"target":saved,"safety":{"employer_verified":False,"sponsorship_proven":False,"employer_interest_proven":False}})

@bp.get("/employers/<employer_id>/dashboard")
def dashboard(employer_id):
 email,error=_account()
 if error:return error
 employer=_employer(employer_id)
 if not employer:return jsonify({"ok":False,"error":"employer_not_found"}),404
 links=get_supabase().table(LINKS).select("*").eq("employer_id",employer_id).execute().data or []
 vacancies=[];applications=[]
 for link in links:
  job_id=link.get("job_id")
  if not job_id:continue
  job=get_supabase().table(JOBS).select("*").eq("id",job_id).maybe_single().execute().data
  if job:vacancies.append(job)
  applications.extend(get_supabase().table(LIFECYCLES).select("*").eq("email",email).eq("job_id",job_id).execute().data or [])
 interactions=get_supabase().table(INTERACTIONS).select("*").eq("email",email).eq("employer_id",employer_id).order("occurred_at",desc=True).execute().data or []
 targets=get_supabase().table(TARGETS).select("*").eq("email",email).eq("employer_id",employer_id).eq("active",True).execute().data or []
 vacancy_fit=float(request.args.get("vacancy_fit") or 0);evidence_quality=float(request.args.get("evidence_quality") or 0);observed_outcome=float(request.args.get("observed_outcome_signal") or 0);freshness=float(request.args.get("freshness") or 0)
 disposition="open"
 if any(x.get("target_type")=="excluded" for x in targets):disposition="excluded"
 elif any(x.get("target_type")=="priority" for x in targets):disposition="priority"
 elif any(x.get("target_type")=="watch" for x in targets):disposition="watch"
 result=build_employer_dashboard(employer=employer,vacancies=vacancies,applications=applications,interactions=interactions,campaign_targets=targets,ranking_inputs={"vacancy_fit":vacancy_fit,"evidence_quality":evidence_quality,"observed_outcome_signal":observed_outcome,"freshness":freshness,"campaign_disposition":disposition})
 return jsonify({"ok":True,**result})
