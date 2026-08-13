from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

SUPPORTED = {"english": {"ielts_general"}, "french": {"tef_canada"}}

def normalize_learning_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    choice = str(payload.get("language_choice") or "english").lower()
    if choice not in {"english", "french", "both"}: raise ValueError("language_choice must be english, french, or both")
    allocation = int(payload.get("english_allocation", 50 if choice == "both" else (100 if choice == "english" else 0)))
    if choice == "english": allocation = 100
    if choice == "french": allocation = 0
    if allocation not in {0, 30, 50, 70, 100}: raise ValueError("english_allocation must be 0, 30, 50, 70, or 100")
    daily = max(1, min(180, int(payload.get("daily_minutes") or 10)))
    return {"language_choice": choice, "english_exam": "ielts_general", "french_exam": "tef_canada", "english_allocation": allocation, "target_clb": payload.get("target_clb"), "target_nclc": payload.get("target_nclc"), "daily_minutes": daily}

def next_review(mistake_count: int, mastery: float, correct: bool) -> Dict[str, Any]:
    mistakes = max(0, int(mistake_count)) + (0 if correct else 1)
    new_mastery = max(0.0, min(100.0, float(mastery) + (12 if correct else -8)))
    days = 1 if not correct else max(1, min(30, int(1 + new_mastery / 12)))
    return {"mistake_count": mistakes, "mastery": round(new_mastery, 2), "next_review_at": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()}

def readiness(attempted: int, correct: int, diagnostic_complete: bool) -> Dict[str, Any]:
    accuracy = round((correct / attempted) * 100, 1) if attempted else 0.0
    if not diagnostic_complete: label = "diagnostic_needed"
    elif attempted < 20: label = "building_baseline"
    elif accuracy >= 80: label = "on_track"
    elif accuracy >= 60: label = "developing"
    else: label = "needs_focus"
    return {"attempted": attempted, "correct": correct, "accuracy": accuracy, "readiness": label}
