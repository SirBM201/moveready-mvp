from __future__ import annotations

from typing import Any, Dict, List

from flask import jsonify, request

from app.routes.passport_provider import _build_public_passport_response
from app.routes.visa_power import (
    _clean_visa_codes,
    _combined_score,
    _destination_count,
    _matched_rules,
    _passport_record,
    _visa_benefit_score,
)
from app.services.passport_index_provider import clean_text


def _copy_matches(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows]


def visa_power_check_safe():
    payload = request.get_json(silent=True) or {}
    passport_country = clean_text(payload.get("passport_country"), 120)
    held_visas = _clean_visa_codes(payload.get("held_visas"))
    multiple_entry_confirmed = bool(payload.get("multiple_entry_confirmed"))
    visa_used_before_confirmed = bool(payload.get("visa_used_before_confirmed"))
    prior_entry_refusal_declared = bool(payload.get("prior_entry_refusal_declared"))
    visa_cancelled_or_revoked_declared = bool(payload.get("visa_cancelled_or_revoked_declared"))

    passport_response = _build_public_passport_response(passport_country)
    passport_record = passport_response.get("passport_index") or _passport_record(passport_country)
    passport_score = int(passport_record.get("passport_opportunity_score") or 0)

    blocked_visa_codes: List[str] = []
    usable_held_visas = list(held_visas)
    eligibility_gate_status = "open"
    eligibility_gate_message = "Selected visas may be checked against reviewed third-country benefit rules."

    if visa_cancelled_or_revoked_declared and held_visas:
        blocked_visa_codes = list(held_visas)
        usable_held_visas = []
        eligibility_gate_status = "blocked_pending_validity_confirmation"
        eligibility_gate_message = (
            "MoveReady has blocked Visa Power benefits because a selected visa may be cancelled or revoked. "
            "Confirm the visa remains valid with the issuing authority before relying on it."
        )

    matched_rules = _copy_matches(
        _matched_rules(
            usable_held_visas,
            multiple_entry_confirmed,
            visa_used_before_confirmed,
        )
    )

    travel_history_warnings: List[str] = []
    if prior_entry_refusal_declared:
        travel_history_warnings.extend(
            [
                "A previous refusal, denied admission, or withdrawal at a border may affect questioning, disclosure duties, future applications, and practical reliance on a third-country visa exemption.",
                "A border refusal is not the same as successful prior use of the visa. Do not mark previous successful use unless entry was actually granted.",
                "Confirm that the visa remains valid and disclose the incident truthfully whenever an immigration authority asks.",
            ]
        )
        for rule in matched_rules:
            warnings = list(rule.get("condition_warnings") or [])
            warnings.append(
                "Personal-history review required: confirm the prior border refusal does not prevent reliance on this destination rule."
            )
            rule["condition_warnings"] = warnings
            rule["condition_status"] = "personal_history_and_rule_conditions_to_confirm"

    visa_score = _visa_benefit_score(matched_rules, usable_held_visas) if usable_held_visas else 0
    combined_score = (
        _combined_score(passport_record, matched_rules, usable_held_visas)
        if usable_held_visas
        else passport_score
    )

    next_actions = [
        "Open the official destination source before booking or paying anyone.",
        "Check passport validity, blank pages, funds, return ticket, accommodation, and travel purpose.",
        "Confirm visa validity, multiple-entry status, previous successful use, and required remaining validity.",
        "Disclose refusals, denied admission, cancellation, revocation, or withdrawal history whenever an authority asks.",
        "Save the route or create an alert so the rule can be checked again before travel.",
    ]

    return jsonify(
        {
            "ok": True,
            "feature": "visa_power_and_travel_benefits_provider_ready_with_safety_gate",
            "passport_country": passport_record.get("country"),
            "held_visas": held_visas,
            "usable_held_visas": usable_held_visas,
            "blocked_visa_codes": blocked_visa_codes,
            "multiple_entry_confirmed": multiple_entry_confirmed,
            "visa_used_before_confirmed": visa_used_before_confirmed,
            "prior_entry_refusal_declared": prior_entry_refusal_declared,
            "visa_cancelled_or_revoked_declared": visa_cancelled_or_revoked_declared,
            "eligibility_gate": {
                "status": eligibility_gate_status,
                "message": eligibility_gate_message,
            },
            "travel_history_warnings": travel_history_warnings,
            "passport_only_score": passport_score,
            "visa_opportunity_score": visa_score,
            "combined_opportunity_score": combined_score,
            "matched_destination_count": _destination_count(matched_rules),
            "passport_index": passport_record,
            "cache_status": passport_response.get("cache_status"),
            "provider_status": passport_response.get("provider_status"),
            "provider_refresh": passport_response.get("provider_refresh"),
            "matches": matched_rules,
            "next_actions": next_actions,
            "safety_note": "This result is planning guidance, not permission to travel. Entry depends on current official rules, airline checks, border officers, document validity, visa validity, travel purpose, funds, ticket, accommodation, and personal immigration history.",
        }
    )
