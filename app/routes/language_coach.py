from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from app.services.account_identity import get_verified_session_email
from app.services.language_coach import (
    DIAGNOSTIC_MINIMUM_ATTEMPTS,
    LANGUAGE_CHOICES,
    QUESTION_FETCH_LIMIT,
    SUPPORTED,
    SUPPORTED_SKILLS,
    LanguageCoachValidationError,
    build_learning_plan,
    eligible_public_questions,
    normalize_answer,
    normalize_difficulty,
    normalize_language,
    normalize_question_ids,
    normalize_response_seconds,
    normalize_skill,
    practice_readiness,
    profile_row_from_payload,
)
from app.services.supabase_client import get_supabase

bp = Blueprint("language_coach", __name__)


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
    return None, (jsonify({"ok": False, "error": "verified_session_required", "hint": "Sign in before using your private Language Coach."}), 401)


def _one(query):
    rows = query.limit(1).execute().data or []
    return rows[0] if rows else None


@bp.get("/options")
@bp.get("/catalog")
def catalog():
    return jsonify({
        "ok": True,
        "contract_version": "b07-v1",
        "language_choices": list(LANGUAGE_CHOICES),
        "allocation_presets": [
            {"english": value, "french": 100 - value}
            for value in (50, 70, 30)
        ],
        "supported_skills": list(SUPPORTED_SKILLS),
        "initial_exams": {
            language: [meta["exam"]]
            for language, meta in SUPPORTED.items()
        },
        "architecture_ready_for": {
            "english": ["CELPIP", "PTE Core"],
            "french": ["TCF Canada"],
        },
        "answer_key_policy": "withheld_until_answer_recorded",
        "content_policy": "moveready_original_or_permitted_official_release_only",
        "score_boundary": "internal_practice_indicators_not_official_exam_results",
    })


@bp.post("/plan")
def plan():
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    return jsonify({"ok": True, "plan": build_learning_plan(payload)})


@bp.get("/profile")
def get_profile():
    email, error = _account()
    if error: return error
    return jsonify({"ok": True, "profile": _one(get_supabase().table("relocation_language_profiles").select("*").eq("email", email))})


@bp.patch("/profile")
@bp.put("/profile")
def save_profile():
    email, error = _account()
    if error:
        return error
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise LanguageCoachValidationError("invalid_payload")
    client = get_supabase()
    existing = _one(
        client.table("relocation_language_profiles")
        .select("*")
        .eq("email", email)
    )
    plan, row = profile_row_from_payload(payload, existing)
    row.update({"email": email, "updated_at": datetime.now(timezone.utc).isoformat()})
    if existing:
        saved_rows = (
            client.table("relocation_language_profiles")
            .update(row)
            .eq("email", email)
            .execute()
            .data
            or []
        )
    else:
        saved_rows = client.table("relocation_language_profiles").insert(row).execute().data or []
    saved = saved_rows[0] if saved_rows else {**(existing or {}), **row}
    return jsonify({"ok": True, "profile": saved, "plan": plan})


def _questions(language, difficulty=None, limit=10):
    query = get_supabase().table("relocation_language_questions").select("id,language,exam,skill,difficulty,prompt,choices,content_origin,source_url").eq("language", language).eq("is_active", True)
    if difficulty is not None:
        query = query.eq("difficulty", difficulty)
    return eligible_public_questions(query.limit(limit).execute().data or [])


@bp.get("/practice")
def practice():
    _email, error = _account()
    if error:
        return error
    language = normalize_language(request.args.get("language"))
    skill = normalize_skill(request.args.get("skill"))
    difficulty = normalize_difficulty(request.args.get("difficulty"))
    query = get_supabase().table("relocation_language_questions").select("id,language,exam,skill,difficulty,prompt,choices,content_origin,source_url").eq("language", language).eq("difficulty", difficulty).eq("is_active", True)
    if skill:
        query = query.eq("skill", skill)
    questions = eligible_public_questions(query.limit(QUESTION_FETCH_LIMIT).execute().data or [])
    return jsonify({
        "ok": True,
        "language": language,
        "difficulty": difficulty,
        "questions": questions,
        "answer_key_withheld": True,
    })


@bp.get("/diagnostic")
def diagnostic():
    _email, error = _account()
    if error:
        return error
    language = normalize_language(request.args.get("language"))
    rows = _questions(language, limit=100)
    selected = []
    for level in range(1, 6):
        selected.extend([
            row for row in rows
            if int(row.get("difficulty") or 1) == level
        ][:2])
    return jsonify({
        "ok": True,
        "language": language,
        "questions": selected,
        "minimum_attempts": DIAGNOSTIC_MINIMUM_ATTEMPTS,
        "answer_key_withheld": True,
        "purpose": "placement_not_official_exam_score",
    })


def _record_daily_progress(email, language, correct, response_seconds=None):
    today = datetime.now(timezone.utc).date().isoformat()
    existing = _one(get_supabase().table("relocation_language_daily_progress").select("*").eq("email", email).eq("activity_date", today)) or {}
    seconds = response_seconds or 0
    minutes = max(1, round(seconds / 60)) if seconds else 1
    row = {"email": email, "activity_date": today, "english_minutes": int(existing.get("english_minutes") or 0) + (minutes if language == "english" else 0), "french_minutes": int(existing.get("french_minutes") or 0) + (minutes if language == "french" else 0), "questions_attempted": int(existing.get("questions_attempted") or 0) + 1, "questions_correct": int(existing.get("questions_correct") or 0) + (1 if correct else 0), "momentum_points": int(existing.get("momentum_points") or 0) + (2 if correct else 1)}
    if existing.get("id"): get_supabase().table("relocation_language_daily_progress").update(row).eq("id", existing["id"]).execute()
    else: get_supabase().table("relocation_language_daily_progress").insert(row).execute()
    return row


@bp.post("/attempts")
def record_attempt():
    email, error = _account()
    if error:
        return error
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise LanguageCoachValidationError("invalid_payload")
    question_id = str(payload.get("question_id") or "").strip()
    if not question_id or len(question_id) > 128:
        raise LanguageCoachValidationError("invalid_question_id", "question_id")
    answer = normalize_answer(payload.get("answer"))
    response_seconds = normalize_response_seconds(payload.get("response_seconds"))
    question = _one(get_supabase().table("relocation_language_questions").select("*").eq("id", question_id).eq("is_active", True))
    if not question:
        return jsonify({"ok": False, "error": "question_not_found"}), 404
    if not eligible_public_questions([question]):
        return jsonify({"ok": False, "error": "question_content_unavailable"}), 409
    correct = answer.casefold() == str(question.get("correct_answer") or "").strip().casefold()
    now = datetime.now(timezone.utc)
    get_supabase().table("relocation_language_attempts").insert({"email": email, "question_id": question_id, "answer": answer, "is_correct": correct, "difficulty": question.get("difficulty") or 1, "response_seconds": response_seconds}).execute()
    existing = _one(get_supabase().table("relocation_language_mistakes").select("*").eq("email", email).eq("question_id", question_id))
    if correct and existing:
        streak = int(existing.get("correct_streak") or 0) + 1; interval = 30 if streak >= 3 else 7 if streak == 2 else 2
        get_supabase().table("relocation_language_mistakes").update({"correct_streak": streak, "last_answer": answer, "last_attempt_at": now.isoformat(), "next_review_at": (now + timedelta(days=interval)).isoformat(), "mastered_at": now.isoformat() if streak >= 3 else None}).eq("id", existing["id"]).execute()
    elif not correct:
        row = {"email": email, "question_id": question_id, "mistake_count": int((existing or {}).get("mistake_count") or 0) + 1, "correct_streak": 0, "next_review_at": (now + timedelta(days=1)).isoformat(), "last_answer": answer, "last_attempt_at": now.isoformat(), "mastered_at": None}
        (get_supabase().table("relocation_language_mistakes").update(row).eq("id", existing["id"]) if existing else get_supabase().table("relocation_language_mistakes").insert(row)).execute()
    daily = _record_daily_progress(email, str(question.get("language") or "english"), correct, response_seconds)
    return jsonify({"ok": True, "correct": correct, "correct_answer": question.get("correct_answer"), "explanation": question.get("explanation"), "next_action": "review_mistake" if not correct else "continue", "daily_progress": daily})


@bp.get("/mistakes")
def mistakes():
    email, error = _account()
    if error: return error
    return jsonify({"ok": True, "mistakes": get_supabase().table("relocation_language_mistakes").select("*").eq("email", email).order("next_review_at").limit(50).execute().data or []})


@bp.get("/review")
def review():
    email, error = _account()
    if error: return error
    now = datetime.now(timezone.utc).isoformat(); mistakes = get_supabase().table("relocation_language_mistakes").select("*").eq("email", email).lte("next_review_at", now).is_("mastered_at", "null").order("next_review_at").limit(10).execute().data or []
    ids = [m.get("question_id") for m in mistakes if m.get("question_id")]
    questions = eligible_public_questions(
        get_supabase().table("relocation_language_questions")
        .select("id,language,exam,skill,difficulty,prompt,choices,content_origin,source_url")
        .in_("id", ids)
        .execute()
        .data
        or []
    ) if ids else []
    by_id = {q["id"]: q for q in questions}
    return jsonify({"ok": True, "due": [{**m, "question": by_id.get(m.get("question_id"))} for m in mistakes if by_id.get(m.get("question_id"))]})


def _progress_stats(email):
    attempts = get_supabase().table("relocation_language_attempts").select("is_correct,difficulty,question_id,attempted_at").eq("email", email).order("attempted_at", desc=True).limit(500).execute().data or []
    questions = get_supabase().table("relocation_language_questions").select("id,language,skill").limit(1000).execute().data or []; qmap = {q["id"]: q for q in questions}; stats = {"english": {"attempted":0,"correct":0}, "french": {"attempted":0,"correct":0}}
    for a in attempts:
        q = qmap.get(a.get("question_id")) or {}; lang = q.get("language")
        if lang in stats: stats[lang]["attempted"] += 1; stats[lang]["correct"] += 1 if a.get("is_correct") else 0
    for language, item in list(stats.items()):
        stats[language] = practice_readiness(item["attempted"], item["correct"])
    return stats


@bp.get("/progress")
def progress():
    email, error = _account()
    if error: return error
    daily = get_supabase().table("relocation_language_daily_progress").select("*").eq("email", email).order("activity_date", desc=True).limit(14).execute().data or []
    active_days = sum(1 for row in daily if int(row.get("questions_attempted") or 0) > 0); momentum = sum(int(row.get("momentum_points") or 0) for row in daily)
    return jsonify({"ok": True, "languages": _progress_stats(email), "daily": daily, "momentum": {"active_days_last_14": active_days, "points_last_14": momentum, "model": "non_punitive"}, "note": "Practice readiness is not an official IELTS, TEF, CLB or NCLC score. Momentum rewards continued activity and is not reset to zero after one missed day."})


@bp.get("/qualification-actions")
def qualification_actions():
    email, error = _account()
    if error: return error
    profile = _one(get_supabase().table("relocation_language_profiles").select("*").eq("email", email)) or {}; stats = _progress_stats(email); selection = str(profile.get("language_selection") or "english").lower(); selected = ["english", "french"] if selection == "both" else [selection if selection in {"english", "french"} else "english"]; actions = []
    for language in selected:
        current = int(profile.get(f"{language}_current_level") or 0); target = int(profile.get(f"{language}_target_level") or 7); progress_item = stats[language]; exam = profile.get(f"{language}_exam") or ("IELTS General" if language == "english" else "TEF Canada"); gap = max(0, target-current)
        if progress_item["attempted"] < 10: action, priority = "complete_diagnostic_and_foundation_practice", "high"
        elif gap > 0 or progress_item["accuracy_percent"] < 70: action, priority = "continue_targeted_practice", "high"
        elif progress_item["accuracy_percent"] < 85: action, priority = "strengthen_exam_readiness", "medium"
        else: action, priority = "maintain_and_review", "low"
        actions.append({"language": language, "exam": exam, "current_target_level": target, "profile_level": current, "target_gap": gap, "practice": progress_item, "action": action, "priority": priority, "href": "/language-coach"})
    return jsonify({"ok": True, "language_selection": selection, "user_choice_preserved": True, "actions": actions, "note": "MoveReady may recommend language preparation for a pathway, but it does not override the user's English/French/Both selection and these practice indicators are not official exam scores."})
