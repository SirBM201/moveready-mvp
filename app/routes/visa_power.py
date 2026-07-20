from __future__ import annotations

from typing import Any, Dict, List, Set

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
    },
]


def _clean_text(value: Any, limit: int = 120) -> str:
    return str(value or "").strip()[:limit]


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


def _score(matched_rules: List[Dict[str, Any]], held_visas: List[str]) -> int:
    reviewed_count = sum(1 for row in matched_rules if row.get("confidence") == "official_reviewed")
    return min(100, round(20 + _destination_count(matched_rules) * 13 + len(held_visas) * 7 + reviewed_count * 3))


@bp.get("/options")
def visa_power_options():
    return jsonify(
        {
            "ok": True,
            "feature": "visa_power_and_travel_benefits",
            "held_visa_options": HELD_VISA_OPTIONS,
            "rule_count": len(VISA_POWER_RULES),
            "safety_note": "Planning guidance only. Confirm official destination rules, airline checks, and border entry conditions before travel.",
        }
    )


@bp.post("/check")
def visa_power_check():
    payload = request.get_json(silent=True) or {}
    passport_country = _clean_text(payload.get("passport_country"), 120)
    held_visas = _clean_visa_codes(payload.get("held_visas"))
    multiple_entry_confirmed = bool(payload.get("multiple_entry_confirmed"))
    visa_used_before_confirmed = bool(payload.get("visa_used_before_confirmed"))

    matched_rules = [
        rule
        for rule in VISA_POWER_RULES
        if any(code in held_visas for code in rule.get("eligible_visa_codes", []))
    ]

    return jsonify(
        {
            "ok": True,
            "passport_country": passport_country,
            "held_visas": held_visas,
            "multiple_entry_confirmed": multiple_entry_confirmed,
            "visa_used_before_confirmed": visa_used_before_confirmed,
            "visa_opportunity_score": _score(matched_rules, held_visas),
            "matched_destination_count": _destination_count(matched_rules),
            "matches": matched_rules,
            "safety_note": "This result is not permission to travel. Entry depends on current official rules, airline checks, border officers, document validity, travel purpose, funds, ticket, and personal history.",
        }
    )
