from __future__ import annotations
from flask import Blueprint,jsonify,request
from app.services.account_identity import get_verified_session_email
from app.services.job_employer_dashboard import build_employer_dashboard
from app.services.supabase_client import get_supabase

bp=Blueprint("job_employers",__name__)
EMPLOYERS="relocation_job_employers";LINKS="relocation_job_employer_vacancies";JOBS="relocation_jobs";LIFECYCLES="relocation_job_application_lifecycles";INTERACTIONS="relocation_job_employer_interactions";TARGETS="relocation_job_campaign_employer_targets"

def _account():
 email=get_verified_session_email();return (email,None) if email else (None,(jsonify({"ok":False,"error":"verified_session_required"}),401))
def _employer(employer_id):return get_supabase().table(EMPLOYERS).select("*").eq("id",employer_id).maybe_single().execute().data

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
