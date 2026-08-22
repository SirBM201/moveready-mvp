from __future__ import annotations

from datetime import datetime, timezone
from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.job_application_followup import CONTRACT_VERSION as FOLLOWUP_VERSION, validate_followup
from app.services.job_application_followup_reconciliation import CONTRACT_VERSION, active_duplicate, reconcile_due_status, reconcile_outcome, terminal_followup_updates
from app.services.job_application_lifecycle_reconciliation import build_reconciliation_event
from app.services.supabase_client import get_supabase

bp=Blueprint("job_application_followups",__name__)
FOLLOWUP_TABLE="relocation_job_application_followups";LIFECYCLE_TABLE="relocation_job_application_lifecycles";EVENT_TABLE="relocation_job_application_lifecycle_events"
def _now(): return datetime.now(timezone.utc).isoformat()
def _account():
    email=get_verified_session_email()
    return (email,None) if email else (None,(jsonify({"ok":False,"error":"verified_session_required"}),401))
def _payload():
    value=request.get_json(silent=True);return value if isinstance(value,dict) else {}
def _lifecycle(lifecycle_id,email): return get_supabase().table(LIFECYCLE_TABLE).select("*").eq("id",lifecycle_id).eq("email",email).maybe_single().execute().data
def _followups(email,lifecycle_id=None):
    q=get_supabase().table(FOLLOWUP_TABLE).select("*").eq("email",email)
    if lifecycle_id:q=q.eq("lifecycle_id",lifecycle_id)
    return q.order("scheduled_for").execute().data or []

def _reconcile_rows(email,rows):
    changed=0;result=[]
    for row in rows:
        rec=reconcile_due_status(row)
        if rec.get("ok") and rec.get("changed"):
            updated=(get_supabase().table(FOLLOWUP_TABLE).update({"status":rec["status"],"updated_at":_now()}).eq("id",row["id"]).eq("email",email).execute().data or [row])[0]
            row=updated;changed+=1
        result.append(row)
    return result,changed

@bp.post("/application-lifecycles/<lifecycle_id>/followups")
def create_followup(lifecycle_id):
    email,error=_account()
    if error:return error
    lifecycle=_lifecycle(lifecycle_id,email)
    if not lifecycle:return jsonify({"ok":False,"error":"application_lifecycle_not_found"}),404
    body=_payload();validation=validate_followup(lifecycle_state=lifecycle.get("state"),action_type=body.get("action_type"),scheduled_for=body.get("scheduled_for"))
    if not validation["ok"]:return jsonify(validation),409
    existing=_followups(email,lifecycle_id)
    if active_duplicate(existing,lifecycle_id=lifecycle_id,action_type=validation["action_type"]):return jsonify({"ok":False,"error":"active_followup_already_exists","contract_version":CONTRACT_VERSION}),409
    now=_now();row={"email":email,"lifecycle_id":lifecycle_id,"job_id":lifecycle.get("job_id"),"action_type":validation["action_type"],"status":"scheduled","scheduled_for":validation["scheduled_for"],"note":str(body.get("note") or "").strip() or None,"user_confirmed":True,"contract_version":FOLLOWUP_VERSION,"created_at":now,"updated_at":now}
    created=(get_supabase().table(FOLLOWUP_TABLE).insert(row).execute().data or [None])[0]
    return jsonify({"ok":True,"followup":created,"safety":{"auto_contact_employer":False}}),201

@bp.get("/application-followups/due")
def due_actions():
    email,error=_account()
    if error:return error
    rows=_followups(email);rows,changed=_reconcile_rows(email,rows)
    due=[row for row in rows if row.get("status")=="due"]
    return jsonify({"ok":True,"count":len(due),"items":due,"reconciled":changed,"contract_version":CONTRACT_VERSION,"safety":{"actions_are_user_tasks":True,"auto_contact_employer":False}})

@bp.post("/application-followups/reconcile")
def reconcile_followups():
    email,error=_account()
    if error:return error
    rows=_followups(email);rows,changed=_reconcile_rows(email,rows);superseded=0
    lifecycle_ids={str(row.get("lifecycle_id")) for row in rows if row.get("lifecycle_id")}
    for lifecycle_id in lifecycle_ids:
        lifecycle=_lifecycle(lifecycle_id,email)
        if not lifecycle:continue
        owned=[row for row in rows if str(row.get("lifecycle_id"))==lifecycle_id]
        updates=terminal_followup_updates(owned,lifecycle.get("state"))
        for followup_id,status in updates.items():
            get_supabase().table(FOLLOWUP_TABLE).update({"status":status,"updated_at":_now()}).eq("id",followup_id).eq("email",email).execute();superseded+=1
    return jsonify({"ok":True,"reconciled_due":changed,"superseded":superseded,"contract_version":CONTRACT_VERSION})

@bp.post("/application-followups/<followup_id>/complete")
def complete_followup(followup_id):
    email,error=_account()
    if error:return error
    row=get_supabase().table(FOLLOWUP_TABLE).select("*").eq("id",followup_id).eq("email",email).maybe_single().execute().data
    if not row:return jsonify({"ok":False,"error":"application_followup_not_found"}),404
    if row.get("status") not in {"scheduled","due"}:return jsonify({"ok":False,"error":"application_followup_not_active"}),409
    lifecycle=_lifecycle(str(row.get("lifecycle_id")),email)
    if not lifecycle:return jsonify({"ok":False,"error":"application_lifecycle_not_found"}),404
    body=_payload();outcome=str(body.get("outcome") or "no_response");evidence=body.get("evidence") if isinstance(body.get("evidence"),dict) else {};user_confirmed=bool(body.get("user_confirmed"))
    reconciled=reconcile_outcome(lifecycle,outcome,evidence=evidence,user_confirmed=user_confirmed)
    if not reconciled["ok"]:return jsonify(reconciled),409
    now=_now();updated=(get_supabase().table(FOLLOWUP_TABLE).update({"status":"completed","completed_at":now,"outcome":reconciled["outcome"],"outcome_evidence":evidence,"user_confirmed":user_confirmed,"updated_at":now}).eq("id",followup_id).eq("email",email).execute().data or [row])[0]
    transition=reconciled.get("transition")
    if reconciled.get("lifecycle_changed") and transition:
        get_supabase().table(LIFECYCLE_TABLE).update({"state":transition["state"],"latest_evidence":evidence,"state_changed_at":now,"updated_at":now,"terminal_at":now if transition.get("terminal") else None}).eq("id",lifecycle["id"]).eq("email",email).execute()
        event=build_reconciliation_event(transition,evidence,source="followup_outcome");event.update({"lifecycle_id":lifecycle["id"],"email":email,"user_confirmed":user_confirmed});get_supabase().table(EVENT_TABLE).insert(event).execute()
    return jsonify({"ok":True,"followup":updated,"outcome_reconciliation":reconciled,"safety":{"employer_contact_performed":False}})
