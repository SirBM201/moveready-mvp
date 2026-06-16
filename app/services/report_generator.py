from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def new_report_ref() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"MRR-{stamp}-{uuid4().hex[:8].upper()}"


def build_readiness_report(payload: dict) -> dict:
    goal = str(payload.get("goal") or "relocation").strip() or "relocation"
    target_country = str(payload.get("target_country") or payload.get("targetCountry") or "Target country").strip()
    current_country = str(payload.get("current_country") or payload.get("currentCountry") or "Current country").strip()
    route_category = str(payload.get("route_category") or payload.get("routeCategory") or goal).strip()
    funds_amount = payload.get("available_funds_amount") or payload.get("availableFundsAmount")
    funds_currency = payload.get("available_funds_currency") or payload.get("availableFundsCurrency") or "USD"
    family_members = int(payload.get("family_members_count") or payload.get("familyMembersCount") or 0)

    risk_level = "medium"
    if route_category in {"work", "family", "protection"}:
        risk_level = "high"
    if route_category in {"visit"}:
        risk_level = "medium"

    readiness_flags = []
    if not target_country or target_country == "Target country":
        readiness_flags.append("Target country not clearly selected")
    if not funds_amount:
        readiness_flags.append("Available funds not provided")
    if family_members > 0:
        readiness_flags.append("Family-member planning needed")

    sections = [
        {
            "section_key": "profile_summary",
            "section_title": "Profile summary",
            "section_content": f"The user is exploring a {route_category} pathway from {current_country} to {target_country}.",
        },
        {
            "section_key": "route_readiness",
            "section_title": "Route readiness",
            "section_content": "Confirm route eligibility from official sources before paying advisers, booking travel, or submitting documents.",
        },
        {
            "section_key": "document_readiness",
            "section_title": "Document readiness",
            "section_content": "Prepare passport, purpose evidence, proof of funds, civil documents, insurance evidence, and route-specific supporting documents.",
        },
        {
            "section_key": "funds_budget",
            "section_title": "Funds and budget",
            "section_content": f"Available funds recorded: {funds_amount or 'not provided'} {funds_currency}. Compare this against official proof-of-funds and first-arrival costs.",
        },
        {
            "section_key": "next_steps",
            "section_title": "Next steps",
            "section_content": "Select a specific route, review official source pages, generate a detailed checklist, estimate budget, and refresh the report after route facts are approved.",
        },
    ]

    return {
        "report_ref": new_report_ref(),
        "report_title": f"{target_country} {route_category.title()} Readiness Report",
        "risk_level": risk_level,
        "status": "generated",
        "source_status": "starter_rules_pending_official_review",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "readiness_flags": readiness_flags,
        "input_summary": {
            "goal": goal,
            "route_category": route_category,
            "current_country": current_country,
            "target_country": target_country,
            "family_members_count": family_members,
            "available_funds_amount": funds_amount,
            "available_funds_currency": funds_currency,
        },
        "sections": sections,
    }
