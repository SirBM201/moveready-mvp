from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.language_coach import build_learning_plan
from app.services.supabase_client import get_supabase

bp = Blueprint("language_coach", __name__)


def _account():
    email = get_verified_session_email()
    if email:
        return email, None
    return None, (jsonify({"ok": False, "error": "verified_session_required", "hint": "Sign in before using your private Language Coach."}), 401)


def _profile_payload(payload):
    plan = build_learning_plan(payload)
    diagnostic = payload.get("diagnostic") or {}
    targets = payload.get("targets") or {}
    return plan, {
        "language_selection": plan["language_selection"],
        "english_allocation": plan["allocation"]["english"],
        "french_allocation": plan["allocation"]["french"],
        "daily_minutes": plan["daily_minutes"],
        "english_exam": "IELTS General",
        "french_exam": "TEF Canada",
        "english_current_level": int(diagnostic.get("english", 0) or 0),
        "french_current_level": int(diagnostic.get("french", 0) or 0),
        "english_target_level": int(targets.get("english", 7) or 7),
        "french_target_level": int(targets.get("french", 7) or 7),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@bp.get("/catalog")
def catalog():
    return jsonify({"ok": True, "language_choices": ["english", "french", "both"], "allocation_presets": [{"english": 50, "french": 50}, {"english": 70, "french": 30}, {"english": 30, "french": 70}], "initial_exams": {"english": ["IELTS General"], "french": ["TEF Canada"]}, "architecture_ready_for": {"english": ["CELPIP", "PTE Core"], "french": ["TCF Canada"]}, "v1_capabilities": ["diagnostic", "personalized_plan", "microlearning", "practice_bank", "mistakes_bank", "spaced_repetition", "adaptive_difficulty", "progress_tracking", "CLB/NCLC_targets"]})


@bp.post("/plan")
def plan():
    return jsonify({"ok": True, "plan": build_learning_plan(request.get_json(silent=True) or {})})


@bp.get("/profile")
def get_profile():
    email, error = _account()
    if error: return error
    row = get_supabase().table("relocation_language_profiles").select("*").eq("email", email).maybe_single().execute().data
    return jsonify({"ok": True, "profile": row})


@bp.put("/profile")
def save_profile():
    email, error = _account()
    if error: return error
    payload = request.get_json(silent=True) or {}
    plan, row = _profile_payload(payload)
    row["email"] = email
    existing = get_supabase().table("relocation_language_profiles").select("id").eq("email", email).maybe_single().execute().data
    if existing:
        saved = (get_supabase().table("relocation_language_profiles").update(row).eq("email", email).execute().data or [None])[0]
    else:
        saved = (get_supabase().table("relocation_language_profiles").insert(row).execute().data or [None])[0]
    return jsonify({"ok": True, "profile": saved, "plan": plan})


@bp.get("/practice")
def practice():
    email, error = _account()
    if error: return error
    language = str(request.args.get("language") or "english").lower()
    skill = str(request.args.get("skill") or "").lower()
    difficulty = max(1, min(5, int(request.args.get("difficulty") or 1)))
    query = get_supabase().table("relocation_language_questions").select("id,language,exam,skill,difficulty,prompt,choices,content_origin,source_url").eq("language", language).eq("difficulty", difficulty).eq("is_active", True)
    if skill: query = query.eq("skill", skill)
    rows = query.limit(10).execute().data or []
    return jsonify({"ok": True, "questions": rows, "answer_key_withheld": True})


@bp.post("/attempts")
def record_attempt():
    email, error = _account()
    if error: return error
    payload = request.get_json(silent=True) or {}
    question_id = str(payload.get("question_id") or "")
    question = get_supabase().table("relocation_language_questions").select("*").eq("id", question_id).eq("is_active", True).maybe_single().execute().data
    if not question: return jsonify({"ok": False, "error": "question_not_found"}), 404
    answer = str(payload.get("answer") or "").strip()
    correct = answer.casefold() == str(question.get("correct_answer") or "").strip().casefold()
    now = datetime.now(timezone.utc)
    get_supabase().table("relocation_language_attempts").insert({"email": email, "question_id": question_id, "answer": answer, "is_correct": correct, "difficulty": question.get("difficulty") or 1, "response_seconds": payload.get("response_seconds")}).execute()
    existing = get_supabase().table("relocation_language_mistakes").select("*").eq("email", email).eq("question_id", question_id).maybe_single().execute().data
    if correct:
        if existing:
            streak = int(existing.get("correct_streak") or 0) + 1
            interval = 30 if streak >= 3 else 7 if streak == 2 else 2
            get_supabase().table("relocation_language_mistakes").update({"correct_streak": streak, "last_answer": answer, "last_attempt_at": now.isoformat(), "next_review_at": (now + timedelta(days=interval)).isoformat(), "mastered_at": now.isoformat() if streak >= 3 else None}).eq("id", existing["id"]).execute()
    else:
        row = {"email": email, "question_id": question_id, "mistake_count": int((existing or {}).get("mistake_count") or 0) + 1, "correct_streak": 0, "next_review_at": (now + timedelta(days=1)).isoformat(), "last_answer": answer, "last_attempt_at": now.isoformat(), "mastered_at": None}
        if existing: get_supabase().table("relocation_language_mistakes").update(row).eq("id", existing["id"]).execute()
        else: get_supabase().table("relocation_language_mistakes").insert(row).execute()
    return jsonify({"ok": True, "correct": correct, "correct_answer": question.get("correct_answer"), "explanation": question.get("explanation"), "next_action": "review_mistake" if not correct else "continue"})


@bp.get("/mistakes")
def mistakes():
    email, error = _account()
    if error: return error
    rows = get_supabase().table("relocation_language_mistakes").select("*").eq("email", email).order("next_review_at").limit(50).execute().data or []
    return jsonify({"ok": True, "mistakes": rows})
