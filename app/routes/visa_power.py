from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from flask import Blueprint, jsonify, request

bp = Blueprint("visa_power", __name__)

HELD_VISA_OPTIONS: List[Dict[str, str]] = [
    {
        "code": "canada_visitor",
        "label": "Canada visitor visa",
        "helper": "Valid Canadian visitor visa in the user's passport.",
    },
    {
        "code": "us_visitor",
        "label": "U.S. visitor visa",
        "helper": "Valid U.S. visitor visa, such as B1/B2 where accepted by the destination rule.",
    },
    {
        "code": "uk_visitor",
        "label": "UK visitor visa",
        "helper": "Valid UK visitor visa where accepted by the destination rule.",
    },
    {
        "code": "schengen_visitor",
        "label": "Schengen visitor visa",
        "helper": "Valid Schengen short-stay visitor visa where accepted by the destination rule.",
    },
    {
        "code": "australia_visitor",
        "label": "Australia visitor visa",
        "helper": "Valid Australia visitor visa where accepted by the destination rule.",
    },
    {
        "code": "japan_visitor",
        "label": "Japan visitor visa",
        "helper": "Valid Japan visitor visa where accepted by the destination rule.",
    },
]

PASSPORT_INDEX_RECORDS: List[Dict[str, Any]] = [
    {
        "country_key": "nigeria",
        "country": "Nigeria",
        "region": "West Africa",
        "passport_strength_band": "starter",
        "passport_opportunity_score": 45,
        "visa_free_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_on_arrival_count_estimate": "Use official passport-index source before showing exact public count",
        "evisa_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_required_count_estimate": "High for Europe, North America, Australia, and many OECD destinations",
        "summary": "A Nigerian passport can support regional and selected leisure travel, but many study, work, tourism, and relocation destinations require a visa or eVisa. Existing strong visas can materially improve short-trip options.",
        "visa_free_examples": [
            {"destination": "ECOWAS destinations", "access_type": "Regional mobility", "stay": "Varies by destination", "conditions": "Carry a valid passport or accepted regional travel document and confirm destination-specific entry conditions."},
            {"destination": "Selected Caribbean and African destinations", "access_type": "Visa-free examples", "stay": "Varies", "conditions": "Confirm official immigration pages before booking because rules and airline checks can change."},
        ],
        "visa_on_arrival_examples": [
            {"destination": "Selected African, Asian, and island destinations", "access_type": "Visa on arrival examples", "stay": "Varies", "conditions": "Check airline boarding rules, fees, hotel/funds evidence, and return/onward ticket requirements."},
        ],
        "evisa_examples": [
            {"destination": "Countries with online visa or ETA systems", "access_type": "eVisa / ETA", "stay": "Varies", "conditions": "Apply only through official government portals or verified partner pages listed by the government."},
        ],
        "visa_required_examples": [
            {"destination": "Canada, United States, United Kingdom, Schengen Area, Australia", "access_type": "Visa usually required", "stay": "Depends on visa issued", "conditions": "Prepare full purpose, funds, ties, travel history, and document evidence before applying."},
        ],
        "validity_notes": "Many destinations require a passport valid for at least 6 months beyond arrival or departure. Some require blank pages.",
        "renewal_notes": "Renew early if the passport will expire within 6 to 9 months of intended travel.",
        "official_source_priority": ["Destination government immigration site", "Embassy or consulate page", "Airline document checker", "Official eVisa or ETA portal"],
        "last_reviewed": "2026-07-20",
        "confidence": "starter_pending_official_review",
    },
    {
        "country_key": "ghana",
        "country": "Ghana",
        "region": "West Africa",
        "passport_strength_band": "starter",
        "passport_opportunity_score": 49,
        "visa_free_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_on_arrival_count_estimate": "Use official passport-index source before showing exact public count",
        "evisa_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_required_count_estimate": "High for many long-haul study, work, and relocation destinations",
        "summary": "A Ghanaian passport has useful regional and selected visitor access, but major relocation destinations still require careful visa planning. Strong visas can increase short-trip opportunities.",
        "visa_free_examples": [
            {"destination": "ECOWAS destinations", "access_type": "Regional mobility", "stay": "Varies by destination", "conditions": "Confirm passport validity, accepted travel document rules, and border requirements."},
            {"destination": "Selected African and Caribbean destinations", "access_type": "Visa-free examples", "stay": "Varies", "conditions": "Check current official source and airline boarding rules."},
        ],
        "visa_on_arrival_examples": [
            {"destination": "Selected African and Asian destinations", "access_type": "Visa on arrival examples", "stay": "Varies", "conditions": "Confirm fees, documents, return ticket, hotel address, and funds evidence."},
        ],
        "evisa_examples": [
            {"destination": "Countries with official online visa systems", "access_type": "eVisa / ETA", "stay": "Varies", "conditions": "Use only official portals or government-listed portals."},
        ],
        "visa_required_examples": [
            {"destination": "Canada, United States, United Kingdom, Schengen Area, Australia", "access_type": "Visa usually required", "stay": "Depends on visa issued", "conditions": "Check route-specific official document and proof-of-funds requirements."},
        ],
        "validity_notes": "Plan with at least 6 months passport validity unless the official destination rule says otherwise.",
        "renewal_notes": "Renew early before applying for long processing-time routes.",
        "official_source_priority": ["Destination government immigration site", "Embassy or consulate page", "Airline document checker", "Official eVisa or ETA portal"],
        "last_reviewed": "2026-07-20",
        "confidence": "starter_pending_official_review",
    },
    {
        "country_key": "kenya",
        "country": "Kenya",
        "region": "East Africa",
        "passport_strength_band": "starter",
        "passport_opportunity_score": 53,
        "visa_free_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_on_arrival_count_estimate": "Use official passport-index source before showing exact public count",
        "evisa_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_required_count_estimate": "Major long-haul relocation destinations usually require visa planning",
        "summary": "A Kenyan passport can be useful for regional and selected short-stay travel. For relocation, study, work, and family routes, users should still confirm visas, funds, and documents early.",
        "visa_free_examples": [
            {"destination": "Regional African destinations", "access_type": "Visa-free or simplified examples", "stay": "Varies", "conditions": "Confirm current regional arrangements and passport validity rules."},
        ],
        "visa_on_arrival_examples": [
            {"destination": "Selected African, Asian, and island destinations", "access_type": "Visa on arrival examples", "stay": "Varies", "conditions": "Check fees, hotel/funds evidence, and airline document checks."},
        ],
        "evisa_examples": [
            {"destination": "Countries with official online visa systems", "access_type": "eVisa / ETA", "stay": "Varies", "conditions": "Use official portals and verify processing time before travel."},
        ],
        "visa_required_examples": [
            {"destination": "Canada, United States, United Kingdom, Schengen Area, Australia", "access_type": "Visa usually required", "stay": "Depends on visa issued", "conditions": "Prepare purpose, funds, ties, and document evidence."},
        ],
        "validity_notes": "Many destinations require at least 6 months passport validity and blank pages.",
        "renewal_notes": "Renew before starting any route where passport validity may expire during processing.",
        "official_source_priority": ["Destination government immigration site", "Embassy or consulate page", "Airline document checker", "Official eVisa or ETA portal"],
        "last_reviewed": "2026-07-20",
        "confidence": "starter_pending_official_review",
    },
    {
        "country_key": "india",
        "country": "India",
        "region": "South Asia",
        "passport_strength_band": "starter_plus",
        "passport_opportunity_score": 57,
        "visa_free_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_on_arrival_count_estimate": "Use official passport-index source before showing exact public count",
        "evisa_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_required_count_estimate": "Visa planning remains important for many OECD relocation destinations",
        "summary": "An Indian passport has a wider mix of visa-free, visa-on-arrival, and eVisa possibilities than many starter passports, but relocation routes still require official checklist planning.",
        "visa_free_examples": [
            {"destination": "Selected Asian, Caribbean, and island destinations", "access_type": "Visa-free examples", "stay": "Varies", "conditions": "Confirm current rule, passport validity, return ticket, and funds."},
        ],
        "visa_on_arrival_examples": [
            {"destination": "Selected Asian, African, and island destinations", "access_type": "Visa on arrival examples", "stay": "Varies", "conditions": "Check fees, documents, hotel address, and airline boarding rules."},
        ],
        "evisa_examples": [
            {"destination": "Countries with official online visa systems", "access_type": "eVisa / ETA", "stay": "Varies", "conditions": "Use official portals and check processing time before booking."},
        ],
        "visa_required_examples": [
            {"destination": "Canada, United States, United Kingdom, Schengen Area, Australia", "access_type": "Visa usually required", "stay": "Depends on visa issued", "conditions": "Prepare route-specific evidence and appointment timelines."},
        ],
        "validity_notes": "Many destinations require 6 months validity and blank pages.",
        "renewal_notes": "Renew before long-stay or residence applications if validity is weak.",
        "official_source_priority": ["Destination government immigration site", "Embassy or consulate page", "Airline document checker", "Official eVisa or ETA portal"],
        "last_reviewed": "2026-07-20",
        "confidence": "starter_pending_official_review",
    },
    {
        "country_key": "pakistan",
        "country": "Pakistan",
        "region": "South Asia",
        "passport_strength_band": "starter",
        "passport_opportunity_score": 38,
        "visa_free_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_on_arrival_count_estimate": "Use official passport-index source before showing exact public count",
        "evisa_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_required_count_estimate": "High for many destinations, including most major relocation routes",
        "summary": "A Pakistani passport often needs more advance visa planning. Visa Power can be especially useful when the user already holds a strong valid visa from Canada, the U.S., UK, Schengen, Australia, or Japan.",
        "visa_free_examples": [
            {"destination": "Selected destinations", "access_type": "Visa-free examples", "stay": "Varies", "conditions": "Confirm official source before booking because eligibility can be narrow."},
        ],
        "visa_on_arrival_examples": [
            {"destination": "Selected destinations", "access_type": "Visa on arrival examples", "stay": "Varies", "conditions": "Confirm whether pre-approval, hotel booking, funds, or return ticket is required."},
        ],
        "evisa_examples": [
            {"destination": "Countries with official online visa systems", "access_type": "eVisa / ETA", "stay": "Varies", "conditions": "Use official portals and save proof of approval before travel."},
        ],
        "visa_required_examples": [
            {"destination": "Canada, United States, United Kingdom, Schengen Area, Australia", "access_type": "Visa usually required", "stay": "Depends on visa issued", "conditions": "Prepare strong purpose, funds, travel history, ties, and document evidence."},
        ],
        "validity_notes": "Passport validity and blank pages are critical; check every destination before applying or travelling.",
        "renewal_notes": "Renew early because weak passport validity can block applications and travel boarding.",
        "official_source_priority": ["Destination government immigration site", "Embassy or consulate page", "Airline document checker", "Official eVisa or ETA portal"],
        "last_reviewed": "2026-07-20",
        "confidence": "starter_pending_official_review",
    },
    {
        "country_key": "philippines",
        "country": "Philippines",
        "region": "Southeast Asia",
        "passport_strength_band": "starter_plus",
        "passport_opportunity_score": 58,
        "visa_free_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_on_arrival_count_estimate": "Use official passport-index source before showing exact public count",
        "evisa_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_required_count_estimate": "Major long-stay and relocation routes usually require visa planning",
        "summary": "A Philippine passport has useful regional travel options and selected wider access. Long-stay relocation still needs route-specific official checks.",
        "visa_free_examples": [
            {"destination": "ASEAN and selected destinations", "access_type": "Visa-free examples", "stay": "Varies", "conditions": "Confirm current stay limits, passport validity, and onward-ticket rules."},
        ],
        "visa_on_arrival_examples": [
            {"destination": "Selected Asian, African, and island destinations", "access_type": "Visa on arrival examples", "stay": "Varies", "conditions": "Check fees, hotel/funds evidence, and airline document rules."},
        ],
        "evisa_examples": [
            {"destination": "Countries with official online visa systems", "access_type": "eVisa / ETA", "stay": "Varies", "conditions": "Apply through official portals and confirm processing times."},
        ],
        "visa_required_examples": [
            {"destination": "Canada, United States, United Kingdom, Schengen Area, Australia", "access_type": "Visa usually required", "stay": "Depends on visa issued", "conditions": "Prepare route evidence, funds, purpose, and travel history."},
        ],
        "validity_notes": "Many destinations require 6 months validity and proof of onward travel.",
        "renewal_notes": "Renew before using the passport for long-stay applications or multiple trips.",
        "official_source_priority": ["Destination government immigration site", "Embassy or consulate page", "Airline document checker", "Official eVisa or ETA portal"],
        "last_reviewed": "2026-07-20",
        "confidence": "starter_pending_official_review",
    },
    {
        "country_key": "kuwait",
        "country": "Kuwait",
        "region": "Gulf",
        "passport_strength_band": "stronger_passport",
        "passport_opportunity_score": 72,
        "visa_free_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_on_arrival_count_estimate": "Use official passport-index source before showing exact public count",
        "evisa_count_estimate": "Use official passport-index source before showing exact public count",
        "visa_required_count_estimate": "Visa planning still applies for many study, work, and residence routes",
        "summary": "A Kuwaiti passport generally has stronger visitor mobility than starter passports, but long-stay relocation, study, work, and PR plans still require official route checks.",
        "visa_free_examples": [
            {"destination": "GCC and selected international destinations", "access_type": "Visa-free or simplified examples", "stay": "Varies", "conditions": "Confirm destination rules, passport validity, and travel purpose."},
        ],
        "visa_on_arrival_examples": [
            {"destination": "Selected destinations", "access_type": "Visa on arrival examples", "stay": "Varies", "conditions": "Confirm fees, duration, and border requirements."},
        ],
        "evisa_examples": [
            {"destination": "Countries with ETA or eVisa systems", "access_type": "eVisa / ETA", "stay": "Varies", "conditions": "Use official portals and verify approval before boarding."},
        ],
        "visa_required_examples": [
            {"destination": "Long-stay study, work, investment, or residence destinations", "access_type": "Visa or permit usually required", "stay": "Depends on route", "conditions": "Check official route requirements, eligibility, and documents."},
        ],
        "validity_notes": "Many destinations require 6 months validity and blank pages.",
        "renewal_notes": "Renew early before long-stay or residence procedures.",
        "official_source_priority": ["Destination government immigration site", "Embassy or consulate page", "Airline document checker", "Official eVisa or ETA portal"],
        "last_reviewed": "2026-07-20",
        "confidence": "starter_pending_official_review",
    },
]

VISA_POWER_RULES: List[Dict[str, Any]] = [
    {
        "id": "mexico-strong-visa-exemption",
        "destination": "Mexico",
        "destination_region": "North America",
        "eligible_visa_codes": ["canada_visitor", "us_visitor", "uk_visitor", "schengen_visitor", "japan_visitor"],
        "separate_visa_needed": "Usually no Mexican visa for eligible visitor purposes",
        "maximum_stay": "Stay is decided under Mexico visitor rules at entry; confirm the current visitor limit before travel.",
        "conditions": "The visa or residence document must be valid and current. Travel purpose should remain non-remunerated unless the official rule says otherwise. Passport, entry record, funds, ticket, and border questions still apply.",
        "official_source_name": "Mexico National Immigration Institute (INM)",
        "official_source_url": "https://www.gob.mx/inm/documentos/paises-y-regiones-que-requieren-visa-para-viajar-a-mexico",
        "last_verified": "2026-07-20",
        "confidence": "official_reviewed",
        "requires_multiple_entry": False,
        "requires_previous_use": False,
        "premium_note": "Good planning option for users who already hold a valid Canada, U.S., UK, Schengen, or Japan visa.",
    },
    {
        "id": "dominican-republic-multiple-entry-visa",
        "destination": "Dominican Republic",
        "destination_region": "Caribbean",
        "eligible_visa_codes": ["canada_visitor", "us_visitor", "uk_visitor", "schengen_visitor"],
        "separate_visa_needed": "Usually no Dominican tourist visa when the qualifying visa/residence rule applies",
        "maximum_stay": "Tourist stay and tourist-card conditions must be confirmed before travel.",
        "conditions": "Rule is tied to permanent residence or a valid multiple-entry visa from Canada, the United States, the United Kingdom, or Schengen/EU for tourist purposes. Passport validity and tourist entry conditions still apply.",
        "official_source_name": "Dominican Republic Ministry of Foreign Affairs (MIREX)",
        "official_source_url": "https://consultas.mirex.gob.do/servicios/visas/consulta-de-requisitos-para-extranjeros-ingresar-a-la-republica-dominicana",
        "last_verified": "2026-07-20",
        "confidence": "official_reviewed",
        "requires_multiple_entry": True,
        "requires_previous_use": False,
        "premium_note": "Strong example of why one valid visa can increase travel options beyond the issuing country.",
    },
    {
        "id": "panama-decree-521-strong-visa",
        "destination": "Panama",
        "destination_region": "Central America",
        "eligible_visa_codes": ["canada_visitor", "us_visitor", "uk_visitor", "schengen_visitor", "australia_visitor", "japan_visitor"],
        "separate_visa_needed": "Sometimes no stamped tourist visa when the qualifying visa rule applies",
        "maximum_stay": "Tourist stay is decided under Panama tourist entry rules and must be checked before travel.",
        "conditions": "The qualifying visa is commonly expected to be multiple-entry, already used in the issuing country or region, and valid for the required remaining period. Tourist entry rules still require passport, funds, return/onward ticket, and border checks.",
        "official_source_name": "Panama National Migration Service (SNM)",
        "official_source_url": "https://www.migracion.gob.pa/decretos-y-resoluciones-2018/",
        "last_verified": "2026-07-20",
        "confidence": "official_reviewed",
        "requires_multiple_entry": True,
        "requires_previous_use": True,
        "premium_note": "Needs a careful rule screen because Panama conditions can depend on visa use history and remaining validity.",
    },
    {
        "id": "costa-rica-us-canada-exemption",
        "destination": "Costa Rica",
        "destination_region": "Central America",
        "eligible_visa_codes": ["canada_visitor", "us_visitor"],
        "separate_visa_needed": "May not need a Costa Rica consular visa for eligible visa-required nationalities",
        "maximum_stay": "Often 30 days for some visa-required groups, extendable up to 90 days; the officer decides the actual stay.",
        "conditions": "U.S. or Canada visa/residence must normally be valid for at least three months at entry. U.S. transit C1, C2, and C3 visas are not accepted for this exemption. Passport and border-control checks still apply.",
        "official_source_name": "Costa Rica Directorate of Migration and Foreigners",
        "official_source_url": "https://www.migracion.go.cr/Paginas/Visas.aspx",
        "last_verified": "2026-07-20",
        "confidence": "official_reviewed",
        "requires_multiple_entry": False,
        "requires_previous_use": False,
        "premium_note": "Useful for users who hold U.S. or Canadian documents, but it must be checked against nationality and visa category.",
    },
]


def _clean_text(value: Any, limit: int = 120) -> str:
    return str(value or "").strip()[:limit]


def _country_key(value: Any) -> str:
    return _clean_text(value, 120).lower().replace("-", " ").replace("_", " ").strip()


def _clean_visa_codes(value: Any) -> List[str]:
    allowed = {item["code"] for item in HELD_VISA_OPTIONS}
    if not isinstance(value, list):
        return []
    cleaned: List[str] = []
    for item in value:
        code = _clean_text(item, 80)
        if code in allowed and code not in cleaned:
            cleaned.append(code)
    return cleaned


def _destination_count(rows: List[Dict[str, Any]]) -> int:
    destinations: Set[str] = {str(row.get("destination") or "") for row in rows if row.get("destination")}
    return len(destinations)


def _passport_record(passport_country: str) -> Dict[str, Any]:
    key = _country_key(passport_country)
    for record in PASSPORT_INDEX_RECORDS:
        if key == record["country_key"] or key == str(record["country"]).lower():
            return dict(record)
    fallback_country = _clean_text(passport_country, 120) or "Not selected"
    return {
        "country_key": key or "unknown",
        "country": fallback_country,
        "region": "Unknown",
        "passport_strength_band": "needs_review",
        "passport_opportunity_score": 35,
        "visa_free_count_estimate": "Not available in starter index yet",
        "visa_on_arrival_count_estimate": "Not available in starter index yet",
        "evisa_count_estimate": "Not available in starter index yet",
        "visa_required_count_estimate": "Check destination official sources",
        "summary": "This passport is not in the starter index yet. MoveReady can still check visa benefits from strong visas you already hold, but passport-only access must be verified from official destination sources.",
        "visa_free_examples": [],
        "visa_on_arrival_examples": [],
        "evisa_examples": [],
        "visa_required_examples": [],
        "validity_notes": "Check passport validity and blank-page requirements for every destination.",
        "renewal_notes": "Renew early if validity is weak or if a route may take months.",
        "official_source_priority": ["Destination government immigration site", "Embassy or consulate page", "Airline document checker", "Official eVisa or ETA portal"],
        "last_reviewed": "2026-07-20",
        "confidence": "starter_pending_official_review",
    }


def _visa_benefit_score(matched_rules: List[Dict[str, Any]], held_visas: List[str]) -> int:
    reviewed_count = sum(1 for row in matched_rules if row.get("confidence") == "official_reviewed")
    return min(100, round(20 + _destination_count(matched_rules) * 13 + len(held_visas) * 7 + reviewed_count * 3))


def _combined_score(passport_record: Dict[str, Any], matched_rules: List[Dict[str, Any]], held_visas: List[str]) -> int:
    passport_score = int(passport_record.get("passport_opportunity_score") or 0)
    benefit_score = _visa_benefit_score(matched_rules, held_visas) if held_visas else 0
    if not held_visas:
        return min(100, passport_score)
    return min(100, max(passport_score, round(passport_score + benefit_score * 0.45)))


def _condition_warnings(rule: Dict[str, Any], multiple_entry_confirmed: bool, visa_used_before_confirmed: bool) -> List[str]:
    warnings: List[str] = []
    if rule.get("requires_multiple_entry") and not multiple_entry_confirmed:
        warnings.append("Confirm that the qualifying visa is multiple-entry before relying on this rule.")
    if rule.get("requires_previous_use") and not visa_used_before_confirmed:
        warnings.append("Confirm whether the visa must have been used before in the issuing country or region.")
    return warnings


def _matched_rules(held_visas: List[str], multiple_entry_confirmed: bool, visa_used_before_confirmed: bool) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for rule in VISA_POWER_RULES:
        if not any(code in held_visas for code in rule.get("eligible_visa_codes", [])):
            continue
        row = dict(rule)
        warnings = _condition_warnings(row, multiple_entry_confirmed, visa_used_before_confirmed)
        row["condition_warnings"] = warnings
        row["condition_status"] = "conditions_to_confirm" if warnings else "basic_conditions_entered"
        rows.append(row)
    return rows


def _passport_options() -> List[Dict[str, str]]:
    return [
        {"country": row["country"], "country_key": row["country_key"], "region": row["region"], "confidence": row["confidence"]}
        for row in PASSPORT_INDEX_RECORDS
    ]


@bp.get("/options")
def visa_power_options():
    return jsonify(
        {
            "ok": True,
            "feature": "visa_power_passport_index_and_travel_benefits",
            "held_visa_options": HELD_VISA_OPTIONS,
            "passport_country_options": _passport_options(),
            "rule_count": len(VISA_POWER_RULES),
            "passport_index_country_count": len(PASSPORT_INDEX_RECORDS),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "safety_note": "Planning guidance only. Confirm official destination rules, airline checks, and border entry conditions before travel.",
        }
    )


@bp.get("/passport-index/options")
def passport_index_options():
    return jsonify(
        {
            "ok": True,
            "feature": "passport_index_starter",
            "passport_country_options": _passport_options(),
            "source_status": "starter_records_pending_official_source_refresh",
            "safety_note": "Do not treat passport index records as permission to travel. Confirm the current official destination rule before booking or travelling.",
        }
    )


@bp.post("/passport-index/check")
def passport_index_check():
    payload = request.get_json(silent=True) or {}
    passport_country = _clean_text(payload.get("passport_country"), 120)
    record = _passport_record(passport_country)
    return jsonify(
        {
            "ok": True,
            "passport_country": record.get("country"),
            "passport_index": record,
            "passport_opportunity_score": record.get("passport_opportunity_score"),
            "source_status": record.get("confidence"),
            "safety_note": "Passport access can change quickly. Confirm official destination rules, airline checks, passport validity, funds, return ticket, and personal history before travel.",
        }
    )


@bp.post("/check")
def visa_power_check():
    payload = request.get_json(silent=True) or {}
    passport_country = _clean_text(payload.get("passport_country"), 120)
    held_visas = _clean_visa_codes(payload.get("held_visas"))
    multiple_entry_confirmed = bool(payload.get("multiple_entry_confirmed"))
    visa_used_before_confirmed = bool(payload.get("visa_used_before_confirmed"))

    passport_record = _passport_record(passport_country)
    matched_rules = _matched_rules(held_visas, multiple_entry_confirmed, visa_used_before_confirmed)
    visa_score = _visa_benefit_score(matched_rules, held_visas)
    passport_score = int(passport_record.get("passport_opportunity_score") or 0)
    combined_score = _combined_score(passport_record, matched_rules, held_visas)

    return jsonify(
        {
            "ok": True,
            "feature": "visa_power_and_travel_benefits",
            "passport_country": passport_record.get("country"),
            "held_visas": held_visas,
            "multiple_entry_confirmed": multiple_entry_confirmed,
            "visa_used_before_confirmed": visa_used_before_confirmed,
            "passport_only_score": passport_score,
            "visa_opportunity_score": visa_score,
            "combined_opportunity_score": combined_score,
            "matched_destination_count": _destination_count(matched_rules),
            "passport_index": passport_record,
            "matches": matched_rules,
            "next_actions": [
                "Open the official destination source before booking or paying anyone.",
                "Check passport validity, blank pages, funds, return ticket, and accommodation evidence.",
                "Confirm visa conditions such as multiple-entry, previous use, remaining validity, and travel purpose.",
                "Save this route or create an alert if you want MoveReady to remind you to re-check later.",
            ],
            "safety_note": "This result is not permission to travel. Entry depends on current official rules, airline checks, border officers, document validity, travel purpose, funds, ticket, and personal history.",
        }
    )
