from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


CONTRACT_VERSION = "b11-v1"

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

ROUTE_CATEGORIES = {
    "work": {"work"},
    "study": {"study"},
    "scholarship": {"scholarship", "study"},
    "startup": {"startup", "business"},
    "business": {"business", "startup"},
    "digital_nomad": {"digital_nomad", "work"},
    "family": {"family"},
    "visit": {"visit"},
    "opportunity": set(),
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _https(value: Any) -> Optional[str]:
    url = _text(value)
    return url if url.lower().startswith("https://") else None


def _freshness(verified_at: Any, review_due_at: Any, now: datetime) -> str:
    if not verified_at:
        return "verification_missing"
    review_due = _date(review_due_at)
    if review_due and review_due < now:
        return "review_due"
    return "current"


def _profile_snapshot(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "main_goal": _text(profile.get("main_goal") or profile.get("goal") or "relocation").lower(),
        "current_country": _text(profile.get("current_country")) or None,
        "country_of_residence": _text(profile.get("residence_country") or profile.get("country_of_residence")) or None,
        "nationality_country": _text(profile.get("nationality") or profile.get("nationality_country")) or None,
        "target_country": _text(profile.get("target_country")) or None,
        "route_category_preference": _text(profile.get("route_category") or profile.get("route_category_preference")) or None,
        "timeline_months": int(_number(profile.get("timeline_months"))) or None,
        "family_members_count": int(_number(profile.get("family_members_count"))),
        "available_funds_recorded": _number(profile.get("available_funds_amount")) > 0,
        "available_funds_currency": _text(profile.get("available_funds_currency")) or None,
        "education_level_recorded": bool(_text(profile.get("education_level"))),
        "work_experience_years_recorded": _number(profile.get("work_experience_years")) > 0,
        "business_stage_recorded": bool(_text(profile.get("business_stage"))),
        "previous_refusal_recorded": bool(profile.get("has_previous_refusal")),
    }


def _cost_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    currencies = sorted({_text(item.get("currency_code")).upper() for item in items if _text(item.get("currency_code"))})
    required = [item for item in items if item.get("is_required", True)]
    mixed = len(currencies) > 1
    return {
        "planning_only": True,
        "currency": currencies[0] if len(currencies) == 1 else None,
        "mixed_currencies": mixed,
        "minimum": None if mixed or not items else sum(_number(item.get("amount_min")) for item in items),
        "maximum": None if mixed or not items else sum(_number(item.get("amount_max")) for item in items),
        "item_count": len(items),
        "required_item_count": len(required),
        "items": [
            {
                "name": item.get("item_name"),
                "category": item.get("item_category"),
                "minimum": item.get("amount_min"),
                "maximum": item.get("amount_max"),
                "currency": item.get("currency_code"),
                "required": bool(item.get("is_required", True)),
                "notes": item.get("notes"),
            }
            for item in items
        ],
    }


def _source_summary(route: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    freshness = _freshness(route.get("verified_at"), route.get("review_due_at"), now)
    sources = []
    official_types = {"government", "embassy", "visa_center", "university", "scholarship_body"}
    for source in route.get("official_sources") or []:
        url = _https(source.get("source_url"))
        if not url or source.get("source_type") not in official_types:
            continue
        sources.append({
            "title": source.get("source_name") or source.get("owner_organization") or "Official source",
            "url": url,
            "source_type": source.get("source_type"),
            "owner_organization": source.get("owner_organization"),
            "reliability_level": source.get("reliability_level"),
            "status": source.get("status"),
            "last_checked_at": source.get("last_checked_at"),
            "review_due_at": source.get("next_review_due_at"),
            "usage_note": source.get("usage_note"),
        })
    source_status = "official_sources_current"
    if not sources:
        source_status = "source_review_required"
    elif freshness != "current" or any(
        source.get("status") != "active"
        or not source.get("last_checked_at")
        or (_date(source.get("review_due_at")) or now) < now
        for source in sources
    ):
        source_status = "source_review_required"
    return {
        "jurisdiction": route.get("country_name") or route.get("country_code"),
        "source_confidence": route.get("source_confidence") or "source review required",
        "freshness_status": freshness,
        "verified_at": route.get("verified_at"),
        "review_due_at": route.get("review_due_at"),
        "official_source_status": source_status,
        "official_sources": sources,
    }


def _route_candidate(route: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    documents = route.get("documents") or []
    version = route.get("version") or {}
    provenance = _source_summary(route, now)
    timeline_notes = [note for note in (version.get("processing_time_notes"), version.get("validity_notes")) if note]
    risk_notes = [note for note in (version.get("refusal_risk_notes"),) if note]
    if provenance["freshness_status"] != "current":
        risk_notes.append("Official-source verification is missing or due for review; confirm current rules before acting.")
    return {
        "route_id": route.get("id"),
        "route_version_id": route.get("active_version_id"),
        "route_code": route.get("route_code"),
        "route_name": route.get("route_name"),
        "route_category": route.get("route_category"),
        "country_id": route.get("country_id"),
        "country_code": route.get("country_code"),
        "country_name": route.get("country_name"),
        "summary": route.get("summary"),
        "risk_level": route.get("risk_level") or "review required",
        "qualification": {
            "decision": "not_determined",
            "status": "requires_route_specific_review",
            "eligibility_notes": version.get("eligibility_notes"),
        },
        "evidence": {
            "required_count": sum(1 for item in documents if item.get("requirement_level") == "required"),
            "conditional_count": sum(1 for item in documents if item.get("requirement_level") == "conditional"),
            "items": [
                {"name": item.get("document_name"), "level": item.get("requirement_level"), "applies_to": item.get("applies_to"), "details": item.get("details")}
                for item in documents
            ],
        },
        "costs": _cost_summary(route.get("budget_items") or []),
        "timeline_notes": timeline_notes,
        "risk_notes": risk_notes,
        "provenance": {key: value for key, value in provenance.items() if key != "official_sources"},
        "official_sources": provenance["official_sources"],
        "next_actions": [
            {"label": "Check this exact route", "href": f"/route-checker?country={route.get('country_code')}&route={route.get('route_code')}"},
            {"label": "Compare countries", "href": "/compare"},
            {"label": "Review financial readiness", "href": "/budget-calculator"},
            {"label": "Prepare evidence", "href": "/evidence-pack"},
        ],
    }


def _normalise_opportunities(opportunities: List[Dict[str, Any]], now: datetime) -> List[Dict[str, Any]]:
    return [{
        "id": item.get("id"),
        "code": item.get("opportunity_code"),
        "name": item.get("opportunity_name"),
        "type": item.get("opportunity_type"),
        "route_category": item.get("route_category"),
        "country_code": item.get("country_code"),
        "country_name": item.get("country_name"),
        "availability_status": item.get("availability_status"),
        "summary": item.get("summary"),
        "eligibility_summary": item.get("eligibility_summary"),
        "application_window_summary": item.get("application_window_summary"),
        "safety_notes": item.get("safety_notes"),
        "official_url": _https(item.get("official_url")),
        "source_confidence": item.get("source_confidence"),
        "last_verified_at": item.get("last_verified_at"),
        "next_review_due_at": item.get("next_review_due_at"),
        "freshness_status": _freshness(item.get("last_verified_at"), item.get("next_review_due_at"), now),
    } for item in opportunities]


def recommend_pathways(
    profile: Dict[str, Any],
    opportunities: List[Dict[str, Any]] | None = None,
    routes: List[Dict[str, Any]] | None = None,
    *,
    retrieved_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = retrieved_at or datetime.now(timezone.utc)
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
        scores["work"] += 20
        reasons["work"].append("Recorded work experience supports employment-route research.")
    if education:
        scores["study"] += 12
        scores["scholarship"] += 8
        reasons["study"].append("An education level is recorded, so academic-fit checks can be narrowed.")
    if business_stage:
        scores["startup"] += 20
        scores["business"] += 20
        reasons["startup"].append("A business stage is recorded in your profile.")
    if funds > 0:
        for key in ("study", "startup", "business", "digital_nomad", "visit"):
            scores[key] += 8
    if family > 0:
        scores["family"] += 18
        reasons["family"].append("Your profile includes accompanying family members.")
    if timeline and timeline <= 6:
        scores["opportunity"] += 8
        reasons["opportunity"].append("A shorter timeline makes current opening windows worth monitoring.")

    live_counts: Dict[str, int] = {}
    for item in opportunities or []:
        category = _text(item.get("route_category") or item.get("opportunity_type")).lower()
        if category:
            live_counts[category] = live_counts.get(category, 0) + 1
    if opportunities:
        scores["opportunity"] += min(15, len(opportunities))
        reasons["opportunity"].append(f"{len(opportunities)} reviewed public opportunity record(s) are currently available for comparison.")

    gaps = []
    if not target_country:
        gaps.append("Choose a target country to narrow official route requirements.")
    if funds <= 0:
        gaps.append("Add available funds so financial-readiness checks can influence pathway priority.")
    if not education:
        gaps.append("Add education level to improve study and qualification screening.")
    if refusal:
        gaps.append("A previous refusal is recorded; use refusal-repair evidence before submitting a new application.")

    candidates = [_route_candidate(route, now) for route in routes or []]
    ranked = []
    for key, meta in PATHWAYS.items():
        score = min(100, scores[key])
        route_candidates = [route for route in candidates if route.get("route_category") in ROUTE_CATEGORIES[key]][:3]
        known_signals = reasons[key][:]
        if target_country:
            known_signals.append(f"Target country recorded as {target_country}; exact jurisdiction rules still require review.")
        ranked.append({
            "pathway": key,
            "title": meta["title"],
            "fit_score": score,
            "score_kind": "profile_alignment_not_eligibility",
            "fit_label": "strong_lead" if score >= 70 else "worth_checking" if score >= 45 else "secondary",
            "reasons": reasons[key] or ["This remains a secondary route until more profile evidence supports it."],
            "find_href": meta["href"],
            "qualify_href": meta["qualify"],
            "target_country": target_country or None,
            "qualification": {"decision": "not_determined", "status": "requires_route_specific_review", "known_signals": known_signals, "gaps": gaps},
            "candidate_routes": route_candidates,
            "next_actions": [
                {"label": "Explore this pathway", "href": meta["href"]},
                {"label": "Build qualification evidence", "href": meta["qualify"]},
            ],
        })
    ranked.sort(key=lambda row: row["fit_score"], reverse=True)

    return {
        "contract_version": CONTRACT_VERSION,
        "retrieved_at": now.isoformat(),
        "recommendations": ranked[:5],
        "profile_goal": goal,
        "target_country": target_country or None,
        "profile_snapshot": _profile_snapshot(profile),
        "profile_gaps": gaps,
        "route_candidate_count": len(candidates),
        "live_opportunity_count": len(opportunities or []),
        "live_category_counts": live_counts,
        "matching_opportunities": _normalise_opportunities(opportunities or [], now),
        "safety_note": "Alignment scores are planning signals, not eligibility decisions or promises of visa, admission, employment, permanent residence, selection, or border entry. Confirm current official requirements before acting.",
    }
