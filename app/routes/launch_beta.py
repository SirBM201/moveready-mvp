from __future__ import annotations
from datetime import datetime,timezone
from flask import Blueprint,jsonify,request
from app.services.account_identity import get_verified_session_email
from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access

bp=Blueprint("launch_beta",__name__)
TABLE="relocation_launch_beta_reports"
DEVICES={"phone","tablet","desktop"};JOURNEYS={"find","qualify","move","alerts","career","full_journey"}
RESULTS={"passed","blocked","needs_help"};SEVERITIES={"none","minor","major","critical"}
def _now():return datetime.now(timezone.utc).isoformat()
def _account():
 email=get_verified_session_email()
 return(email,None)if email else(None,(jsonify({"ok":False,"error":"verified_session_required"}),401))
def _public(row):return{k:v for k,v in(row or{}).items()if k!="email"}

@bp.get("/beta/reports")
def list_reports():
 email,error=_account()
 if error:return error
 rows=get_supabase().table(TABLE).select("*").eq("email",email).order("created_at",desc=True).limit(100).execute().data or[]
 return jsonify({"ok":True,"contract_version":"lq12-v1","items":[_public(x)for x in rows],"count":len(rows),"privacy":"Private to the verified account."})

@bp.post("/beta/reports")
def create_report():
 email,error=_account()
 if error:return error
 body=request.get_json(silent=True)or{}
 device=str(body.get("device_class")or"").strip();journey=str(body.get("journey")or"").strip()
 result=str(body.get("result")or"").strip();severity=str(body.get("severity")or"none").strip()
 summary=str(body.get("summary")or"").strip();steps=str(body.get("reproduction_steps")or"").strip()
 if device not in DEVICES:return jsonify({"ok":False,"error":"unsupported_device_class"}),400
 if journey not in JOURNEYS:return jsonify({"ok":False,"error":"unsupported_beta_journey"}),400
 if result not in RESULTS:return jsonify({"ok":False,"error":"unsupported_beta_result"}),400
 if severity not in SEVERITIES:return jsonify({"ok":False,"error":"unsupported_beta_severity"}),400
 if not summary or len(summary)>1200 or len(steps)>4000:return jsonify({"ok":False,"error":"invalid_beta_report_text"}),400
 if result=="passed" and severity!="none":return jsonify({"ok":False,"error":"passed_report_must_have_no_severity"}),400
 row={"email":email,"cohort_code":"v1-controlled-beta","device_class":device,"journey":journey,"result":result,"severity":severity,"summary":summary,"reproduction_steps":steps or None,"technical_help_required":bool(body.get("technical_help_required")),"consent_to_contact":bool(body.get("consent_to_contact")),"app_commit":str(body.get("app_commit")or"")[:64]or None,"backend_commit":str(body.get("backend_commit")or"")[:64]or None,"status":"open","created_at":_now(),"updated_at":_now()}
 saved=(get_supabase().table(TABLE).insert(row).execute().data or[row])[0]
 return jsonify({"ok":True,"report":_public(saved),"safety_note":"Beta feedback records product usability only and is not an immigration, employment or approval outcome."}),201

@bp.get("/admin/beta/summary")
@require_admin_access
def admin_summary():
 rows=get_supabase().table(TABLE).select("*").neq("status","excluded").limit(1000).execute().data or[]
 participants=len({str(x.get("email")or"").lower()for x in rows if x.get("email")})
 completed={str(x.get("email")or"").lower()for x in rows if x.get("journey")=="full_journey"and x.get("result")=="passed"}
 critical=sum(1 for x in rows if x.get("status")=="open"and x.get("severity")=="critical")
 help_free=sum(1 for x in rows if not x.get("technical_help_required"))
 pass_rate=round(100*len(completed)/participants,1)if participants else 0
 help_free_rate=round(100*help_free/len(rows),1)if rows else 0
 gates={"participants":participants>=10,"full_journey_completion":pass_rate>=80,"no_open_critical":critical==0,"help_free":help_free_rate>=90}
 return jsonify({"ok":True,"contract_version":"lq12-v1","participants":participants,"target_participants":{"minimum":10,"maximum":20},"reports":len(rows),"full_journey_completion_rate":pass_rate,"help_free_rate":help_free_rate,"open_critical":critical,"gates":gates,"ready_for_public_launch":all(gates.values())and participants<=20})
