from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4


def new_report_ref() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"MRR-{stamp}-{uuid4().hex[:8].upper()}"


def _text(value: Any, fallback: str = "") -> str:
    cleaned = str(value or "").strip()
    return cleaned or fallback


def _number(value: Any, fallback: float = 0) -> float:
    try:
        if value in (None, ""):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _integer(value: Any, fallback: int = 0) -> int:
    try:
        if value in (None, ""):
            return fallback
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _normalise_route(value: str) -> str:
    cleaned = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "business": "startup",
        "entrepreneur": "startup",
        "startup_founder": "startup",
        "student": "study",
        "scholarship": "study",
        "employment": "work",
        "job": "work",
        "visitor": "visit",
        "tourist": "visit",
    }
    return aliases.get(cleaned, cleaned or "relocation")


def _route_plan(route_category: str) -> Dict[str, Any]:
    route = _normalise_route(route_category)
    plans: Dict[str, Dict[str, Any]] = {
        "startup": {
            "label": "Startup / entrepreneur pathway",
            "minimum_funds": 12000,
            "required_documents": [
                "Valid passport",
                "Founder profile / CV",
                "Business plan or pitch deck",
                "MVP, traction, revenue, or product evidence",
                "Proof of funds and source of funds",
                "Company registration or planned incorporation evidence",
            ],
            "recommended_documents": [
                "Tax or income evidence",
                "Client, partner, or market validation evidence",
                "Insurance evidence",
                "Accommodation or arrival-plan evidence",
                "Legalization or translation checks where required",
            ],
            "route_questions": [
                "Is the business innovative, scalable, and credible for the target country?",
                "Can the founder explain role, ownership, traction, and funding clearly?",
                "Are business documents consistent with personal funds and relocation timeline?",
            ],
        },
        "study": {
            "label": "Study / scholarship pathway",
            "minimum_funds": 9000,
            "required_documents": [
                "Valid passport",
                "Admission, enrollment, or scholarship evidence",
                "Academic transcripts and certificates",
                "Proof of funds or sponsorship evidence",
                "Tuition or funding evidence",
            ],
            "recommended_documents": [
                "Accommodation plan",
                "Insurance evidence",
                "Statement of purpose",
                "Translation or legalization checks",
            ],
            "route_questions": [
                "Is the admission or scholarship evidence final and verifiable?",
                "Do funds cover tuition, living costs, and dependants where relevant?",
                "Are academic records consistent across names and dates?",
            ],
        },
        "work": {
            "label": "Work pathway",
            "minimum_funds": 7000,
            "required_documents": [
                "Valid passport",
                "Job offer or employer sponsorship evidence",
                "Qualification and work-experience evidence",
                "Proof of funds or salary evidence",
                "CV and professional records",
            ],
            "recommended_documents": [
                "Employment contract review",
                "Employer eligibility check",
                "Professional license or recognition checks",
                "Accommodation and arrival plan",
            ],
            "route_questions": [
                "Is the employer eligible to support the route?",
                "Does the job match qualification, salary, and route rules?",
                "Are professional documents ready for verification?",
            ],
        },
        "family": {
            "label": "Family pathway",
            "minimum_funds": 9000,
            "required_documents": [
                "Valid passport",
                "Relationship evidence",
                "Civil documents such as marriage or birth certificates",
                "Sponsor identity or residence evidence",
                "Proof of funds or support evidence",
            ],
            "recommended_documents": [
                "Legalization or apostille checks",
                "Custody or consent documents where children are involved",
                "Accommodation evidence",
                "Insurance or healthcare preparation",
            ],
            "route_questions": [
                "Is the relationship evidence complete and consistent?",
                "Are civil documents legalized, translated, or certified if required?",
                "Does the sponsor meet route-specific support requirements?",
            ],
        },
        "visit": {
            "label": "Visitor pathway",
            "minimum_funds": 3000,
            "required_documents": [
                "Valid passport",
                "Purpose of visit evidence",
                "Proof of funds",
                "Travel itinerary or invitation evidence",
                "Home-tie or return evidence",
            ],
            "recommended_documents": [
                "Employment or business tie evidence",
                "Accommodation plan",
                "Travel insurance where required",
                "Previous travel history evidence",
            ],
            "route_questions": [
                "Is the visit purpose clear and temporary?",
                "Can the applicant explain funds and return plan?",
                "Are home ties strong enough for the route?",
            ],
        },
        "digital_nomad": {
            "label": "Digital nomad / remote work pathway",
            "minimum_funds": 10000,
            "required_documents": [
                "Valid passport",
                "Remote work, freelance, or business income evidence",
                "Bank statements and source-of-funds evidence",
                "Client contracts or employer permission",
                "Insurance evidence",
            ],
            "recommended_documents": [
                "Tax-residency planning notes",
                "Accommodation plan",
                "Business registration or freelancer records",
                "Income consistency evidence",
            ],
            "route_questions": [
                "Is remote income stable and route-eligible?",
                "Are bank inflows consistent with contracts or invoices?",
                "Have tax and residence implications been checked?",
            ],
        },
        "relocation": {
            "label": "General relocation pathway",
            "minimum_funds": 8000,
            "required_documents": [
                "Valid passport",
                "Purpose evidence",
                "Proof of funds",
                "Civil documents where applicable",
                "Route-specific evidence once selected",
            ],
            "recommended_documents": [
                "Insurance check",
                "Accommodation plan",
                "Name consistency check",
                "Translation or legalization review",
            ],
            "route_questions": [
                "Is the route category selected clearly?",
                "Are documents mapped against an official checklist?",
                "Is the timeline realistic for document preparation?",
            ],
        },
    }
    return plans.get(route, plans["relocation"])


def _documents_from_payload(payload: Dict[str, Any]) -> List[str]:
    docs = payload.get("documents") or payload.get("document_checklist") or []
    if not isinstance(docs, list):
        return []
    cleaned: List[str] = []
    for item in docs:
        if isinstance(item, dict):
            label = _text(item.get("document_name") or item.get("name") or item.get("label"))
        else:
            label = _text(item)
        if label:
            cleaned.append(label.lower())
    return cleaned


def _document_gap(required_documents: List[str], supplied_documents: List[str]) -> Tuple[List[str], List[str]]:
    if not supplied_documents:
        return required_documents, []

    missing = []
    matched = []
    supplied_text = " | ".join(supplied_documents)
    for document in required_documents:
        tokens = [token for token in document.lower().replace("/", " ").replace(",", " ").split() if len(token) > 3]
        if any(token in supplied_text for token in tokens):
            matched.append(document)
        else:
            missing.append(document)
    return missing, matched


def _score_report(
    *,
    target_country: str,
    route_category: str,
    funds_amount: float,
    minimum_funds: float,
    timeline_months: int,
    family_members: int,
    has_previous_refusal: bool,
    missing_documents: List[str],
    supplied_documents: List[str],
) -> Tuple[int, str, str, List[str], List[str]]:
    score = 0
    strengths: List[str] = []
    flags: List[str] = []

    if target_country and target_country.lower() not in {"target country", "not set"}:
        score += 15
        strengths.append("Target country is selected.")
    else:
        flags.append("Target country is not clearly selected.")

    if route_category:
        score += 15
        strengths.append("Route category is selected.")
    else:
        flags.append("Route category is missing.")

    if funds_amount >= minimum_funds:
        score += 25
        strengths.append("Available funds meet the starter planning threshold for this route category.")
    elif funds_amount > 0:
        score += 12
        flags.append("Available funds are below the starter planning threshold for this route category.")
    else:
        flags.append("Available funds were not provided.")

    if timeline_months >= 6:
        score += 15
        strengths.append("Timeline gives room for document preparation and source checks.")
    elif timeline_months > 0:
        score += 7
        flags.append("Timeline is short; document preparation may become compressed.")
    else:
        flags.append("Timeline was not provided.")

    if supplied_documents:
        if missing_documents:
            score += 10
            flags.append("Some required starter documents appear missing from the entered checklist.")
        else:
            score += 20
            strengths.append("Entered document checklist covers the starter required categories.")
    else:
        flags.append("No document checklist was submitted with the report.")

    if family_members > 0:
        flags.append("Family-member planning is required for funds, documents, accommodation, and appointments.")
    else:
        score += 5
        strengths.append("No accompanying family members were entered for this starter plan.")

    if has_previous_refusal:
        flags.append("Previous refusal must be reviewed and repaired before relying on this route.")
    else:
        score += 5
        strengths.append("No previous refusal was declared in this profile.")

    score = max(0, min(score, 100))
    if score >= 75:
        readiness_level = "strong_start"
    elif score >= 50:
        readiness_level = "needs_detail"
    else:
        readiness_level = "early_stage"

    if has_previous_refusal or score < 45 or len(flags) >= 5:
        risk_level = "high"
    elif score < 70 or flags:
        risk_level = "medium"
    else:
        risk_level = "low"

    return score, readiness_level, risk_level, flags, strengths


def _money(amount: float, currency: str) -> str:
    if amount <= 0:
        return "not provided"
    return f"{currency} {amount:,.0f}"


def _section(key: str, title: str, content: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "section_key": key,
        "section_title": title,
        "section_content": content,
        "section_payload": payload or {},
    }


def build_readiness_report(payload: dict) -> dict:
    goal = _text(payload.get("goal") or payload.get("main_goal"), "relocation")
    target_country = _text(payload.get("target_country") or payload.get("targetCountry"), "Target country")
    current_country = _text(payload.get("current_country") or payload.get("currentCountry"), "Current country")
    route_category = _normalise_route(_text(payload.get("route_category") or payload.get("routeCategory") or goal, "relocation"))
    funds_amount = _number(payload.get("available_funds_amount") or payload.get("availableFundsAmount"), 0)
    funds_currency = _text(payload.get("available_funds_currency") or payload.get("availableFundsCurrency") or payload.get("currency"), "USD")
    family_members = _integer(payload.get("family_members_count") or payload.get("familyMembersCount"), 0)
    timeline_months = _integer(payload.get("timeline_months") or payload.get("target_timeline_months") or payload.get("timelineMonths"), 0)
    has_previous_refusal = _bool(payload.get("has_previous_refusal") or payload.get("previous_refusal"))
    full_name = _text(payload.get("full_name") or payload.get("name"), "Applicant")

    route_plan = _route_plan(route_category)
    required_documents = list(route_plan["required_documents"])
    recommended_documents = list(route_plan["recommended_documents"])
    supplied_documents = _documents_from_payload(payload)
    missing_documents, matched_documents = _document_gap(required_documents, supplied_documents)
    minimum_funds = float(route_plan["minimum_funds"])
    starter_gap = max(minimum_funds - funds_amount, 0)

    score, readiness_level, risk_level, readiness_flags, strengths = _score_report(
        target_country=target_country,
        route_category=route_category,
        funds_amount=funds_amount,
        minimum_funds=minimum_funds,
        timeline_months=timeline_months,
        family_members=family_members,
        has_previous_refusal=has_previous_refusal,
        missing_documents=missing_documents,
        supplied_documents=supplied_documents,
    )

    action_items = [
        {
            "priority": "high",
            "title": "Verify the exact official route checklist",
            "detail": f"Compare this starter {route_plan['label'].lower()} plan against the official source for {target_country} before paying, booking, or submitting.",
        },
        {
            "priority": "high" if missing_documents else "medium",
            "title": "Close document gaps",
            "detail": "Prepare missing starter documents: " + ", ".join(missing_documents[:6]) if missing_documents else "Keep document evidence updated and ready for route-specific formatting.",
        },
        {
            "priority": "high" if starter_gap > 0 else "medium",
            "title": "Confirm funds and source-of-funds evidence",
            "detail": f"Starter threshold used for planning: {_money(minimum_funds, funds_currency)}. Current entered funds: {_money(funds_amount, funds_currency)}.",
        },
        {
            "priority": "high" if has_previous_refusal else "medium",
            "title": "Review refusal or risk history",
            "detail": "Prepare a refusal repair note and evidence map before relying on this route." if has_previous_refusal else "Keep refusal-risk notes available; no previous refusal was declared in the current profile.",
        },
    ]

    sections = [
        _section(
            "executive_summary",
            "Executive summary",
            f"{full_name} is preparing a {route_plan['label'].lower()} from {current_country} to {target_country}. The starter readiness score is {score}/100 ({readiness_level}) with {risk_level} risk. This report is advisory and should be refreshed after official source review.",
            {"readiness_score": score, "readiness_level": readiness_level, "risk_level": risk_level},
        ),
        _section(
            "profile_snapshot",
            "Profile snapshot",
            f"Goal: {goal}. Route category: {route_category}. Timeline: {timeline_months or 'not provided'} months. Family members joining: {family_members}. Available funds: {_money(funds_amount, funds_currency)}.",
            {
                "goal": goal,
                "route_category": route_category,
                "timeline_months": timeline_months,
                "family_members_count": family_members,
                "available_funds_amount": funds_amount,
                "available_funds_currency": funds_currency,
            },
        ),
        _section(
            "route_fit",
            "Route fit questions",
            "Key questions to answer before treating this pathway as serious: " + " ".join(f"{idx}. {question}" for idx, question in enumerate(route_plan["route_questions"], start=1)),
            {"questions": route_plan["route_questions"]},
        ),
        _section(
            "document_readiness",
            "Document readiness",
            "Required starter documents: " + "; ".join(required_documents) + ". " + ("Missing or not confirmed: " + "; ".join(missing_documents) + "." if missing_documents else "The submitted document list covers the starter required categories."),
            {"required_documents": required_documents, "recommended_documents": recommended_documents, "missing_documents": missing_documents, "matched_documents": matched_documents},
        ),
        _section(
            "funds_budget",
            "Funds and budget pressure",
            f"Entered funds are {_money(funds_amount, funds_currency)}. The starter planning threshold for this route category is {_money(minimum_funds, funds_currency)}. " + (f"The visible planning gap is about {_money(starter_gap, funds_currency)} before official proof-of-funds rules, fees, family costs, and arrival reserve are reviewed." if starter_gap > 0 else "This meets the starter threshold, but official proof-of-funds, fee, family, and arrival-reserve rules must still be checked."),
            {"starter_threshold": minimum_funds, "entered_funds": funds_amount, "visible_gap": starter_gap, "currency": funds_currency},
        ),
        _section(
            "risk_flags",
            "Risk flags",
            "Current flags: " + ("; ".join(readiness_flags) if readiness_flags else "No major starter flags were detected from the entered profile."),
            {"flags": readiness_flags, "strengths": strengths},
        ),
        _section(
            "action_plan",
            "30-day action plan",
            "Next actions: " + " ".join(f"{idx}. {item['title']} — {item['detail']}" for idx, item in enumerate(action_items, start=1)),
            {"action_items": action_items},
        ),
        _section(
            "trust_notice",
            "Trust and source notice",
            "MoveReady does not guarantee visa approval, admission, job offers, lottery selection, ballot success, or provider acceptance. Treat this as a readiness report that must remain tied to official sources, review dates, and risk labels.",
            {"source_status": "starter_rules_pending_official_review", "guarantee": False},
        ),
    ]

    return {
        "report_ref": new_report_ref(),
        "report_title": f"{target_country} {route_plan['label']} Readiness Report",
        "risk_level": risk_level,
        "status": "generated",
        "source_status": "starter_rules_pending_official_review",
        "source_confidence": "starter",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "readiness_score": score,
        "readiness_level": readiness_level,
        "readiness_flags": readiness_flags,
        "strengths": strengths,
        "required_documents": required_documents,
        "recommended_documents": recommended_documents,
        "missing_documents": missing_documents,
        "action_items": action_items,
        "input_summary": {
            "goal": goal,
            "route_category": route_category,
            "current_country": current_country,
            "target_country": target_country,
            "family_members_count": family_members,
            "timeline_months": timeline_months,
            "available_funds_amount": funds_amount,
            "available_funds_currency": funds_currency,
            "has_previous_refusal": has_previous_refusal,
        },
        "sections": sections,
    }
