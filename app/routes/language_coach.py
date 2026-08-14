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


def _one(query):
    rows = query.limit(1).execute().data or []
    return rows[0] if rows else None


def _profile_payload(payload):
    plan = build_learning_plan(payload)
    diagnostic = payload.get("diagnostic") or {}
    targets = payload.get("targets") or {}
    return plan, {
        "language_selection": plan["language_selection"], "english_allocation": plan["allocation"]["english"], "french_allocation": plan["allocation"]["french"],
        "daily_minutes": plan["daily_minutes"], "english_exam": "IELTS General", "french_exam": "TEF Canada",
        "english_current_level": int(diagnostic.get("english", 0) or 0), "french_current_level": int(diagnostic.get("french", 0) or 0),
        "english_target_level": int(targets.get("english", 7) or 7), "french_target_level": int(targets.get("french", 7) or 7),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@bp.get("/catalog")
def catalog():
    return jsonify({"ok": True, "language_choices": ["english", "french", "both"], "allocation_presets": [{"english": 50, "french": 50}, {"english": 70, "french": 30}, {"english": 30, "french": 70}], "initial_exams": {"english": ["IELTS General"], "french": ["TEF Canada"]}, "architecture_ready_for": {"english": ["CELPIP", "PTE Core"], "french": ["TCF Canada"]}})


@bp.post("/plan")
def plan(): return jsonify({"ok": True, "plan": build_learning_plan(request.get_json(silent=True) or {})})


@bp.get("/profile")
def get_profile():
    email, error = _account()
    if error: return error
    row = _one(get_supabase().table("relocation_language_profiles").select("*").eq("email", email))
    return jsonify({"ok": True, "profile": row})


@bp.put("/profile")
def save_profile():
    email, error = _account()
    if error: return error
    payload = request.get_json(silent=True) or {}; plan, row = _profile_payload(payload); row["email"] = email
    existing = _one(get_supabase().table("relocation_language_profiles").select("id").eq("email", email))
    saved = (get_supabase().table("relocation_language_profiles").update(row).eq("email", email).execute().data or [None])[0] if existing else (get_supabase().table("relocation_language_profiles").insert(row).execute().data or [None])[0]
    return jsonify({"ok": True, "profile": saved, "plan": plan})


def _questions(language, difficulty=None, limit=10):
    query = get_supabase().table("relocation_language_questions").select("id,language,exam,skill,difficulty,prompt,choices,content_origin,source_url").eq("language", language).eq("is_active", True)
    if difficulty is not None: query = query.eq("difficulty", difficulty)
    return query.limit(limit).execute().data or []


@bp.get("/practice")
def practice():
    email, error = _account()
    if error: return error
    language = str(request.args.get("language") or "english").lower(); skill = str(request.args.get("skill") or "").lower(); difficulty = max(1, min(5, int(request.args.get("difficulty") or 1)))
    query = get_supabase().table("relocation_language_questions").select("id,language,exam,skill,difficulty,prompt,choices,content_origin,source_url").eq("language", language).eq("difficulty", difficulty).eq("is_active", True)
    if skill: query = query.eq("skill", skill)
    return jsonify({"ok": True, "questions": query.limit(10).execute().data or [], "answer_key_withheld": True})


@bp.get("/diagnostic")
def diagnostic():
    email, error = _account()
    if error: return error
    language = str(request.args.get("language") or "english").lower()
    if language not in {"english", "french"}: return jsonify({"ok": False, "error": "unsupported_language"}), 400
    rows = _questions(language, limit=30)
    selected = []
    for level in range(1, 6):
        level_rows = [r for r in rows if int(r.get("difficulty") or 1) == level]
        selected.extend(level_rows[:2])
    return jsonify({"ok": True, "language": language, "questions": selected, "answer_key_withheld": True, "purpose": "placement_not_official_exam_score"})


@bp.post("/attempts")
def record_attempt():
    email, error = _account()
    if error: return error
    payload = request.get_json(silent=True) or {}; question_id = str(payload.get("question_id") or "")
    question = _one(get_supabase().table("relocation_language_questions").select("*").eq("id", question_id).eq("is_active", True))
    if not question: return jsonify({"ok": False, "error": "question_not_found"}), 404
    answer = str(payload.get("answer") or "").strip(); correct = answer.casefold() == str(question.get("correct_answer") or "").strip().casefold(); now = datetime.now(timezone.utc)
    get_supabase().table("relocation_language_attempts").insert({"email": email, "question_id": question_id, "answer": answer, "is_correct": correct, "difficulty": question.get("difficulty") or 1, "response_seconds": payload.get("response_seconds")}).execute()
    existing = _one(get_supabase().table("relocation_language_mistakes").select("*").eq("email", email).eq("question_id", question_id))
    if correct and existing:
        streak = int(existing.get("correct_streak") or 0) + 1; interval = 30 if streak >= 3 else 7 if streak == 2 else 2
        get_supabase().table("relocation_language_mistakes").update({"correct_streak": streak, "last_answer": answer, "last_attempt_at": now.isoformat(), "next_review_at": (now + timedelta(days=interval)).isoformat(), "mastered_at": now.isoformat() if streak >= 3 else None}).eq("id", existing["id"]).execute()
    elif not correct:
        row = {"email": email, "question_id": question_id, "mistake_count": int((existing or {}).get("mistake_count") or 0) + 1, "correct_streak": 0, "next_review_at": (now + timedelta(days=1)).isoformat(), "last_answer": answer, "last_attempt_at": now.isoformat(), "mastered_at": None}
        (get_supabase().table("relocation_language_mistakes").update(row).eq("id", existing["id"]) if existing else get_supabase().table("relocation_language_mistakes").insert(row)).execute()
    return jsonify({"ok": True, "correct": correct, "correct_answer": question.get("correct_answer"), "explanation": question.get("explanation"), "next_action": "review_mistake" if not correct else "continue"})


@bp.get("/mistakes")
def mistakes():
    email, error = _account()
    if error: return error
    rows = get_supabase().table("relocation_language_mistakes").select("*").eq("email", email).order("next_review_at").limit(50).execute().data or []
    return jsonify({"ok": True, "mistakes": rows})


@bp.get("/review")
def review():
    email, error = _account()
    if error: return error
    now = datetime.now(timezone.utc).isoformat(); mistakes = get_supabase().table("relocation_language_mistakes").select("*").eq("email", email).lte("next_review_at", now).is_("mastered_at", "null").order("next_review_at").limit(10).execute().data or []
    ids = [m.get("question_id") for m in mistakes if m.get("question_id")]
    questions = get_supabase().table("relocation_language_questions").select("id,language,exam,skill,difficulty,prompt,choices,content_origin").in_("id", ids).execute().data or [] if ids else []
    by_id = {q["id"]: q for q in questions}
    return jsonify({"ok": True, "due": [{**m, "question": by_id.get(m.get("question_id"))} for m in mistakes if by_id.get(m.get("question_id"))]})


def _progress_stats(email):
    attempts = get_supabase().table("relocation_language_attempts").select("is_correct,difficulty,question_id,created_at").eq("email", email).order("created_at", desc=True).limit(500).execute().data or []
    questions = get_supabase().table("relocation_language_questions").select("id,language,skill").limit(1000).execute().data or []
    qmap = {q["id"]: q for q in questions}; stats = {"english": {"attempted":0,"correct":0}, "french": {"attempted":0,"correct":0}}
    for a in attempts:
        q = qmap.get(a.get("question_id")) or {}; lang = q.get("language")
        if lang in stats: stats[lang]["attempted"] += 1; stats[lang]["correct"] += 1 if a.get("is_correct") else 0
    for item in stats.values():
        item["accuracy_percent"] = round(item["correct"] * 100 / item["attempted"]) if item["attempted"] else 0
        item["readiness"] = "building" if item["attempted"] < 10 else "developing" if item["accuracy_percent"] < 70 else "progressing" if item["accuracy_percent"] < 85 else "strong_practice_readiness"
    return stats


@bp.get("/progress")
def progress():
    email, error = _account()
    if error: return error
    return jsonify({"ok": True, "languages": _progress_stats(email), "note": "Practice readiness is not an official IELTS, TEF, CLB or NCLC score."})


@bp.get("/qualification-actions")
def qualification_actions():
    email, error = _account()
    if error: return error
    profile = _one(get_supabase().table("relocation_language_profiles").select("*").eq("email", email)) or {}
    stats = _progress_stats(email)
    selection = str(profile.get("language_selection") or "english").lower()
    selected = ["english", "french"] if selection == "both" else [selection if selection in {"english", "french"} else "english"]
    actions = []
    for language in selected:
        current = int(profile.get(f"{language}_current_level") or 0)
        target = int(profile.get(f"{language}_target_level") or 7)
        progress_item = stats[language]
        exam = profile.get(f"{language}_exam") or ("IELTS General" if language == "english" else "TEF Canada")
        gap = max(0, target - current)
        if progress_item["attempted"] < 10:
            action = "complete_diagnostic_and_foundation_practice"
            priority = "high"
        elif gap > 0 or progress_item["accuracy_percent"] < 70:
            action = "continue_targeted_practice"
            priority = "high"
        elif progress_item["accuracy_percent"] < 85:
            action = "strengthen_exam_readiness"
            priority = "medium"
        else:
            action = "maintain_and_review"
            priority = "low"
        actions.append({"language": language, "exam": exam, "current_target_level": target, "profile_level": current, "target_gap": gap, "practice": progress_item, "action": action, "priority": priority, "href": "/language-coach"})
    return jsonify({"ok": True, "language_selection": selection, "user_choice_preserved": True, "actions": actions, "note": "MoveReady may recommend language preparation for a pathway, but it does not override the user's English/French/Both selection and these practice indicators are not official exam scores."})
