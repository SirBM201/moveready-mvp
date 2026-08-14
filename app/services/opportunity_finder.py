from __future__ import annotations

from typing import Any, Dict, List


PATHWAYS = {
    "work": {"title": "Work and employer route", "href": "/jobs", "qualify": "/language-coach"},
    "study": {"title": "Study and admission route", "href": "/study-planner", "qualify": "/language-coach"},
    "scholarship": {"title": "Scholarship and funded study", "href": "/opportunities", "qualify": "/study-planner"},
    "startup": {"title": "Startup and founder mobility", "href": "/compare", "qualify": "/evidence-pack"},
    "business": {"title": "Entrepreneur and business route", "href": "/compare", "qualify": "/evidence-pack"},
    "digital_nomad": {"title": "Remote-work and digital nomad route", "href": "/compare", "qualify": "/proof-of-funds"},
    "family": {"title": "Family relocation route", "href": "/family-planner", "qualify": "/evidence-pack"},
    "visit": {"title": "Visitor and travel route", "href": "/trip-planner", "qualify": "/visa-power"},
    "opportunity": {"title": "Ballot, quota and mobility opportunity", "href": "/opportunities", "qualify": "/watchlist"},
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def recommend_pathways(profile: Dict[str, Any], opportunities: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    goal = _text(profile.get("main_goal") or profile.get("goal") or "relocation").lower()
    funds = _number(profile.get("available_funds_amount"))
    experience = _number(profile.get("work_experience_years"))
    education = _text(profile.get("education_level"))
    business_stage = _text(profile.get("business_stage"))
    target_country = _text(profile.get("target_country"))
    timeline = int(_number(profile.get("timeline_months")))
    family = int(_number(profile.get("family_members_count")))
    refusal = bool(profile.get("has_previous_refusal"))

    scores: Dict[str, int] = {key: 20 for key in PATHWAYS}
    reasons: Dict[str, List[str]] = {key: [] for key in PATHWAYS}
    if goal in scores:
        scores[goal] += 45
        reasons[goal].append("Matches the main goal saved in your MoveReady profile.")
    if experience >= 2:
        scores["work"] += 20; reasons["work"].append("Recorded work experience supports employment-route research.")
    if education:
        scores["study"] += 12; scores["scholarship"] += 8
        reasons["study"].append("An education level is recorded, so academic-fit checks can be narrowed.")
    if business_stage:
        scores["startup"] += 20; scores["business"] += 20
        reasons["startup"].append("A business stage is recorded in your profile.")
    if funds > 0:
        for key in ("study", "startup", "business", "digital_nomad", "visit"):
            scores[key] += 8
    if family > 0:
        scores["family"] += 18; reasons["family"].append("Your profile includes accompanying family members.")
    if timeline and timeline <= 6:
        scores["opportunity"] += 8; reasons["opportunity"].append("A shorter timeline makes current opening windows worth monitoring.")

    live_counts: Dict[str, int] = {}
    for item in opportunities or []:
        category = _text(item.get("route_category") or item.get("opportunity_type")).lower()
        if category:
            live_counts[category] = live_counts.get(category, 0) + 1
    if opportunities:
        scores["opportunity"] += min(15, len(opportunities))
        reasons["opportunity"].append(f"{len(opportunities)} reviewed public opportunity record(s) are currently available for comparison.")

    ranked = []
    for key, meta in PATHWAYS.items():
        score = min(100, scores[key])
        ranked.append({
            "pathway": key, "title": meta["title"], "fit_score": score,
            "fit_label": "strong_lead" if score >= 70 else "worth_checking" if score >= 45 else "secondary",
            "reasons": reasons[key] or ["This remains a secondary route until more profile evidence supports it."],
            "find_href": meta["href"], "qualify_href": meta["qualify"], "target_country": target_country or None,
        })
    ranked.sort(key=lambda row: row["fit_score"], reverse=True)
    gaps = []
    if not target_country: gaps.append("Choose a target country to narrow official route requirements.")
    if funds <= 0: gaps.append("Add available funds so financial-readiness checks can influence pathway priority.")
    if not education: gaps.append("Add education level to improve study and qualification screening.")
    if refusal: gaps.append("A previous refusal is recorded; use refusal-repair evidence before submitting a new application.")
    return {
        "recommendations": ranked[:5], "profile_goal": goal, "target_country": target_country or None,
        "profile_gaps": gaps, "live_opportunity_count": len(opportunities or []), "live_category_counts": live_counts,
        "safety_note": "Fit scores are planning signals, not eligibility decisions or promises of visa, admission, employment, permanent residence, selection, or border entry. Confirm current official requirements before acting.",
    }
