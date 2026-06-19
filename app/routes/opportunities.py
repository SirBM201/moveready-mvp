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
        {
            "opportunity_code": "JP-WH",
            "country_code": "JP",
            "country_name": "Japan",
            "opportunity_name": "Working Holiday Programme",
            "opportunity_type": "annual_quota",
            "route_category": "working_holiday",
            "availability_status": "monitoring",
            "official_url": "https://www.mofa.go.jp/j_info/visit/w_holiday/index.html",
            "summary": "Partner-country working holiday route for eligible young people who want an extended holiday in Japan with incidental work rights.",
            "eligibility_summary": "Eligibility depends on nationality, age, quota, funds, health, character, and embassy-specific instructions for the applicant's country.",
            "application_window_summary": "Opening windows and quota handling vary by partner country and Japanese mission. Users should verify the current embassy instruction before applying.",
            "safety_notes": "This is a holiday-first route and should not be treated as a guaranteed employment, skilled work, or permanent migration pathway.",
            "source_confidence": "high",
            "tags": ["japan", "working holiday", "youth mobility", "annual quota", "embassy"],
        },
        {
            "opportunity_code": "KR-WH",
            "country_code": "KR",
            "country_name": "South Korea",
            "opportunity_name": "Working Holiday Visa",
            "opportunity_type": "annual_quota",
            "route_category": "working_holiday",
            "availability_status": "monitoring",
            "official_url": "https://whic.mofa.go.kr/contents.do?contentsNo=38&menuNo=90",
            "summary": "Working holiday route for eligible young people from Korea's partner countries who want a temporary holiday stay with limited work rights.",
            "eligibility_summary": "Eligibility depends on nationality, age, quota, funds, insurance, purpose of stay, and Korean mission instructions.",
            "application_window_summary": "Quota and intake handling vary by country agreement and consular process. Users should verify the current national quota and application channel.",
            "safety_notes": "This route is not a dependant, permanent migration, or guaranteed employment route. Users must follow country-specific working holiday conditions.",
            "source_confidence": "high",
            "tags": ["korea", "south korea", "working holiday", "youth mobility", "quota"],
        },
        {
            "opportunity_code": "HK-WHS",
            "country_code": "HK",
            "country_name": "Hong Kong",
            "opportunity_name": "Working Holiday Scheme",
            "opportunity_type": "first_come_quota",
            "route_category": "working_holiday",
            "availability_status": "monitoring",
            "official_url": "https://www.immd.gov.hk/eng/services/visas/working_holiday_scheme.html",
            "summary": "Working Holiday Scheme for eligible nationals of participating countries, with annual quotas and first-come quota pressure for some routes.",
            "eligibility_summary": "Eligibility depends on participating nationality, age, financial means, insurance, travel purpose, and Immigration Department requirements.",
            "application_window_summary": "Annual country quotas and availability should be checked directly from the Hong Kong Immigration Department before applying.",
            "safety_notes": "Temporary work and short study must stay within scheme conditions. Users should not assume dependants or repeat use are available.",
            "source_confidence": "high",
            "tags": ["hong kong", "working holiday", "annual quota", "first come", "youth mobility"],
        },
        {
            "opportunity_code": "IE-WHA",
            "country_code": "IE",
            "country_name": "Ireland",
            "opportunity_name": "Working Holiday Authorisation",
            "opportunity_type": "annual_quota",
            "route_category": "working_holiday",
            "availability_status": "monitoring",
            "official_url": "https://www.ireland.ie/en/usa/washington/services/visas/working-holiday-authorisation/",
            "summary": "Country-specific working holiday authorisation route for eligible young people from Ireland's partner countries.",
            "eligibility_summary": "Eligibility, age, fees, validity, permitted work, and application channel vary by citizenship and Irish mission location.",
            "application_window_summary": "Users should verify the Ireland.ie page for their citizenship and local Irish mission before relying on availability or timing.",
            "safety_notes": "A working holiday authorisation should not be confused with ordinary visitor status or a guaranteed right to long-term residence.",
            "source_confidence": "high",
            "tags": ["ireland", "working holiday", "authorisation", "youth mobility", "country specific"],
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
