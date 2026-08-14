from __future__ import annotations

from typing import Any, Dict, List


SUPPORTED = {
    "english": {"exam": "IELTS General", "framework": "CLB"},
    "french": {"exam": "TEF Canada", "framework": "NCLC"},
}


def _level(value: Any) -> int:
    try:
        return max(0, min(12, int(value)))
    except (TypeError, ValueError):
        return 0


def build_learning_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    selection = str(payload.get("language_selection") or "english").strip().lower()
    if selection not in {"english", "french", "both"}:
        selection = "english"

    allocation = payload.get("allocation") or {}
    if selection == "both":
        english_share = max(0, min(100, int(allocation.get("english", 50) or 50)))
        french_share = 100 - english_share
    elif selection == "english":
        english_share, french_share = 100, 0
    else:
        english_share, french_share = 0, 100

    diagnostic = payload.get("diagnostic") or {}
    targets = payload.get("targets") or {}
    languages: List[Dict[str, Any]] = []
    for language, share in (("english", english_share), ("french", french_share)):
        if share <= 0:
            continue
        current = _level(diagnostic.get(language))
        target = _level(targets.get(language)) or 7
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

    minutes = max(5, min(180, int(payload.get("daily_minutes", 20) or 20)))
    daily = []
    for item in languages:
        share_minutes = max(1, round(minutes * item["allocation_percent"] / 100))
        daily.append({
            "language": item["language"],
            "minutes": share_minutes,
            "activities": [
                {"type": "micro_challenge", "minutes": min(5, share_minutes)},
                {"type": "mistakes_review", "minutes": min(5, max(1, share_minutes // 4))},
                {"type": "adaptive_practice", "minutes": max(1, share_minutes - min(10, share_minutes))},
            ],
        })

    return {
        "language_selection": selection,
        "allocation": {"english": english_share, "french": french_share},
        "daily_minutes": minutes,
        "languages": languages,
        "daily_plan": daily,
        "momentum_policy": "A missed day reduces weekly consistency only; it does not erase accumulated progress.",
        "content_policy": "Use officially released material where permitted or original MoveReady exam-style questions; never use leaked or recalled live exam content.",
    }
