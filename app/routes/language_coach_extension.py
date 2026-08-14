from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.language_coach import adaptive_difficulty, placement_level
from app.services.supabase_client import get_supabase

bp = Blueprint("language_coach_extension", __name__)


def _account():
    email = get_verified_session_email()
    if email:
        return email, None
    return None, (jsonify({"ok": False, "error": "verified_session_required"}), 401)


def _language(value):
    language = str(value or "english").lower()
    return language if language in {"english", "french"} else None


@bp.get("/adaptive-practice")
def adaptive_practice():
    email, error = _account()
    if error:
        return error
    language = _language(request.args.get("language"))
    if not language:
        return jsonify({"ok": False, "error": "unsupported_language"}), 400
    skill = str(request.args.get("skill") or "").lower()
    question_rows = get_supabase().table("relocation_language_questions").select("id,language").eq("language", language).eq("is_active", True).limit(1000).execute().data or []
    ids = [row["id"] for row in question_rows]
    attempts = []
    if ids:
        attempts = get_supabase().table("relocation_language_attempts").select("is_correct,difficulty,question_id,attempted_at").eq("email", email).in_("question_id", ids).order("attempted_at", desc=True).limit(20).execute().data or []
    difficulty = adaptive_difficulty(attempts)
    query = get_supabase().table("relocation_language_questions").select("id,language,exam,skill,difficulty,prompt,choices,content_origin,source_url").eq("language", language).eq("difficulty", difficulty).eq("is_active", True)
    if skill:
        query = query.eq("skill", skill)
    questions = query.limit(10).execute().data or []
    return jsonify({"ok": True, "language": language, "difficulty": difficulty, "questions": questions, "answer_key_withheld": True, "adaptive": True})


@bp.get("/daily-challenge")
def daily_challenge():
    email, error = _account()
    if error:
        return error
    language = _language(request.args.get("language"))
    if not language:
        return jsonify({"ok": False, "error": "unsupported_language"}), 400
    question_rows = get_supabase().table("relocation_language_questions").select("id,language").eq("language", language).eq("is_active", True).limit(1000).execute().data or []
    ids = [row["id"] for row in question_rows]
    attempts = get_supabase().table("relocation_language_attempts").select("is_correct,difficulty,question_id,attempted_at").eq("email", email).in_("question_id", ids).order("attempted_at", desc=True).limit(20).execute().data or [] if ids else []
    difficulty = adaptive_difficulty(attempts)
    questions = get_supabase().table("relocation_language_questions").select("id,language,exam,skill,difficulty,prompt,choices,content_origin,source_url").eq("language", language).eq("difficulty", difficulty).eq("is_active", True).limit(5).execute().data or []
    return jsonify({"ok": True, "language": language, "difficulty": difficulty, "questions": questions, "estimated_minutes": "1-5", "answer_key_withheld": True})


@bp.post("/diagnostic/complete")
def complete_diagnostic():
    email, error = _account()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    language = _language(payload.get("language"))
    question_ids = [str(value) for value in (payload.get("question_ids") or []) if value]
    if not language:
        return jsonify({"ok": False, "error": "unsupported_language"}), 400
    if not question_ids:
        return jsonify({"ok": False, "error": "question_ids_required"}), 400
    questions = get_supabase().table("relocation_language_questions").select("id,language").in_("id", question_ids).eq("language", language).execute().data or []
    valid_ids = [row["id"] for row in questions]
    if not valid_ids:
        return jsonify({"ok": False, "error": "diagnostic_questions_not_found"}), 404
    attempts = get_supabase().table("relocation_language_attempts").select("question_id,is_correct,attempted_at").eq("email", email).in_("question_id", valid_ids).order("attempted_at", desc=True).limit(len(valid_ids) * 3).execute().data or []
    latest = {}
    for row in attempts:
        latest.setdefault(str(row.get("question_id")), row)
    scored = [row for key, row in latest.items() if key in {str(value) for value in valid_ids}]
    correct = sum(1 for row in scored if row.get("is_correct"))
    level = placement_level(correct, len(scored))
    column = f"{language}_current_level"
    existing = get_supabase().table("relocation_language_profiles").select("id").eq("email", email).limit(1).execute().data or []
    if existing:
        get_supabase().table("relocation_language_profiles").update({column: level}).eq("email", email).execute()
    else:
        defaults = {"email": email, "language_selection": language, "english_allocation": 100 if language == "english" else 0, "french_allocation": 100 if language == "french" else 0, column: level}
        get_supabase().table("relocation_language_profiles").insert(defaults).execute()
    return jsonify({"ok": True, "language": language, "attempted": len(scored), "correct": correct, "placement_level": level, "purpose": "internal_placement_not_official_exam_score", "next_action": "adaptive_practice"})
