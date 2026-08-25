from __future__ import annotations
import json
from datetime import datetime,timezone
from flask import Blueprint,jsonify,request
from app.services.account_identity import get_verified_session_email
from app.services.supabase_client import get_supabase

bp=Blueprint("job_career_practice",__name__)
TABLE="relocation_job_career_practice_sessions";TYPES={"linkedin_review","mock_interview"};LANGUAGES={"en","fr"};STATUSES={"draft","completed","archived"}
def _now():return datetime.now(timezone.utc).isoformat()
def _account():
 email=get_verified_session_email();return(email,None)if email else(None,(jsonify({"ok":False,"error":"verified_session_required"}),401))
def _body():
 value=request.get_json(silent=True);return value if isinstance(value,dict)else{}
def _safe_object(value):return value if isinstance(value,dict)else{}
def _public(row):return {k:v for k,v in(row or{}).items()if k!="email"}

@bp.get("/career-practice")
def list_sessions():
 email,error=_account()
 if error:return error
 kind=str(request.args.get("practice_type")or"").strip()
 if kind and kind not in TYPES:return jsonify({"ok":False,"error":"unsupported_practice_type"}),400
 q=get_supabase().table(TABLE).select("*").eq("email",email)
 if kind:q=q.eq("practice_type",kind)
 rows=q.order("created_at",desc=True).limit(100).execute().data or[]
 return jsonify({"ok":True,"items":[_public(x)for x in rows],"count":len(rows),"privacy":"Private to the verified account."})

@bp.post("/career-practice")
def create_session():
 email,error=_account()
 if error:return error
 body=_body();kind=str(body.get("practice_type")or"").strip();language=str(body.get("language")or"en").strip().lower();status=str(body.get("status")or"completed").strip()
 if kind not in TYPES:return jsonify({"ok":False,"error":"unsupported_practice_type"}),400
 if language not in LANGUAGES:return jsonify({"ok":False,"error":"unsupported_practice_language"}),400
 if status not in STATUSES:return jsonify({"ok":False,"error":"unsupported_practice_status"}),400
 if body.get("user_confirmed")is not True:return jsonify({"ok":False,"error":"user_confirmation_required"}),400
 input_snapshot=_safe_object(body.get("input_snapshot"));output_snapshot=_safe_object(body.get("output_snapshot"))
 if len(json.dumps(input_snapshot))+len(json.dumps(output_snapshot))>60000:return jsonify({"ok":False,"error":"practice_snapshot_too_large"}),413
 score=body.get("score")
 try:score=None if score in(None,"")else max(0,min(100,round(float(score),2)))
 except(TypeError,ValueError):return jsonify({"ok":False,"error":"invalid_practice_score"}),400
 row={"email":email,"practice_type":kind,"job_id":body.get("job_id")or None,"target_role":str(body.get("target_role")or"").strip()[:220]or None,"language":language,"input_snapshot":input_snapshot,"output_snapshot":output_snapshot,"score":score,"status":status,"user_confirmed":True,"created_at":_now(),"updated_at":_now()}
 saved=(get_supabase().table(TABLE).insert(row).execute().data or[row])[0]
 return jsonify({"ok":True,"session":_public(saved),"safety":{"feedback_is_advisory":True,"selection_outcome_not_predicted":True,"employer_or_recruiter_insight_not_inferred":True}}),201

@bp.get("/career-practice/<session_id>")
def get_session(session_id):
 email,error=_account()
 if error:return error
 row=get_supabase().table(TABLE).select("*").eq("id",session_id).eq("email",email).maybe_single().execute().data
 if not row:return jsonify({"ok":False,"error":"career_practice_session_not_found"}),404
 return jsonify({"ok":True,"session":_public(row)})

@bp.patch("/career-practice/<session_id>")
def update_session(session_id):
 email,error=_account()
 if error:return error
 body=_body();status=str(body.get("status")or"").strip()
 if status not in STATUSES:return jsonify({"ok":False,"error":"unsupported_practice_status"}),400
 rows=get_supabase().table(TABLE).update({"status":status,"updated_at":_now()}).eq("id",session_id).eq("email",email).execute().data or[]
 if not rows:return jsonify({"ok":False,"error":"career_practice_session_not_found"}),404
 return jsonify({"ok":True,"session":_public(rows[0])})


