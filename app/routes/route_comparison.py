from __future__ import annotations

from typing import Any, Dict, List
from flask import Blueprint, jsonify, request

from app.routes import relocation_public

bp = Blueprint("route_comparison", __name__)


def _token(value: Any) -> str:
    return str(value or "").strip()


def _detail(country_code: str, route_code: str) -> Dict[str, Any] | None:
    try:
        rows = relocation_public._route_summary_rows(country_code=country_code) or []
        match = next((row for row in rows if _token(row.get("route_code")) == route_code), None)
        if match:
            detail = relocation_public._route_detail(match)
            if detail:
                return detail
    except Exception:
        pass
    return relocation_public._fallback_route_detail(country_code, route_code)


def _costs(route: Dict[str, Any]) -> Dict[str, Any]:
    items = route.get("budget_items") if isinstance(route.get("budget_items"), list) else []
    minimum = maximum = 0.0
    currencies = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            low = float(item.get("amount_min") or 0)
            high = float(item.get("amount_max") if item.get("amount_max") is not None else low)
        except (TypeError, ValueError):
            continue
        minimum += low; maximum += high
        if item.get("currency_code"): currencies.add(str(item.get("currency_code")).upper())
    return {"minimum": round(minimum,2), "maximum": round(maximum,2), "currency": next(iter(currencies)) if len(currencies)==1 else None, "mixed_currency": len(currencies)>1}


def _normalize(route: Dict[str, Any]) -> Dict[str, Any]:
    documents = route.get("documents") if isinstance(route.get("documents"), list) else []
    required = [d for d in documents if isinstance(d, dict) and str(d.get("requirement_level") or "").lower()=="required"]
    conditional = [d for d in documents if isinstance(d, dict) and str(d.get("requirement_level") or "").lower()=="conditional"]
    return {
        "country_code": route.get("country_code"), "country_name": route.get("country_name"),
        "route_code": route.get("route_code"), "route_name": route.get("route_name"), "route_category": route.get("route_category"),
        "summary": route.get("summary"), "risk_level": route.get("risk_level"), "source_confidence": route.get("source_confidence"),
        "freshness_status": route.get("freshness_status"), "verified_at": route.get("verified_at"), "review_due_at": route.get("review_due_at"),
        "costs": _costs(route), "required_document_count": len(required), "conditional_document_count": len(conditional),
        "required_documents": [d.get("document_name") for d in required[:8]],
        "provenance": {"source_kind": (route.get("raw") or {}).get("source") if isinstance(route.get("raw"), dict) else None, "active_version_id": route.get("active_version_id")},
    }


@bp.post("")
def compare_routes():
    payload = request.get_json(silent=True) or {}
    selections = payload.get("routes") if isinstance(payload.get("routes"), list) else []
    if len(selections) < 2 or len(selections) > 4:
        return jsonify({"ok":False,"error":"select_between_2_and_4_routes"}),400
    results: List[Dict[str, Any]]=[]
    missing=[]
    for selection in selections:
        if not isinstance(selection, dict): continue
        country=_token(selection.get("country_code")).upper(); code=_token(selection.get("route_code"))
        route=_detail(country,code) if country and code else None
        if route: results.append(_normalize(route))
        else: missing.append({"country_code":country,"route_code":code})
    if len(results)<2:
        return jsonify({"ok":False,"error":"not_enough_comparable_routes","missing":missing}),404
    return jsonify({"ok":True,"routes":results,"missing":missing,"comparison_rules":{"costs":"Compare amounts only when currencies match; no exchange rate is inferred.","risk":"Risk labels describe route complexity/data risk and are not approval probabilities.","sources":"Prefer active, recently verified, high-confidence records; starter/fallback records require official verification."},"safety_note":"Route comparison is decision support, not legal advice, eligibility confirmation, or an approval prediction. Verify current official rules before paying, applying, travelling, or moving funds."})
