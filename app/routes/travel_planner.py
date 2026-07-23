from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase


bp = Blueprint("travel_planner", __name__)


TRIP_PURPOSES = [
    "tourism",
    "family_visit",
    "business_visit",
    "conference",
    "study_arrival",
    "work_arrival",
    "relocation_arrival",
    "medical",
    "transit",
    "other",
]

BOOKING_NEEDS = [
    "flight",
    "hotel",
    "short_stay_apartment",
    "airport_pickup",
    "intercity_transport",
    "travel_insurance",
    "local_sim",
    "other",
]



def _text(value: Any, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]



def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value, 20).lower() in {"1", "true", "yes", "y", "on"}



def _int(value: Any, default: int = 0, minimum: int = 0, maximum: int = 100) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return min(max(parsed, minimum), maximum)



def _float(value: Any, default: float = 0.0, minimum: float = 0.0, maximum: float = 1_000_000_000.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    return min(max(parsed, minimum), maximum)



def _date(value: Any) -> Optional[date]:
    raw = _text(value, 40)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None



def _list(value: Any, allowed: set[str], limit: int = 12) -> List[str]:
    if not isinstance(value, list):
        return []
    output: List[str] = []
    for item in value:
        cleaned = _text(item, 80)
        if cleaned in allowed and cleaned not in output:
            output.append(cleaned)
        if len(output) >= limit:
            break
    return output



def _risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"



def _readiness_status(risk_level: str) -> str:
    if risk_level == "high":
        return "not_ready_to_book"
    if risk_level == "medium":
        return "review_before_booking"
    return "ready_for_price_comparison"



def _store_run(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    result["stored"] = False
    try:
        row = {
            "tool_slug": "trip_readiness_plan",
            "status": "completed",
            "risk_level": result.get("risk_level"),
            "readiness_status": result.get("readiness_status"),
            "input_payload": payload,
            "result_payload": result,
            "source_page": _text(payload.get("source_page"), 240) or None,
        }
        response = get_supabase().table("relocation_readiness_check_runs").insert(row).execute()
        stored = (response.data or [None])[0]
        if stored:
            result["stored"] = True
            result["id"] = stored.get("id")
    except Exception:
        result["storage_note"] = "The trip plan was generated but could not be saved. Run the readiness storage SQL if account recovery is required."
    return result



def _approved_travel_providers(target_country: str, needs: List[str]) -> List[Dict[str, Any]]:
    try:
        response = (
            get_supabase()
            .table("relocation_partner_applications")
            .select(
                "id,provider_type,provider_label,business_name,website_url,country,city,service_countries,"
                "service_summary,credentials_summary,preferred_contact_channel,public_status,metadata"
            )
            .eq("public_status", "approved_public")
            .limit(100)
            .execute()
        )
        target = target_country.strip().lower()
        requested = {item.lower() for item in needs}
        rows: List[Dict[str, Any]] = []
        for row in response.data or []:
            provider_type = _text(row.get("provider_type"), 100).lower()
            label = _text(row.get("provider_label"), 160).lower()
            summary = _text(row.get("service_summary"), 800).lower()
            service_countries = [str(item).strip().lower() for item in (row.get("service_countries") or [])]
            service_text = " ".join([provider_type, label, summary])

            travel_match = any(
                token in service_text
                for token in ["flight", "hotel", "accommodation", "airport", "transport", "travel", "insurance", "sim"]
            )
            need_match = not requested or any(need.replace("_", " ") in service_text for need in requested)
            country_match = not target or not service_countries or target in service_countries or "global" in service_countries
            if travel_match and need_match and country_match:
                rows.append(
                    {
                        "id": row.get("id"),
                        "provider_type": row.get("provider_type"),
                        "provider_label": row.get("provider_label"),
                        "business_name": row.get("business_name"),
                        "website_url": row.get("website_url"),
                        "country": row.get("country"),
                        "city": row.get("city"),
                        "service_countries": row.get("service_countries") or [],
                        "service_summary": row.get("service_summary"),
                        "credentials_summary": row.get("credentials_summary"),
                        "preferred_contact_channel": row.get("preferred_contact_channel"),
                        "approval_status": "approved_public",
                    }
                )
        return rows[:20]
    except Exception:
        return []


@bp.get("/options")
def travel_options():
    return jsonify(
        {
            "ok": True,
            "trip_purposes": TRIP_PURPOSES,
            "booking_needs": BOOKING_NEEDS,
            "affiliate_policy": "MoveReady may later earn a referral commission from clearly disclosed approved links. Commission must not change the price shown to the user or the safety ranking.",
            "safety_note": "A booking is not evidence of entry permission. Confirm visa, passport, transit, airline, border, insurance, health, ticket, accommodation, funds, and personal-history requirements first.",
        }
    )


@bp.post("/trip-plan")
def trip_plan():
    payload = request.get_json(silent=True) or {}

    departure_country = _text(payload.get("departure_country"), 120)
    destination_country = _text(payload.get("destination_country"), 120)
    destination_city = _text(payload.get("destination_city"), 120)
    passport_country = _text(payload.get("passport_country"), 120)
    trip_purpose = _text(payload.get("trip_purpose"), 80) or "tourism"
    departure_date = _date(payload.get("departure_date"))
    return_date = _date(payload.get("return_date"))
    adults = max(1, _int(payload.get("adults"), 1, 1, 20))
    children = _int(payload.get("children"), 0, 0, 20)
    infants = _int(payload.get("infants"), 0, 0, 10)
    booking_needs = _list(payload.get("booking_needs"), set(BOOKING_NEEDS))

    passport_valid_months = _int(payload.get("passport_valid_months"), 0, 0, 240)
    destination_entry_rule_checked = _bool(payload.get("destination_entry_rule_checked"))
    visa_or_authorization_confirmed = _bool(payload.get("visa_or_authorization_confirmed"))
    transit_rule_checked = _bool(payload.get("transit_rule_checked"))
    travel_insurance_confirmed = _bool(payload.get("travel_insurance_confirmed"))
    accommodation_confirmed = _bool(payload.get("accommodation_confirmed"))
    onward_or_return_ticket_planned = _bool(payload.get("onward_or_return_ticket_planned"))
    funds_plan_confirmed = _bool(payload.get("funds_plan_confirmed"))
    prior_refusal_or_denied_admission = _bool(payload.get("prior_refusal_or_denied_admission"))
    visa_validity_uncertain = _bool(payload.get("visa_validity_uncertain"))
    special_medical_or_accessibility_need = _bool(payload.get("special_medical_or_accessibility_need"))

    trip_budget = _float(payload.get("trip_budget_amount"), 0)
    currency = _text(payload.get("currency"), 20) or "USD"
    household_size = adults + children + infants

    risk_score = 0
    warnings: List[str] = []

    if not destination_entry_rule_checked:
        warnings.append("The destination entry rule has not been checked from an official or reviewed source.")
        risk_score += 30
    if not visa_or_authorization_confirmed:
        warnings.append("Required visa, eVisa, eTA, exemption, residence document, or other travel authorization is not confirmed.")
        risk_score += 30
    if visa_validity_uncertain:
        warnings.append("A selected visa or status may be cancelled, revoked, limited, expired, electronically invalid, or otherwise uncertain. Do not rely on the sticker alone.")
        risk_score += 35
    if passport_valid_months < 6:
        warnings.append("The passport has fewer than six months of recorded remaining validity. Confirm the destination and airline rule before booking.")
        risk_score += 25
    if not transit_rule_checked:
        warnings.append("Transit-airport and transit-country requirements are not confirmed.")
        risk_score += 20
    if not onward_or_return_ticket_planned and trip_purpose not in {"relocation_arrival", "work_arrival", "study_arrival"}:
        warnings.append("Return or onward travel evidence is not planned for a temporary trip.")
        risk_score += 15
    if not accommodation_confirmed:
        warnings.append("Accommodation is not confirmed. Use a refundable or flexible booking until entry and travel conditions are clear.")
        risk_score += 15
    if not travel_insurance_confirmed:
        warnings.append("Travel or route-required insurance is not confirmed.")
        risk_score += 15
    if not funds_plan_confirmed:
        warnings.append("Trip funds and border-evidence planning are not confirmed.")
        risk_score += 15
    if prior_refusal_or_denied_admission:
        warnings.append("A previous refusal, denied admission, or withdrawal may affect visa validity, disclosure duties, airline checks, or border questioning. Confirm the record before relying on a third-country benefit.")
        risk_score += 25
    if departure_date:
        days_until_departure = (departure_date - date.today()).days
        if days_until_departure < 0:
            warnings.append("The departure date is in the past.")
            risk_score += 70
        elif days_until_departure <= 7:
            warnings.append("Departure is within seven days, leaving little time to correct documents, transit, insurance, accommodation, or visa issues.")
            risk_score += 25
        elif days_until_departure <= 21:
            warnings.append("Departure is close. Prefer flexible or refundable bookings until all travel conditions are confirmed.")
            risk_score += 10
    else:
        days_until_departure = None

    if departure_date and return_date and return_date < departure_date:
        warnings.append("The return date is earlier than the departure date.")
        risk_score += 70
    if household_size >= 5:
        warnings.append("A larger travelling group increases fare, room, baggage, seating, consent, insurance, accessibility, and transfer complexity.")
        risk_score += 10
    if special_medical_or_accessibility_need:
        warnings.append("Medical, medication, mobility, pregnancy, dietary, or accessibility arrangements need direct confirmation with airline, accommodation, insurer, and local provider.")
        risk_score += 15

    risk_level = _risk_level(risk_score)
    providers = _approved_travel_providers(destination_country, booking_needs)

    booking_sequence = [
        {
            "stage": "1. Confirm permission and documents",
            "actions": [
                "Check the current official destination entry rule for the passport and travel purpose.",
                "Confirm any visa, eVisa, eTA, exemption, residence document, previous-use condition, multiple-entry condition, and remaining-validity condition.",
                "Check passport validity, blank pages, transit visas, airline document rules, health requirements, and any prior immigration-history implications.",
            ],
        },
        {
            "stage": "2. Build a flexible itinerary",
            "actions": [
                "Compare direct and transit routes, airport changes, self-transfer risk, baggage re-check, minimum connection time, overnight transit, and terminal changes.",
                "Avoid non-refundable tickets until the visa, authorization, transit, leave, appointment, or relocation timing is sufficiently certain.",
                "Keep enough time for border control, baggage, children, accessibility, local transport, and arrival accommodation check-in.",
            ],
        },
        {
            "stage": "3. Compare total booking cost",
            "actions": [
                "Compare total fare after baggage, seat, payment, change, cancellation, resort, cleaning, local tax, and transfer charges.",
                "Check whether the seller is the airline, hotel, licensed agency, approved provider, or an intermediary with different support and refund rules.",
                "Save screenshots, confirmation emails, receipts, fare rules, cancellation terms, and provider contact details.",
            ],
        },
        {
            "stage": "4. Verify accommodation and transport",
            "actions": [
                "Verify address, host or property identity, check-in process, cancellation terms, accessibility, family capacity, local registration, and neighbourhood transport.",
                "Do not pay an unverified landlord, driver, host, or agent outside an approved platform or documented contract.",
                "For airport pickup or intercity transport, confirm driver identity, meeting point, delay policy, luggage capacity, child seat, accessibility, and emergency contact.",
            ],
        },
        {
            "stage": "5. Prepare for travel day",
            "actions": [
                "Carry passport, visa or authorization evidence, ticket, accommodation, funds, insurance, invitation or purpose documents, prescriptions, and emergency contacts.",
                "Keep copies separate from originals and do not share confirmation numbers, passport images, or payment details with unverified persons.",
                "Re-check flight, terminal, entry, transit, weather, strike, health, and local transport information shortly before departure.",
            ],
        },
    ]

    result = {
        "ok": True,
        "departure_country": departure_country,
        "destination_country": destination_country,
        "destination_city": destination_city,
        "passport_country": passport_country,
        "trip_purpose": trip_purpose,
        "departure_date": departure_date.isoformat() if departure_date else None,
        "return_date": return_date.isoformat() if return_date else None,
        "days_until_departure": days_until_departure,
        "traveller_count": household_size,
        "booking_needs": booking_needs,
        "trip_budget_amount": trip_budget or None,
        "currency": currency,
        "risk_level": risk_level,
        "readiness_status": _readiness_status(risk_level),
        "summary": "A neutral trip-readiness and booking sequence has been generated. It does not confirm entry permission, ticket availability, room inventory, price, provider performance, refund, or border admission.",
        "warnings": warnings,
        "booking_sequence": booking_sequence,
        "approved_provider_count": len(providers),
        "approved_providers": providers,
        "provider_handoff_status": "approved_providers_available" if providers else "no_approved_travel_provider_listed_yet",
        "affiliate_disclosure": "MoveReady may later earn a referral commission from clearly labelled approved links. Any commission must be disclosed before the user clicks and must not replace independent price, safety, refund, or official-rule checks.",
        "fraud_checks": [
            "Do not pay for guaranteed visa approval, border entry, airline boarding, hotel availability, refund, or immigration clearance.",
            "Verify the domain, seller, payment recipient, cancellation policy, and customer-support channel before paying.",
            "Avoid off-platform transfers, gift cards, cryptocurrency, or pressure to pay before written terms are available.",
            "Use only approved public providers or independently verified major booking channels; MoveReady does not endorse unapproved listings.",
        ],
        "safety_note": "A valid ticket and hotel booking do not grant entry. Airline and border authorities can still refuse boarding or admission under current rules and personal circumstances.",
    }
    return jsonify(_store_run(payload, result))
