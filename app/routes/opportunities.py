from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase

bp = Blueprint("opportunities", __name__)

OPPORTUNITY_COLUMNS = (
    "id,opportunity_code,country_code,country_name,opportunity_name,opportunity_type,"
    "route_category,availability_status,official_url,result_check_url,summary,eligibility_summary,"
    "application_window_summary,safety_notes,source_confidence,last_verified_at,next_review_due_at,tags,is_public"
)


def _fallback_opportunities() -> List[Dict[str, Any]]:
    return [
        {
            "opportunity_code": "US-DV",
            "country_code": "US",
            "country_name": "United States",
            "opportunity_name": "Diversity Visa Program",
            "opportunity_type": "lottery",
            "availability_status": "monitoring",
            "official_url": "https://travel.state.gov/content/travel/en/us-visas/immigrate/diversity-visa-program-entry.html",
            "result_check_url": "https://dvprogram.state.gov/",
            "summary": "Annual diversity immigrant visa route for eligible people from qualifying countries.",
            "eligibility_summary": "Eligibility depends on country rules plus education or work-experience requirements published by the U.S. Department of State.",
            "application_window_summary": "Registration windows must be verified on the official Department of State website.",
            "safety_notes": "Use only the official E-DV website. Do not submit duplicate entries. No one can guarantee selection.",
            "source_confidence": "high",
            "tags": ["usa", "diversity visa", "lottery", "official-only"],
        },
        {
            "opportunity_code": "CA-IEC",
            "country_code": "CA",
            "country_name": "Canada",
            "opportunity_name": "International Experience Canada invitation pools",
            "opportunity_type": "invitation_pool",
            "availability_status": "open",
            "official_url": "https://ircc.canada.ca/english/work/iec/selections.asp",
            "summary": "Invitation-pool system for eligible youth from partner countries and territories to work and travel in Canada.",
            "eligibility_summary": "Eligibility depends on citizenship or territory, age, category, quota, admissibility, and season rules.",
            "application_window_summary": "IRCC publishes country-specific spots, invitation chances, and dates.",
            "safety_notes": "Selection is not guaranteed. Follow official IRCC instructions and deadlines after invitation.",
            "source_confidence": "high",
            "tags": ["canada", "iec", "working holiday", "invitation pool"],
        },
        {
            "opportunity_code": "AU-462-BALLOT",
            "country_code": "AU",
            "country_name": "Australia",
            "opportunity_name": "Work and Holiday subclass 462 ballot and country caps",
            "opportunity_type": "ballot",
            "availability_status": "monitoring",
            "official_url": "https://immi.homeaffairs.gov.au/what-we-do/whm-program/status-of-country-caps",
            "summary": "Work and Holiday route with annual caps for some countries and ballot arrangements for selected high-demand countries.",
            "eligibility_summary": "Eligibility depends on passport country, age, education, funds, health, character, and country-specific subclass 462 rules.",
            "application_window_summary": "Program year runs from 1 July to 30 June. Check Home Affairs for current caps and ballot rules.",
            "safety_notes": "Ballot selection only allows a person to apply. It does not guarantee visa grant.",
            "source_confidence": "high",
            "tags": ["australia", "subclass 462", "ballot", "country cap"],
        },
        {
            "opportunity_code": "UK-IYPS",
            "country_code": "GB",
            "country_name": "United Kingdom",
            "opportunity_name": "India Young Professionals Scheme ballot",
            "opportunity_type": "ballot",
            "availability_status": "monitoring",
            "official_url": "https://www.gov.uk/guidance/india-young-professionals-scheme-visa-ballot-system",
            "summary": "Ballot route for eligible Indian citizens who want to apply under the India Young Professionals Scheme visa.",
            "eligibility_summary": "Eligibility includes Indian citizenship, age rules, qualification and savings requirements, and ballot selection before application.",
            "application_window_summary": "Ballot dates and entry instructions are published by GOV.UK before each opening.",
            "safety_notes": "Entering the ballot is not approval. Use only official GOV.UK guidance.",
            "source_confidence": "high",
            "tags": ["uk", "india", "young professionals", "ballot"],
        },
    ]


def _match_text(row: Dict[str, Any], query: str) -> bool:
    haystack = " ".join(
        str(row.get(key) or "") for key in ["opportunity_code", "country_name", "opportunity_name", "summary", "eligibility_summary"]
    ).lower()
    return query.lower() in haystack


@bp.get("")
@bp.get("/")
def opportunities():
    country_code = (request.args.get("country_code") or "").strip().upper()
    opportunity_type = (request.args.get("type") or "").strip()
    status = (request.args.get("status") or "").strip()
    q = (request.args.get("q") or "").strip()

    rows: Optional[List[Dict[str, Any]]]
    try:
        query = (
            get_supabase()
            .table("relocation_opportunities")
            .select(OPPORTUNITY_COLUMNS)
            .eq("is_public", True)
            .order("country_name")
        )
        if country_code:
            query = query.eq("country_code", country_code)
        if opportunity_type:
            query = query.eq("opportunity_type", opportunity_type)
        if status:
            query = query.eq("availability_status", status)
        rows = query.execute().data or []
    except Exception:
        rows = _fallback_opportunities()
        if country_code:
            rows = [row for row in rows if row.get("country_code") == country_code]
        if opportunity_type:
            rows = [row for row in rows if row.get("opportunity_type") == opportunity_type]
        if status:
            rows = [row for row in rows if row.get("availability_status") == status]

    if q:
        rows = [row for row in rows if _match_text(row, q)]

    return jsonify({"ok": True, "opportunities": rows, "source_status": "database_backed" if rows and rows[0].get("id") else "starter_fallback"})


@bp.get("/<opportunity_code>")
def opportunity_detail(opportunity_code: str):
    code = opportunity_code.strip().upper()
    try:
        response = (
            get_supabase()
            .table("relocation_opportunities")
            .select("*")
            .eq("opportunity_code", code)
            .eq("is_public", True)
            .maybe_single()
            .execute()
        )
        row = response.data
        if row:
            return jsonify({"ok": True, "opportunity": row, "source_status": "database_backed"})
    except Exception:
        pass

    row = next((item for item in _fallback_opportunities() if item.get("opportunity_code") == code), None)
    if not row:
        return jsonify({"ok": False, "error": "opportunity_not_found"}), 404
    return jsonify({"ok": True, "opportunity": row, "source_status": "starter_fallback"})
