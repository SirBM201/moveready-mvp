from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.report_generator import build_readiness_report
from app.services.supabase_client import get_supabase

bp = Blueprint("relocation_public", __name__)


def _fallback_countries():
    return [
        {
            "country_code": "PT",
            "country_name": "Portugal",
            "region": "Europe",
            "summary": "Routes for visitors, students, entrepreneurs, workers, and families should be verified from official sources before use.",
        },
        {
            "country_code": "EE",
            "country_name": "Estonia",
            "region": "Europe",
            "summary": "Useful for startup, e-residency, digital business, study, and work pathway research.",
        },
        {
            "country_code": "FI",
            "country_name": "Finland",
            "region": "Europe",
            "summary": "Popular for study, work, startup, family, and long-term settlement planning.",
        },
    ]


def _fallback_routes():
    return [
        {
            "route_code": "study",
            "route_name": "Study pathway",
            "route_category": "study",
            "country_code": "generic",
            "risk_level": "medium",
            "last_verified_at": None,
            "summary": "Compare admission, proof of funds, insurance, accommodation, and family rules before applying.",
        },
        {
            "route_code": "startup",
            "route_name": "Startup or business pathway",
            "route_category": "startup",
            "country_code": "generic",
            "risk_level": "medium",
            "last_verified_at": None,
            "summary": "Check business eligibility, founder commitment, funds, and local registration expectations.",
        },
        {
            "route_code": "work",
            "route_name": "Work pathway",
            "route_category": "work",
            "country_code": "generic",
            "risk_level": "high",
            "last_verified_at": None,
            "summary": "Usually depends on job offer, employer eligibility, qualification evidence, and residence rules.",
        },
    ]


def _select(table: str, columns: str = "*"):
    try:
        response = get_supabase().table(table).select(columns).execute()
        return response.data or []
    except Exception:
        return None


@bp.get("/countries")
def countries():
    rows = _select("relocation_countries", "country_code,country_name,region,currency_code,summary,is_active")
    if rows is None:
        rows = _fallback_countries()
    return jsonify({"ok": True, "countries": rows})


@bp.get("/routes")
def routes():
    rows = _select(
        "relocation_visa_routes",
        "id,route_code,route_name,route_category,is_public,country_id,active_version_id",
    )
    if rows is None:
        rows = _fallback_routes()
    return jsonify({"ok": True, "routes": rows})


@bp.get("/routes/<route_id>")
def route_detail(route_id: str):
    try:
        route = (
            get_supabase()
            .table("relocation_visa_routes")
            .select("*, relocation_route_versions(*)")
            .eq("id", route_id)
            .maybe_single()
            .execute()
        )
        if route.data:
            return jsonify({"ok": True, "route": route.data})
    except Exception:
        pass

    return jsonify({"ok": False, "error": "route_not_found"}), 404


@bp.post("/checklist")
def checklist():
    payload = request.get_json(silent=True) or {}
    goal = payload.get("goal") or "relocation"
    route_category = payload.get("route_category") or goal

    items = [
        {"document_name": "Valid passport", "requirement_level": "required", "details": "Confirm passport validity and blank-page rules for the target route."},
        {"document_name": "Proof of funds", "requirement_level": "required", "details": "Prepare bank statements, sponsor evidence, or funding proof as required."},
        {"document_name": "Purpose evidence", "requirement_level": "required", "details": "Use admission, job offer, business plan, invitation, or family documents depending on the route."},
        {"document_name": "Insurance evidence", "requirement_level": "conditional", "details": "Travel or health insurance may be required before application or entry."},
    ]

    if route_category in {"study", "scholarship"}:
        items.append({"document_name": "Admission or scholarship documents", "requirement_level": "required", "details": "Include offer letter, scholarship award, tuition evidence, or school correspondence."})
    if route_category in {"business", "startup"}:
        items.append({"document_name": "Business plan and founder evidence", "requirement_level": "required", "details": "Prepare business model, traction, founder role, and funding plan."})

    return jsonify({"ok": True, "checklist": items, "source_status": "starter_rules_pending_official_review"})


@bp.post("/budget-estimate")
def budget_estimate():
    payload = request.get_json(silent=True) or {}
    currency = payload.get("currency") or payload.get("available_funds_currency") or "USD"
    family_members = int(payload.get("family_members_count") or 0)

    base_items = [
        {"item_name": "Application and visa fees", "item_category": "visa_fee", "amount_min": 100, "amount_max": 600, "currency_code": currency},
        {"item_name": "Document preparation", "item_category": "document", "amount_min": 50, "amount_max": 400, "currency_code": currency},
        {"item_name": "Insurance", "item_category": "insurance", "amount_min": 80, "amount_max": 600, "currency_code": currency},
        {"item_name": "Flight and first arrival costs", "item_category": "flight", "amount_min": 500, "amount_max": 1500, "currency_code": currency},
        {"item_name": "Initial accommodation", "item_category": "accommodation", "amount_min": 800, "amount_max": 2500, "currency_code": currency},
    ]

    multiplier = max(1, 1 + (family_members * 0.55))
    total_min = sum(float(item["amount_min"]) for item in base_items) * multiplier
    total_max = sum(float(item["amount_max"]) for item in base_items) * multiplier

    return jsonify({
        "ok": True,
        "currency": currency,
        "items": base_items,
        "estimated_total_min": round(total_min, 2),
        "estimated_total_max": round(total_max, 2),
        "note": "Starter estimate only. Official proof-of-funds and fee rules must be verified per country and route.",
    })


@bp.get("/scholarships")
def scholarships():
    rows = _select("relocation_scholarships", "scholarship_name,provider_name,scholarship_url,deadline_date,funding_type,status,summary")
    if rows is None:
        rows = []
    return jsonify({"ok": True, "scholarships": rows})


@bp.get("/insurance-requirements")
def insurance_requirements():
    rows = _select("relocation_insurance_requirements", "insurance_type,is_required,minimum_coverage_amount,currency_code,details")
    if rows is None:
        rows = []
    return jsonify({"ok": True, "insurance_requirements": rows})


@bp.post("/reports")
def create_report():
    payload = request.get_json(silent=True) or {}
    report = build_readiness_report(payload)

    try:
        row = {
            "report_ref": report["report_ref"],
            "status": "generated",
            "report_title": report["report_title"],
            "risk_level": report["risk_level"],
            "input_payload": payload,
            "report_payload": report,
        }
        response = get_supabase().table("relocation_generated_reports").insert(row).execute()
        stored = (response.data or [None])[0]
        if stored:
            report["stored"] = True
            report["id"] = stored.get("id")
    except Exception:
        report["stored"] = False
        report["storage_note"] = "Report generated but not saved. Run Supabase SQL and configure backend env to enable storage."

    return jsonify({"ok": True, "report": report})
