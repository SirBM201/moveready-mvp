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
            "route_category": "immigrant_lottery",
            "availability_status": "monitoring",
            "official_url": "https://travel.state.gov/content/travel/en/us-visas/immigrate/diversity-visa-program-entry.html",
            "result_check_url": "https://dvprogram.state.gov/",
            "summary": "Annual Diversity Visa route for eligible people from qualifying countries. MoveReady tracks official entry, result-check, document, and scam-safety reminders.",
            "eligibility_summary": "Eligibility depends on country rules plus education or work-experience requirements published by the U.S. Department of State.",
            "application_window_summary": "Registration and result-check windows must be verified from the official Department of State pages for each program year.",
            "safety_notes": "There is no paid advantage, no guaranteed selection, and duplicate entries can create serious risk. Users should keep their confirmation number and use the official E-DV website only.",
            "source_confidence": "high",
            "tags": ["usa", "diversity visa", "lottery", "green card", "official-only", "scam-warning"],
        },
        {
            "opportunity_code": "CA-IEC",
            "country_code": "CA",
            "country_name": "Canada",
            "opportunity_name": "International Experience Canada invitation pools",
            "opportunity_type": "invitation_pool",
            "route_category": "working_holiday",
            "availability_status": "open",
            "official_url": "https://ircc.canada.ca/english/work/iec/selections.asp",
            "summary": "Invitation-pool system for eligible youth from partner countries and territories to work and travel in Canada.",
            "eligibility_summary": "Eligibility depends on citizenship or territory, age, category, quota, admissibility, and season rules.",
            "application_window_summary": "IRCC publishes country-specific key dates, available spots, invitation chances, and normally updates pool numbers weekly during the season.",
            "safety_notes": "Creating a profile or entering a pool does not guarantee an invitation or final approval. Users must follow official IRCC deadlines after invitation.",
            "source_confidence": "high",
            "tags": ["canada", "iec", "working holiday", "invitation pool", "youth mobility"],
        },
        {
            "opportunity_code": "AU-462-BALLOT",
            "country_code": "AU",
            "country_name": "Australia",
            "opportunity_name": "Work and Holiday subclass 462 ballot and country caps",
            "opportunity_type": "ballot",
            "route_category": "working_holiday",
            "availability_status": "monitoring",
            "official_url": "https://immi.homeaffairs.gov.au/what-we-do/whm-program/status-of-country-caps",
            "summary": "Work and Holiday route with annual caps for some countries and ballot arrangements for selected high-demand countries.",
            "eligibility_summary": "Eligibility depends on passport country, age, education, funds, health, character, and country-specific subclass 462 rules.",
            "application_window_summary": "Program year runs from 1 July to 30 June. Country cap status may be open, paused, or closed and must be checked on Home Affairs.",
            "safety_notes": "A ballot or open cap only allows a person to apply. It does not guarantee visa grant.",
            "source_confidence": "high",
            "tags": ["australia", "subclass 462", "work and holiday", "ballot", "country cap"],
        },
        {
            "opportunity_code": "UK-IYPS",
            "country_code": "GB",
            "country_name": "United Kingdom",
            "opportunity_name": "India Young Professionals Scheme ballot",
            "opportunity_type": "ballot",
            "route_category": "youth_mobility",
            "availability_status": "monitoring",
            "official_url": "https://www.gov.uk/guidance/india-young-professionals-scheme-visa-ballot-system",
            "summary": "Ballot route for eligible Indian citizens who want to apply under the India Young Professionals Scheme visa.",
            "eligibility_summary": "Eligibility includes Indian citizenship, age rules, qualification and savings requirements, and ballot selection before application.",
            "application_window_summary": "GOV.UK publishes ballot opening and closing dates before each round. The first 2026 ballot has closed and the page should be monitored for the next 2026 ballot.",
            "safety_notes": "Entering the ballot is not approval. Users should use GOV.UK only and must still meet all visa requirements if selected.",
            "source_confidence": "high",
            "tags": ["uk", "india", "young professionals", "ballot", "youth mobility"],
        },
        {
            "opportunity_code": "NZ-PAC",
            "country_code": "NZ",
            "country_name": "New Zealand",
            "opportunity_name": "Pacific Access Category Resident Visa ballot",
            "opportunity_type": "ballot",
            "route_category": "resident_quota",
            "availability_status": "results_open",
            "official_url": "https://www.immigration.govt.nz/visas/pacific-access-category-resident-visa/",
            "result_check_url": "https://www.immigration.govt.nz/live/resident-visas-to-live-in-new-zealand/resident-visas-for-samoa-kiribati-tuvalu-tonga-and-fiji-nationals/pacific-access-category-resident-visa-ballot-results/",
            "summary": "Annual ballot route that can lead selected eligible citizens of Fiji, Kiribati, Tonga, and Tuvalu toward New Zealand residence.",
            "eligibility_summary": "Eligibility is limited to eligible citizens of Fiji, Kiribati, Tonga, or Tuvalu, with age, birth/parentage, location, health, character, job offer, and family requirements.",
            "application_window_summary": "The 2026 ballot results have been published. Future registration reopening dates should be checked directly with Immigration New Zealand.",
            "safety_notes": "A drawn ballot number is not final residence approval. Users should keep their registration number and follow official INZ invitation instructions.",
            "source_confidence": "high",
            "tags": ["new zealand", "pacific access category", "pac", "ballot", "quota", "residence"],
        },
        {
            "opportunity_code": "NZ-SQ",
            "country_code": "NZ",
            "country_name": "New Zealand",
            "opportunity_name": "Samoan Quota Resident Visa ballot",
            "opportunity_type": "ballot",
            "route_category": "resident_quota",
            "availability_status": "results_open",
            "official_url": "https://www.immigration.govt.nz/visas/samoan-quota-resident-visa/",
            "result_check_url": "https://www.immigration.govt.nz/live/resident-visas-to-live-in-new-zealand/resident-visas-for-samoa-kiribati-tuvalu-tonga-and-fiji-nationals/samoan-quota-resident-visa-ballot-results/",
            "summary": "Annual quota ballot allowing selected eligible Samoan citizens to apply for New Zealand residence.",
            "eligibility_summary": "Eligibility is limited to eligible Samoan citizens, with age, birth/parentage, location, health, character, job offer, income, English, and family requirements.",
            "application_window_summary": "The 2026 ballot results have been published. Future opening dates should be monitored directly on Immigration New Zealand.",
            "safety_notes": "A ballot draw is not final approval. Users should keep their registration number and follow official INZ instructions if selected.",
            "source_confidence": "high",
            "tags": ["new zealand", "samoan quota", "sq", "ballot", "quota", "residence"],
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
