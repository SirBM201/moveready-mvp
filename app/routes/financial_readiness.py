from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.routes import relocation_public
from app.services.financial_readiness import (
    CONTRACT_VERSION,
    FinancialReadinessInputError,
    assess_financial_readiness,
)

bp = Blueprint("financial_readiness", __name__)


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
        return number if number >= 0 else None
    except (TypeError, ValueError):
        return None


def _route(country_code: str, route_code: str) -> Optional[Dict[str, Any]]:
    try:
        rows = relocation_public._route_summary_rows(country_code=country_code) or []
        match = next((row for row in rows if str(row.get("route_code") or "") == route_code), None)
        if match and match.get("id"):
            detail = relocation_public._route_detail(match)
            if detail:
                return detail
    except Exception:
        pass
    return relocation_public._fallback_route_detail(country_code, route_code)


def _budget(route: Dict[str, Any]) -> Tuple[float, float, str, List[Dict[str, Any]]]:
    items = route.get("budget_items") if isinstance(route.get("budget_items"), list) else []
    minimum = 0.0
    maximum = 0.0
    currency = "EUR"
    normalized: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        low = _number(item.get("amount_min")) or 0.0
        high = _number(item.get("amount_max"))
        high = high if high is not None else low
        currency = str(item.get("currency_code") or currency).upper()
        minimum += low
        maximum += high
        normalized.append({
            "name": item.get("item_name"),
            "category": item.get("item_category"),
            "minimum": low,
            "maximum": high,
            "currency": currency,
            "required": bool(item.get("is_required", True)),
            "notes": item.get("notes"),
        })
    return round(minimum, 2), round(maximum, 2), currency, normalized


def _planning_category(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"fees", "tuition", "relocation", "flight", "accommodation", "settlement_reserve"}:
        return token
    if token in {"visa_fee", "application_fee", "document", "courier", "translation", "notarization"}:
        return "fees"
    if token == "tuition":
        return "tuition"
    if token == "flight":
        return "flight"
    if token == "accommodation":
        return "accommodation"
    if token == "settlement":
        return "settlement_reserve"
    return "relocation"


def _route_cost_items(route: Dict[str, Any]) -> List[Dict[str, Any]]:
    route_name = str(route.get("route_name") or "Route cost estimate").strip()
    freshness = str(route.get("freshness_status") or "not_recorded").strip()
    result: List[Dict[str, Any]] = []
    for item in route.get("budget_items") if isinstance(route.get("budget_items"), list) else []:
        if not isinstance(item, dict):
            continue
        low = _number(item.get("amount_min")) or 0.0
        high = _number(item.get("amount_max"))
        planning_amount = high if high is not None else low
        result.append({
            "category": _planning_category(item.get("item_category")),
            "label": item.get("item_name") or "Route cost estimate",
            "amount": planning_amount,
            "currency": item.get("currency_code") or "EUR",
            "source_type": "route_estimate",
            "source_title": route_name,
            "source_checked_at": route.get("verified_at"),
            "amount_basis": "route_estimated_maximum",
            "notes": f"{item.get('notes') or 'Planning estimate.'} Route freshness: {freshness}.",
        })
    return result


def _user_cost_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    costs = payload.get("costs")
    if not isinstance(costs, dict):
        return []
    result = []
    for category, value in costs.items():
        item = value if isinstance(value, dict) else {"amount": value}
        result.append({**item, "category": category, "source_type": "user_entered"})
    return result


@bp.post("/check")
def check():
    payload = request.get_json(silent=True) or {}
    country_code = str(payload.get("country_code") or "").strip().upper()
    route_code = str(payload.get("route_code") or "").strip()
    available = _number(payload.get("available_funds", payload.get("savings")))
    declared_currency = str(payload.get("currency") or "").strip().upper()
    family_members = int(_number(payload.get("family_members")) or 0)

    if not country_code or not route_code:
        return jsonify({"ok": False, "error": "country_code_and_route_code_required"}), 400
    route = _route(country_code, route_code)
    if not route:
        return jsonify({"ok": False, "error": "route_not_found"}), 404

    minimum, maximum, route_currency, items = _budget(route)
    currency_mismatch = bool(declared_currency and declared_currency != route_currency)
    status = "unknown"
    gap_to_minimum = None
    reserve_after_maximum = None
    if available is not None and not currency_mismatch:
        gap_to_minimum = round(max(0.0, minimum - available), 2)
        reserve_after_maximum = round(available - maximum, 2)
        if available < minimum:
            status = "below_estimated_cost_range"
        elif available < maximum:
            status = "within_estimated_cost_range"
        else:
            status = "above_estimated_cost_range"

    user_costs = _user_cost_items(payload)
    overridden_categories = {
        _planning_category(item.get("category"))
        for item in user_costs
    }
    route_costs = [
        item for item in _route_cost_items(route)
        if item["category"] not in overridden_categories
    ]
    proof = payload.get("proof_of_funds") if isinstance(payload.get("proof_of_funds"), dict) else {}
    family_size = payload.get("family_size")
    if family_size in (None, ""):
        family_size = family_members + 1

    try:
        plan = assess_financial_readiness({
            "currency": declared_currency or route_currency,
            "savings": payload.get("savings", available),
            "expected_funding": payload.get("expected_funding", 0),
            "family_size": family_size,
            "proof_of_funds": {
                "amount": proof.get(
                    "amount",
                    payload.get("proof_of_funds_required", payload.get("required_funds_amount")),
                ),
                "currency": proof.get("currency") or declared_currency or route_currency,
                "source_url": proof.get("source_url") or payload.get("proof_of_funds_source_url"),
                "source_title": proof.get("source_title") or payload.get("proof_of_funds_source_title"),
                "source_checked_at": proof.get("source_checked_at") or payload.get("proof_of_funds_source_checked_at"),
            },
            "cost_items": route_costs,
            "costs": payload.get("costs") if isinstance(payload.get("costs"), dict) else {},
            "target_date": payload.get("target_date"),
            "target_timeline_months": payload.get("target_timeline_months"),
        })
    except FinancialReadinessInputError as exc:
        return jsonify({"ok": False, "error": exc.code, "field": exc.field, "contract_version": CONTRACT_VERSION}), 400

    return jsonify({
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "route": {
            "country_code": country_code,
            "country_name": route.get("country_name"),
            "route_code": route_code,
            "route_name": route.get("route_name"),
            "freshness_status": route.get("freshness_status"),
            "source_confidence": route.get("source_confidence"),
            "verified_at": route.get("verified_at"),
        },
        "estimated_costs": {"minimum": minimum, "maximum": maximum, "currency": route_currency, "items": items},
        "user_inputs": {
            "available_funds": available,
            "currency": declared_currency or route_currency,
            "family_members": family_members,
            "family_size": family_size,
            "expected_funding": plan["resources"]["expected_funding"],
            "target_date": plan["target"]["date"],
        },
        "assessment": {
            "status": status,
            "gap_to_estimated_minimum": gap_to_minimum,
            "reserve_after_estimated_maximum": reserve_after_maximum,
            "currency_mismatch": currency_mismatch,
            "financial_readiness_status": plan["assessment"]["status"],
            "combined_target": plan["assessment"]["combined_target"],
            "funding_gap": plan["assessment"]["funding_gap"],
            "monthly_savings_target": plan["assessment"]["monthly_savings_target"],
        },
        "proof_of_funds": {
            **plan["proof_of_funds"],
            "official_minimum": None,
            "checks": [
                "Confirm the official minimum amount for this exact route and family size.",
                "Confirm required holding period and acceptable statement history.",
                "Confirm sponsor, scholarship, business-fund, and joint-account rules where applicable.",
                "Keep proof-of-funds separate from estimated relocation spending unless the authority explicitly combines them.",
            ],
        },
        "financial_plan": plan,
        "safety_note": plan["safety_note"],
    })
