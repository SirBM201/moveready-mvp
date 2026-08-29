from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.job_application_portfolio import CONTRACT_VERSION, EXECUTION_COMMAND_VERSION, build_portfolio_item, sort_portfolio
from app.services.job_application_portfolio_action_feed import CONTRACT_VERSION as ACTION_FEED_VERSION, build_portfolio_action_feed, what_should_i_do_next
from app.services.job_application_portfolio_reconciliation import build_corrective_plan, validate_corrective_operation
from app.services.supabase_client import get_supabase

bp=Blueprint("job_application_portfolio",__name__)
JOB_TABLE="relocation_jobs";READINESS_TABLE="relocation_job_application_readiness";DRAFT_TABLE="relocation_job_application_drafts";HANDOFF_TABLE="relocation_job_application_handoffs";LIFECYCLE_TABLE="relocation_job_application_lifecycles";FOLLOWUP_TABLE="relocation_job_application_followups"
def _account():
    email=get_verified_session_email();return (email,None) if email else (None,(jsonify({"ok":False,"error":"verified_session_required"}),401))
def _owned_rows(table,email):return get_supabase().table(table).select("*").eq("email",email).execute().data or []
def _jobs(ids):return [] if not ids else (get_supabase().table(JOB_TABLE).select("*").in_("id",sorted(ids)).execute().data or [])
def _group(rows):
    grouped=defaultdict(list)
    for row in rows:
        key=str(row.get("job_id") or "").strip()
        if key:grouped[key].append(row)
    return grouped
def _latest_readiness(rows):return {str(r.get("job_id")):r for r in rows if r.get("job_id")}
def _job_artifacts(email,job_id):
    s=get_supabase();return (s.table(READINESS_TABLE).select("*").eq("job_id",job_id).eq("email",email).maybe_single().execute().data,s.table(DRAFT_TABLE).select("*").eq("job_id",job_id).eq("email",email).execute().data or [],s.table(HANDOFF_TABLE).select("*").eq("job_id",job_id).eq("email",email).execute().data or [],s.table(LIFECYCLE_TABLE).select("*").eq("job_id",job_id).eq("email",email).execute().data or [],s.table(FOLLOWUP_TABLE).select("*").eq("job_id",job_id).eq("email",email).execute().data or [])
def _portfolio(email):
    rr=_owned_rows(READINESS_TABLE,email);dr=_owned_rows(DRAFT_TABLE,email);hr=_owned_rows(HANDOFF_TABLE,email);lr=_owned_rows(LIFECYCLE_TABLE,email);fr=_owned_rows(FOLLOWUP_TABLE,email);r=_latest_readiness(rr);d=_group(dr);h=_group(hr);l=_group(lr);f=_group(fr);ids=set(r)|set(d)|set(h)|set(l)|set(f);jm={str(x.get("id")):x for x in _jobs(ids) if x.get("id")};return sort_portfolio([build_portfolio_item(job=jm.get(j) or {"id":j},readiness=r.get(j),drafts=d.get(j,[]),handoffs=h.get(j,[]),lifecycles=l.get(j,[]),followups=f.get(j,[])) for j in ids])

@bp.get("/application-portfolio")
def application_portfolio():
    email,error=_account()
    if error:return error
    items=_portfolio(email);state=str(request.args.get("state") or "").strip().lower()
    if state:items=[x for x in items if str(x.get("pipeline_state") or "").lower()==state]
    if str(request.args.get("actionable") or "").lower() in {"1","true","yes"}:items=[x for x in items if x.get("next_action",{}).get("type")!="none"]
    return jsonify({"ok":True,"contract_version":CONTRACT_VERSION,"execution_command_version":EXECUTION_COMMAND_VERSION,"count":len(items),"items":items,"summary":{"terminal":sum(1 for x in items if x.get("terminal")),"actionable":sum(1 for x in items if x.get("next_action",{}).get("type")!="none"),"blocking":sum(1 for x in items if x.get("next_action",{}).get("blocking")),"ready_to_apply":sum(1 for x in items if x.get("pipeline_state")=="ready_to_apply"),"in_progress":sum(1 for x in items if x.get("pipeline_state") in {"draft_ready","handoff_ready","submitted","screening","interview","offer"}),"due_followups":sum(int(x.get("due_followup_count") or 0) for x in items),"reconciliation_required":sum(1 for x in items if x.get("reconciliation",{}).get("requires_write_reconciliation"))},"safety":{"read_model_only":True,"auto_submit_allowed":False,"auto_contact_employer":False,"eligibility_inference_allowed":False}})

@bp.get("/application-portfolio/actions")
def application_portfolio_actions():
    email,error=_account()
    if error:return error
    actions=build_portfolio_action_feed(_portfolio(email));return jsonify({"ok":True,"contract_version":ACTION_FEED_VERSION,"count":len(actions),"actions":actions,"next":actions[0] if actions else None})

@bp.get("/application-portfolio/next-action")
def application_portfolio_next_action():
    email,error=_account()
    if error:return error
    items=_portfolio(email);return jsonify({"ok":True,"contract_version":ACTION_FEED_VERSION,"action":what_should_i_do_next(items),"portfolio_count":len(items)})

@bp.get("/application-portfolio/<job_id>")
def application_portfolio_item(job_id):
    email,error=_account()
    if error:return error
    r,d,h,l,f=_job_artifacts(email,job_id)
    if not any([r,d,h,l,f]):return jsonify({"ok":False,"error":"application_portfolio_item_not_found"}),404
    jobs=_jobs({job_id});return jsonify({"ok":True,"contract_version":CONTRACT_VERSION,"item":build_portfolio_item(job=jobs[0] if jobs else {"id":job_id},readiness=r,drafts=d,handoffs=h,lifecycles=l,followups=f)})

@bp.post("/application-portfolio/<job_id>/reconcile")
def reconcile_application_portfolio(job_id):
    email,error=_account()
    if error:return error
    r,d,h,l,f=_job_artifacts(email,job_id)
    if not any([r,d,h,l,f]):return jsonify({"ok":False,"error":"application_portfolio_item_not_found"}),404
    lifecycle=max(l,key=lambda x:str(x.get("state_changed_at") or x.get("updated_at") or "")) if l else None;plan=build_corrective_plan(lifecycle=lifecycle,followups=f)
    if not plan["operations"]:return jsonify({"ok":True,"changed":False,"plan":plan})
    changed=[];now=datetime.now(timezone.utc).isoformat()
    for op in plan["operations"]:
        validation=validate_corrective_operation(op)
        if not validation["ok"]:return jsonify(validation),409
        for fid,status in op["followup_updates"].items():get_supabase().table(FOLLOWUP_TABLE).update({"status":status,"updated_at":now}).eq("id",fid).eq("email",email).eq("job_id",job_id).execute();changed.append(fid)
    return jsonify({"ok":True,"changed":bool(changed),"updated_followup_ids":changed,"plan":plan,"safety":{"employer_contact_performed":False,"application_submission_performed":False,"lifecycle_state_modified":False}})
