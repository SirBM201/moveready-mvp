from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

bp = Blueprint("readiness_tools", __name__)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


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
    return jsonify({
        "ok": True,
        "risk_level": _risk_level(score),
        "issues": issues,
        "summary": "No visible name mismatch detected." if not issues else "Potential name mismatch detected across documents.",
        "note": "This is a readiness check, not legal advice. Official document correction or affidavit requirements depend on the route and receiving authority.",
    })


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

    return jsonify({
        "ok": True,
        "risk_level": _risk_level(score),
        "missing_required": missing,
        "recommended_checks": recommended,
        "summary": "Core required documents appear present." if not missing else "Some core required documents are missing from the checklist.",
        "note": "Document names are normalized starter categories. Route-specific official document names should be verified before applying.",
    })


@bp.post("/funds-plan")
def funds_plan():
    payload = request.get_json(silent=True) or {}
    available = float(payload.get("available_funds_amount") or 0)
    required = float(payload.get("required_funds_amount") or 0)
    months = max(int(payload.get("target_timeline_months") or 1), 1)
    family_members = int(payload.get("family_members_count") or 0)
    currency = _text(payload.get("currency") or payload.get("available_funds_currency") or "USD")

    adjusted_required = required * max(1, 1 + (family_members * 0.45))
    shortfall = max(adjusted_required - available, 0)
    monthly_target = shortfall / months if shortfall else 0
    large_deposit_risk = bool(payload.get("recent_large_deposits"))

    score = 0
    if shortfall > 0:
        score += 45
    if large_deposit_risk:
        score += 25
    if months <= 2 and shortfall > 0:
        score += 20

    return jsonify({
        "ok": True,
        "currency": currency,
        "available_funds": round(available, 2),
        "required_funds_adjusted": round(adjusted_required, 2),
        "shortfall": round(shortfall, 2),
        "monthly_savings_target": round(monthly_target, 2),
        "risk_level": _risk_level(score),
        "warnings": [item for item in [
            "Funds are below the entered requirement." if shortfall else None,
            "Recent large deposits may need clear source-of-funds explanation." if large_deposit_risk else None,
            "Timeline is short for closing a funds gap." if months <= 2 and shortfall else None,
        ] if item],
        "note": "Use official proof-of-funds rules for the target route. This planner only models readiness pressure.",
    })


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

    return jsonify({
        "ok": True,
        "risk_level": _risk_level(score),
        "findings": findings,
        "repair_plan": [
            "Confirm the correct route and official eligibility rules.",
            "Prepare a complete document checklist before paying for submission.",
            "Explain funds, purpose, and ties with clear evidence.",
            "For previous refusal, compare the old refusal reasons against the new evidence pack.",
        ],
        "note": "This is a risk-screening tool, not a guarantee of approval or refusal.",
    })
