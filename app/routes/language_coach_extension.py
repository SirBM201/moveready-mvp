from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.language_coach import (
    LanguageCoachValidationError,
    adaptive_difficulty,
    diagnostic_placement,
    eligible_public_questions,
    normalize_language,
    normalize_question_ids,
    normalize_skill,
)
from app.services.supabase_client import get_supabase

bp = Blueprint("language_coach_extension", __name__)


@bp.errorhandler(LanguageCoachValidationError)
def _validation_error(error):
    payload = {"ok": False, "error": error.code}
    if error.field:
        payload["field"] = error.field
    return jsonify(payload), 400


def _account():
    email = get_verified_session_email()
    if email:
        return email, None
    return None, (jsonify({"ok": False, "error": "verified_session_required"}), 401)


@bp.get("/adaptive-practice")
def adaptive_practice():
    email, error = _account()
    if error:
        return error
    language = normalize_language(request.args.get("language"))
    skill = normalize_skill(request.args.get("skill"))
    question_rows = eligible_public_questions(
        get_supabase().table("relocation_language_questions")
        .select("id,language,content_origin,source_url")
        .eq("language", language)
        .eq("is_active", True)
        .limit(1000)
        .execute()
        .data
        or []
    )
    ids = [row["id"] for row in question_rows]
    attempts = []
    if ids:
        attempts = get_supabase().table("relocation_language_attempts").select("is_correct,difficulty,question_id,attempted_at").eq("email", email).in_("question_id", ids).order("attempted_at", desc=True).limit(20).execute().data or []
    difficulty = adaptive_difficulty(attempts)
    query = get_supabase().table("relocation_language_questions").select("id,language,exam,skill,difficulty,prompt,choices,content_origin,source_url").eq("language", language).eq("difficulty", difficulty).eq("is_active", True)
    if skill:
        query = query.eq("skill", skill)
    questions = eligible_public_questions(query.limit(10).execute().data or [])
    return jsonify({"ok": True, "language": language, "difficulty": difficulty, "questions": questions, "answer_key_withheld": True, "adaptive": True})


@bp.get("/daily-challenge")
def daily_challenge():
    email, error = _account()
    if error:
        return error
    language = normalize_language(request.args.get("language"))
    question_rows = eligible_public_questions(
        get_supabase().table("relocation_language_questions")
        .select("id,language,content_origin,source_url")
        .eq("language", language)
        .eq("is_active", True)
        .limit(1000)
        .execute()
        .data
        or []
    )
    ids = [row["id"] for row in question_rows]
    attempts = get_supabase().table("relocation_language_attempts").select("is_correct,difficulty,question_id,attempted_at").eq("email", email).in_("question_id", ids).order("attempted_at", desc=True).limit(20).execute().data or [] if ids else []
    difficulty = adaptive_difficulty(attempts)
    questions = eligible_public_questions(
        get_supabase().table("relocation_language_questions")
        .select("id,language,exam,skill,difficulty,prompt,choices,content_origin,source_url")
        .eq("language", language)
        .eq("difficulty", difficulty)
        .eq("is_active", True)
        .limit(3)
        .execute()
        .data
        or []
    )
    return jsonify({"ok": True, "language": language, "difficulty": difficulty, "questions": questions, "estimated_minutes": "1-5", "answer_key_withheld": True})


@bp.post("/diagnostic/complete")
def complete_diagnostic():
    email, error = _account()
    if error:
        return error
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise LanguageCoachValidationError("invalid_payload")
    language = normalize_language(payload.get("language"))
    question_ids = normalize_question_ids(payload.get("question_ids"))
    questions = eligible_public_questions(
        get_supabase().table("relocation_language_questions")
        .select("id,language,content_origin,source_url")
        .in_("id", question_ids)
        .eq("language", language)
        .eq("is_active", True)
        .execute()
        .data
        or []
    )
    valid_ids = [row["id"] for row in questions]
    if not valid_ids:
        return jsonify({"ok": False, "error": "diagnostic_questions_not_found"}), 404
    attempts = get_supabase().table("relocation_language_attempts").select("question_id,is_correct,attempted_at").eq("email", email).in_("question_id", valid_ids).order("attempted_at", desc=True).limit(len(valid_ids) * 3).execute().data or []
    latest = {}
    for row in attempts:
        latest.setdefault(str(row.get("question_id")), row)
    scored = [row for key, row in latest.items() if key in {str(value) for value in valid_ids}]
    placement = diagnostic_placement(scored)
    if not placement["complete"]:
        return jsonify({
            "ok": False,
            "error": "diagnostic_incomplete",
            **placement,
        }), 400
    level = placement["placement_level"]
    column = f"{language}_current_level"
    existing = get_supabase().table("relocation_language_profiles").select("id").eq("email", email).limit(1).execute().data or []
    if existing:
        get_supabase().table("relocation_language_profiles").update({column: level}).eq("email", email).execute()
    else:
        defaults = {"email": email, "language_selection": language, "english_allocation": 100 if language == "english" else 0, "french_allocation": 100 if language == "french" else 0, column: level}
        get_supabase().table("relocation_language_profiles").insert(defaults).execute()
    return jsonify({
        "ok": True,
        "language": language,
        **placement,
        "next_action": "adaptive_practice",
    })
