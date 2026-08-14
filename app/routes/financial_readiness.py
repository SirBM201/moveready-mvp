from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.routes import relocation_public

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


@bp.post("/check")
def check():
    payload = request.get_json(silent=True) or {}
    country_code = str(payload.get("country_code") or "").strip().upper()
    route_code = str(payload.get("route_code") or "").strip()
    available = _number(payload.get("available_funds"))
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

    return jsonify({
        "ok": True,
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
        "user_inputs": {"available_funds": available, "currency": declared_currency or route_currency, "family_members": family_members},
        "assessment": {"status": status, "gap_to_estimated_minimum": gap_to_minimum, "reserve_after_estimated_maximum": reserve_after_maximum, "currency_mismatch": currency_mismatch},
        "proof_of_funds": {
            "official_minimum": None,
            "status": "official_requirement_not_inferred",
            "checks": [
                "Confirm the official minimum amount for this exact route and family size.",
                "Confirm required holding period and acceptable statement history.",
                "Confirm sponsor, scholarship, business-fund, and joint-account rules where applicable.",
                "Keep proof-of-funds separate from estimated relocation spending unless the authority explicitly combines them.",
            ],
        },
        "safety_note": "This is a budgeting readiness calculation, not a visa eligibility or approval prediction. Route cost estimates and proof-of-funds rules can change. Currency conversion is deliberately not guessed; use matching currencies and verify official requirements before applying or moving money.",
    })
