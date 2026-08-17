from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence


LANGUAGE_CHOICES = ("english", "french", "both")
ALLOCATION_PRESETS = (30, 50, 70)
SUPPORTED_SKILLS = ("vocabulary", "grammar", "reading", "listening")
DIAGNOSTIC_MINIMUM_ATTEMPTS = 6
QUESTION_FETCH_LIMIT = 10
MAX_ANSWER_LENGTH = 500
MAX_RESPONSE_SECONDS = 7200

SUPPORTED = {
    "english": {"exam": "IELTS General", "framework": "CLB"},
    "french": {"exam": "TEF Canada", "framework": "NCLC"},
}


class LanguageCoachValidationError(ValueError):
    def __init__(self, code: str, field: str | None = None):
        super().__init__(code)
        self.code = code
        self.field = field


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise LanguageCoachValidationError(f"invalid_{field}", field)
    return value


def _integer(
    value: Any,
    *,
    field: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise LanguageCoachValidationError(f"invalid_{field}", field)
    if isinstance(value, float) and not value.is_integer():
        raise LanguageCoachValidationError(f"invalid_{field}", field)
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise LanguageCoachValidationError(f"invalid_{field}", field) from None
    if normalized < minimum or normalized > maximum:
        raise LanguageCoachValidationError(f"invalid_{field}", field)
    return normalized


def normalize_language_choice(value: Any, default: str = "english") -> str:
    choice = str(value or default).strip().lower()
    if choice not in LANGUAGE_CHOICES:
        raise LanguageCoachValidationError("unsupported_language_selection", "language_selection")
    return choice


def normalize_language(value: Any, default: str = "english") -> str:
    language = str(value or default).strip().lower()
    if language not in SUPPORTED:
        raise LanguageCoachValidationError("unsupported_language", "language")
    return language


def normalize_skill(value: Any, *, optional: bool = True) -> str:
    skill = str(value or "").strip().lower()
    if not skill and optional:
        return ""
    if skill not in SUPPORTED_SKILLS:
        raise LanguageCoachValidationError("unsupported_skill", "skill")
    return skill


def normalize_difficulty(value: Any, default: int = 1) -> int:
    return _integer(value, field="difficulty", default=default, minimum=1, maximum=5)


def normalize_response_seconds(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return _integer(
        value,
        field="response_seconds",
        default=0,
        minimum=0,
        maximum=MAX_RESPONSE_SECONDS,
    )


def normalize_answer(value: Any) -> str:
    answer = str(value or "").strip()
    if not answer:
        raise LanguageCoachValidationError("answer_required", "answer")
    if len(answer) > MAX_ANSWER_LENGTH:
        raise LanguageCoachValidationError("answer_too_long", "answer")
    return answer


def normalize_question_ids(value: Any) -> List[str]:
    if not isinstance(value, list):
        raise LanguageCoachValidationError("question_ids_required", "question_ids")
    result: List[str] = []
    seen = set()
    for raw in value:
        question_id = str(raw or "").strip()
        if not question_id or len(question_id) > 128:
            raise LanguageCoachValidationError("invalid_question_id", "question_ids")
        if question_id not in seen:
            seen.add(question_id)
            result.append(question_id)
    if not result:
        raise LanguageCoachValidationError("question_ids_required", "question_ids")
    if len(result) > 30:
        raise LanguageCoachValidationError("too_many_question_ids", "question_ids")
    return result


def question_content_is_eligible(question: Mapping[str, Any]) -> bool:
    origin = str(question.get("content_origin") or "").strip().lower()
    if origin == "moveready_original":
        return True
    if origin == "official_released":
        return str(question.get("source_url") or "").strip().lower().startswith("https://")
    return False


def eligible_public_questions(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows if question_content_is_eligible(row)]


def placement_level(correct: int, attempted: int) -> int:
    """Return a conservative 0-5 internal placement level, never an official exam score."""
    if attempted <= 0:
        return 0
    ratio = max(0.0, min(1.0, correct / attempted))
    if ratio < 0.30:
        return 1
    if ratio < 0.50:
        return 2
    if ratio < 0.70:
        return 3
    if ratio < 0.85:
        return 4
    return 5


def diagnostic_placement(
    attempts: Sequence[Mapping[str, Any]],
    minimum_attempts: int = DIAGNOSTIC_MINIMUM_ATTEMPTS,
) -> Dict[str, Any]:
    attempted = len(attempts)
    correct = sum(1 for row in attempts if row.get("is_correct"))
    complete = attempted >= minimum_attempts
    return {
        "complete": complete,
        "attempted": attempted,
        "correct": correct,
        "required_attempts": minimum_attempts,
        "placement_level": placement_level(correct, attempted) if complete else None,
        "purpose": "internal_placement_not_official_exam_score",
    }


def adaptive_difficulty(attempts: List[Dict[str, Any]], default: int = 1) -> int:
    """Choose the next 1-5 practice difficulty from recent performance."""
    recent = attempts[:20]
    fallback = max(1, min(5, int(default or 1)))
    if not recent:
        return fallback
    try:
        current = normalize_difficulty(recent[0].get("difficulty"), fallback)
    except LanguageCoachValidationError:
        current = fallback
    correct = sum(1 for row in recent if row.get("is_correct"))
    accuracy = correct / len(recent)
    if len(recent) >= 5 and accuracy >= 0.80:
        return min(5, current + 1)
    if len(recent) >= 5 and accuracy < 0.55:
        return max(1, current - 1)
    return current


def practice_readiness(attempted: int, correct: int) -> Dict[str, Any]:
    attempted = max(0, int(attempted or 0))
    correct = max(0, min(attempted, int(correct or 0)))
    accuracy = round(correct * 100 / attempted) if attempted else 0
    if attempted < 10:
        readiness = "building"
    elif accuracy < 70:
        readiness = "developing"
    elif accuracy < 85:
        readiness = "progressing"
    else:
        readiness = "strong_practice_readiness"
    return {
        "attempted": attempted,
        "correct": correct,
        "accuracy_percent": accuracy,
        "readiness": readiness,
    }


def build_learning_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise LanguageCoachValidationError("invalid_payload")
    selection = normalize_language_choice(payload.get("language_selection"))
    allocation = _mapping(payload.get("allocation"), "allocation")
    if selection == "both":
        english_share = _integer(
            allocation.get("english"),
            field="english_allocation",
            default=50,
            minimum=0,
            maximum=100,
        )
        if english_share not in ALLOCATION_PRESETS:
            raise LanguageCoachValidationError("unsupported_allocation", "allocation")
        french_share = 100 - english_share
        if "french" in allocation and _integer(
            allocation.get("french"),
            field="french_allocation",
            default=french_share,
            minimum=0,
            maximum=100,
        ) != french_share:
            raise LanguageCoachValidationError("allocation_must_total_100", "allocation")
    elif selection == "english":
        english_share, french_share = 100, 0
    else:
        english_share, french_share = 0, 100

    diagnostic = _mapping(payload.get("diagnostic"), "diagnostic")
    targets = _mapping(payload.get("targets"), "targets")
    languages: List[Dict[str, Any]] = []
    for language, share in (("english", english_share), ("french", french_share)):
        if share <= 0:
            continue
        current = _integer(
            diagnostic.get(language),
            field=f"{language}_current_level",
            default=0,
            minimum=0,
            maximum=12,
        )
        target = _integer(
            targets.get(language),
            field=f"{language}_target_level",
            default=7,
            minimum=0,
            maximum=12,
        )
        gap = max(0, target - current)
        meta = SUPPORTED[language]
        languages.append({
            "language": language,
            "allocation_percent": share,
            "exam": meta["exam"],
            "framework": meta["framework"],
            "current_level": current,
            "target_level": target,
            "gap": gap,
            "readiness": "target_met" if gap == 0 else "close" if gap <= 2 else "building",
        })

    minutes = _integer(
        payload.get("daily_minutes"),
        field="daily_minutes",
        default=20,
        minimum=5,
        maximum=180,
    )
    daily = []
    for item in languages:
        share_minutes = max(1, round(minutes * item["allocation_percent"] / 100))
        micro_minutes = min(5, share_minutes)
        remaining = max(0, share_minutes - micro_minutes)
        review_minutes = min(5, remaining)
        adaptive_minutes = max(0, remaining - review_minutes)
        activities = [{"type": "micro_challenge", "minutes": micro_minutes}]
        if review_minutes:
            activities.append({"type": "mistakes_review", "minutes": review_minutes})
        if adaptive_minutes:
            activities.append({"type": "adaptive_practice", "minutes": adaptive_minutes})
        daily.append({
            "language": item["language"],
            "minutes": share_minutes,
            "activities": activities,
        })

    return {
        "contract_version": "b07-v1",
        "language_selection": selection,
        "allocation": {"english": english_share, "french": french_share},
        "daily_minutes": minutes,
        "languages": languages,
        "daily_plan": daily,
        "momentum_policy": "A missed day reduces weekly consistency only; it does not erase accumulated progress.",
        "content_policy": "Use officially released material where permitted or original MoveReady exam-style questions; never use leaked or recalled live exam content.",
        "score_boundary": "Placement and readiness are internal practice indicators, not official IELTS, TEF, CLB, or NCLC results.",
    }


def profile_row_from_payload(
    payload: Dict[str, Any],
    existing: Mapping[str, Any] | None = None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    existing = existing or {}
    diagnostic = {
        "english": existing.get("english_current_level", 0),
        "french": existing.get("french_current_level", 0),
    }
    normalized_payload = dict(payload)
    normalized_payload.setdefault(
        "language_selection",
        existing.get("language_selection", "english"),
    )
    normalized_payload.setdefault(
        "allocation",
        {
            "english": existing.get("english_allocation", 100),
            "french": existing.get("french_allocation", 0),
        },
    )
    normalized_payload.setdefault(
        "daily_minutes",
        existing.get("daily_minutes", 20),
    )
    normalized_payload["diagnostic"] = diagnostic
    submitted_targets = _mapping(payload.get("targets"), "targets")
    normalized_payload["targets"] = {
        "english": submitted_targets.get(
            "english",
            existing.get("english_target_level", 7),
        ),
        "french": submitted_targets.get(
            "french",
            existing.get("french_target_level", 7),
        ),
    }
    plan = build_learning_plan(normalized_payload)
    targets = normalized_payload["targets"]
    row = {
        "language_selection": plan["language_selection"],
        "english_allocation": plan["allocation"]["english"],
        "french_allocation": plan["allocation"]["french"],
        "daily_minutes": plan["daily_minutes"],
        "english_exam": SUPPORTED["english"]["exam"],
        "french_exam": SUPPORTED["french"]["exam"],
        "english_current_level": _integer(
            existing.get("english_current_level"),
            field="english_current_level",
            default=0,
            minimum=0,
            maximum=12,
        ),
        "french_current_level": _integer(
            existing.get("french_current_level"),
            field="french_current_level",
            default=0,
            minimum=0,
            maximum=12,
        ),
        "english_target_level": _integer(
            targets.get("english"),
            field="english_target_level",
            default=int(existing.get("english_target_level") or 7),
            minimum=0,
            maximum=12,
        ),
        "french_target_level": _integer(
            targets.get("french"),
            field="french_target_level",
            default=int(existing.get("french_target_level") or 7),
            minimum=0,
            maximum=12,
        ),
    }
    return plan, row
