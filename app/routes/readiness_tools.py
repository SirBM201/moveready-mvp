from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from app.services.financial_readiness import (
    CONTRACT_VERSION,
    FinancialReadinessInputError,
    assess_financial_readiness,
)
from app.services.supabase_client import get_supabase

bp = Blueprint("readiness_tools", __name__)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _readiness_status(risk_level: str) -> str:
    if risk_level == "high":
        return "needs_attention"
    if risk_level == "medium":
        return "review_recommended"
    return "ready_to_continue"


def _with_storage(tool_slug: str, payload: Dict[str, Any], result: Dict[str, Any]):
    result["stored"] = False
    try:
        row = {
            "tool_slug": tool_slug,
            "status": "completed",
            "risk_level": result.get("risk_level"),
            "readiness_status": result.get("readiness_status"),
            "input_payload": payload,
            "result_payload": result,
            "source_page": _text(payload.get("source_page"))[:240] or None,
        }
        response = get_supabase().table("relocation_readiness_check_runs").insert(row).execute()
        stored = (response.data or [None])[0]
        if stored:
            result["stored"] = True
            result["id"] = stored.get("id")
    except Exception:
        result["storage_note"] = "Check completed but not saved. Run the readiness storage SQL if persistence is required."
    return jsonify(result)


@bp.post("/name-consistency")
def name_consistency():
    payload = request.get_json(silent=True) or {}
    records = payload.get("records") or []
    issues: List[Dict[str, Any]] = []

    normalized = []
    for item in records:
        label = _text(item.get("label") if isinstance(item, dict) else "Document")
        name = _text(item.get("name") if isinstance(item, dict) else item)
        tokens = [part for part in name.lower().replace(".", " ").replace(",", " ").split() if part]
        normalized.append({"label": label, "name": name, "tokens": tokens})

    base = normalized[0] if normalized else None
    for item in normalized[1:]:
        if not item["name"]:
            issues.append({"severity": "high", "label": item["label"], "issue": "Missing name", "suggestion": "Add the exact name shown on this document."})
            continue
        if base and item["tokens"] != base["tokens"]:
            missing = sorted(set(base["tokens"]) - set(item["tokens"]))
            extra = sorted(set(item["tokens"]) - set(base["tokens"]))
            severity = "medium" if set(item["tokens"]) == set(base["tokens"]) else "high"
            issues.append({
                "severity": severity,
                "label": item["label"],
                "issue": "Name does not exactly match the base record.",
                "missing_tokens": missing,
                "extra_tokens": extra,
                "suggestion": "Prepare evidence for spelling, middle-name, order, abbreviation, maiden/married-name, or correction differences before submission.",
            })

    score = sum(30 if issue["severity"] == "high" else 15 for issue in issues)
    risk_level = _risk_level(score)
    result = {
        "ok": True,
        "risk_level": risk_level,
        "readiness_status": _readiness_status(risk_level),
        "issues": issues,
        "summary": "No visible name mismatch detected." if not issues else "Potential name mismatch detected across documents.",
        "note": "This is a readiness check, not legal advice. Official document correction or affidavit requirements depend on the route and receiving authority.",
    }
    return _with_storage("name_consistency", payload, result)


@bp.post("/document-readiness")
def document_readiness():
    payload = request.get_json(silent=True) or {}
    route_category = _text(payload.get("route_category") or payload.get("goal") or "relocation").lower()
    documents = {str(item).strip().lower() for item in payload.get("documents") or [] if str(item).strip()}

    required = ["passport", "proof of funds", "purpose evidence"]
    conditional = ["insurance", "translation", "notarization", "apostille or legalization"]
    if route_category in {"study", "scholarship"}:
        required.extend(["admission letter", "academic records"])
    if route_category in {"startup", "business"}:
        required.extend(["business plan", "founder evidence", "traction or mvp evidence"])
    if route_category in {"family"}:
        required.extend(["relationship evidence", "civil documents"])

    missing = [item for item in required if item not in documents]
    recommended = [item for item in conditional if item not in documents]
    score = len(missing) * 25 + len(recommended) * 7
    risk_level = _risk_level(score)

    result = {
        "ok": True,
        "risk_level": risk_level,
        "readiness_status": _readiness_status(risk_level),
        "missing_required": missing,
        "recommended_checks": recommended,
        "summary": "Core required documents appear present." if not missing else "Some core required documents are missing from the checklist.",
        "note": "Document names are normalized starter categories. Route-specific official document names should be verified before applying.",
    }
    return _with_storage("document_readiness", payload, result)


@bp.post("/funds-plan")
def funds_plan():
    payload = request.get_json(silent=True) or {}
    family_members = payload.get("family_members_count")
    try:
        additional_family_members = int(family_members or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_non_negative_integer", "field": "family_members_count", "contract_version": CONTRACT_VERSION}), 400
    if additional_family_members < 0:
        return jsonify({"ok": False, "error": "invalid_non_negative_integer", "field": "family_members_count", "contract_version": CONTRACT_VERSION}), 400

    family_size = payload.get("family_size")
    if family_size in (None, ""):
        family_size = additional_family_members + 1

    proof = payload.get("proof_of_funds") if isinstance(payload.get("proof_of_funds"), dict) else {}
    costs = payload.get("costs") if isinstance(payload.get("costs"), dict) else {}
    for category, aliases in {
        "fees": ("fees", "estimated_fees"),
        "tuition": ("tuition", "estimated_tuition"),
        "relocation": ("relocation", "estimated_relocation_cost"),
        "flight": ("flight", "estimated_flight"),
        "accommodation": ("accommodation", "estimated_accommodation"),
        "settlement_reserve": ("settlement_reserve",),
    }.items():
        if category in costs:
            continue
        for alias in aliases:
            if alias in payload:
                costs[category] = payload.get(alias)
                break

    try:
        plan = assess_financial_readiness({
            "currency": payload.get("currency") or payload.get("available_funds_currency") or "USD",
            "savings": payload.get("savings", payload.get("available_funds_amount", payload.get("available_funds"))),
            "expected_funding": payload.get("expected_funding", 0),
            "family_size": family_size,
            "proof_of_funds": {
                "amount": proof.get(
                    "amount",
                    payload.get("required_funds_amount", payload.get("proof_of_funds_required")),
                ),
                "currency": proof.get("currency") or payload.get("currency") or payload.get("available_funds_currency") or "USD",
                "source_url": proof.get("source_url") or payload.get("proof_of_funds_source_url"),
                "source_title": proof.get("source_title") or payload.get("proof_of_funds_source_title"),
                "source_checked_at": proof.get("source_checked_at") or payload.get("proof_of_funds_source_checked_at"),
            },
            "costs": costs,
            "target_date": payload.get("target_date"),
            "target_timeline_months": payload.get("target_timeline_months"),
        })
    except FinancialReadinessInputError as exc:
        return jsonify({"ok": False, "error": exc.code, "field": exc.field, "contract_version": CONTRACT_VERSION}), 400

    shortfall = plan["assessment"]["funding_gap"]
    monthly_target = plan["assessment"]["monthly_savings_target"]
    large_deposit_risk = bool(payload.get("recent_large_deposits"))

    score = 0
    if shortfall is not None and shortfall > 0:
        score += 45
    if plan["assessment"]["status"] in {"requirements_needed", "source_review_required"}:
        score += 35
    if large_deposit_risk:
        score += 25
    months = plan["target"]["months_remaining"]
    if months is not None and months <= 2 and shortfall is not None and shortfall > 0:
        score += 20
    risk_level = _risk_level(score)

    result = {
        **plan,
        "available_funds": plan["resources"]["savings"],
        "required_funds_adjusted": plan["proof_of_funds"]["amount"],
        "shortfall": shortfall,
        "monthly_savings_target": monthly_target,
        "risk_level": risk_level,
        "readiness_status": plan["assessment"]["status"] if plan["assessment"]["status"] in {"requirements_needed", "source_review_required", "currency_mismatch"} else _readiness_status(risk_level),
        "warnings": [
            *plan["warnings"],
            *(["Recent large deposits may need clear source-of-funds explanation."] if large_deposit_risk else []),
        ],
        "note": "Use current official proof-of-funds rules for the selected pathway and family size. MoveReady does not invent thresholds, family multipliers, or exchange rates.",
    }
    return _with_storage("funds_plan", payload, result)


@bp.post("/refusal-risk")
def refusal_risk():
    payload = request.get_json(silent=True) or {}
    indicators = payload.get("indicators") or {}
    checks = [
        ("previous_refusal", "Previous refusal may require a clear repair explanation.", 20),
        ("low_funds", "Funds may be weak for this route.", 25),
        ("unclear_purpose", "Purpose of travel or relocation is unclear.", 20),
        ("weak_home_ties", "Home-tie evidence may be weak.", 15),
        ("incomplete_documents", "Incomplete documents increase refusal risk.", 25),
        ("unexplained_deposits", "Unexplained deposits can create source-of-funds concerns.", 15),
        ("weak_business_plan", "Business/startup evidence may be weak.", 20),
    ]
    findings = [
        {"indicator": key, "severity": "high" if points >= 20 else "medium", "issue": text}
        for key, text, points in checks
        if bool(indicators.get(key))
    ]
    score = sum(points for key, _text_value, points in checks if bool(indicators.get(key)))
    risk_level = _risk_level(score)

    result = {
        "ok": True,
        "risk_level": risk_level,
        "readiness_status": _readiness_status(risk_level),
        "findings": findings,
        "repair_plan": [
            "Confirm the correct route and official eligibility rules.",
            "Prepare a complete document checklist before paying for submission.",
            "Explain funds, purpose, and ties with clear evidence.",
            "For previous refusal, compare the old refusal reasons against the new evidence pack.",
        ],
        "note": "This is a risk-screening tool, not a guarantee of approval or refusal.",
    }
    return _with_storage("refusal_risk", payload, result)
