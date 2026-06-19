from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.services.report_generator import build_readiness_report
from app.services.supabase_client import get_supabase

bp = Blueprint("relocation_public", __name__)

RISK_WEIGHT = {"low": 1, "medium": 2, "high": 3}
CONFIDENCE_WEIGHT = {"low": 1, "medium": 2, "high": 3}


def _fallback_countries() -> List[Dict[str, Any]]:
    return [
        {"country_code": "PT", "country_name": "Portugal", "region": "Europe", "summary": "Routes for visitors, students, entrepreneurs, workers, and families should be verified from official sources before use."},
        {"country_code": "EE", "country_name": "Estonia", "region": "Europe", "summary": "Useful for startup, e-residency, digital business, study, and work pathway research."},
        {"country_code": "FI", "country_name": "Finland", "region": "Europe", "summary": "Popular for study, work, startup, family, and long-term settlement planning."},
    ]


def _fallback_routes() -> List[Dict[str, Any]]:
    return [
        {"route_code": "study", "route_name": "Study pathway", "route_category": "study", "country_code": "generic", "risk_level": "medium", "last_verified_at": None, "freshness_status": "starter_fallback", "summary": "Compare admission, proof of funds, insurance, accommodation, and family rules before applying."},
        {"route_code": "startup", "route_name": "Startup or business pathway", "route_category": "startup", "country_code": "generic", "risk_level": "medium", "last_verified_at": None, "freshness_status": "starter_fallback", "summary": "Check business eligibility, founder commitment, funds, and local registration expectations."},
        {"route_code": "work", "route_name": "Work pathway", "route_category": "work", "country_code": "generic", "risk_level": "high", "last_verified_at": None, "freshness_status": "starter_fallback", "summary": "Usually depends on job offer, employer eligibility, qualification evidence, and residence rules."},
    ]


def _fallback_route_detail(country_code: str, route_code: str) -> Optional[Dict[str, Any]]:
    country_code = country_code.upper()
    key = (country_code, route_code)

    route_map: Dict[tuple[str, str], Dict[str, Any]] = {
        ("EE", "startup-founder"): {
            "route_name": "Estonia startup founder pathway",
            "route_category": "startup",
            "country_name": "Estonia",
            "summary": "For non-EU founders building a technology-based, innovative, scalable startup with MVP or traction. Startup Committee approval and a unique application code are central before visa or residence permit next steps.",
            "budget_range": "EUR 1,430 - 5,900",
            "facts": [
                ("startup_definition", "Startup definition", "Technology-based, innovative, scalable business with MVP/traction and global growth potential."),
                ("startup_committee", "Startup Committee approval", "Founder should obtain Startup Committee verification/application code before visa or residence next steps."),
                ("committee_timeline", "Committee timeline", "Startup Committee review is commonly described as a working-day review process; users should verify current timing before relying on it."),
                ("d_visa_duration", "D visa duration", "Long-stay D visa may support temporary stay while residence-permit steps are being handled."),
                ("financial_means", "Financial means", "Prepare evidence of funds, income, company backing, sponsor support, or other official financial means required by the route."),
            ],
            "documents": [
                ("Passport", "required", "Valid passport with enough validity and blank pages for application and travel."),
                ("Startup Committee evidence", "required", "Startup Committee confirmation, application code, or equivalent route evidence."),
                ("Business evidence", "required", "Pitch deck, MVP/traction evidence, founder role, company documents, and market plan."),
                ("Proof of financial means", "required", "Bank statements, income evidence, sponsor support, or company funding evidence."),
                ("Insurance evidence", "conditional", "Travel or health insurance may be required depending on application stage."),
            ],
            "budget_items": [
                ("Startup preparation", "document", 250, 1500, "EUR", "Pitch deck, business evidence, translation, and document preparation."),
                ("Visa and residence fees", "visa_fee", 100, 600, "EUR", "Official fees vary by application stage and applicant profile."),
                ("Insurance", "insurance", 80, 500, "EUR", "Insurance cost depends on period and coverage."),
                ("Arrival reserve", "accommodation", 1000, 3300, "EUR", "Initial accommodation and first-arrival buffer."),
            ],
        },
        ("FI", "d-visa"): {
            "route_name": "Finland D visa / fast-track pathway",
            "route_category": "work",
            "country_name": "Finland",
            "summary": "For eligible applicants using Finland residence-permit routes where a D visa can support faster travel after a positive residence-permit decision or in connection with eligible fast-track routes.",
            "budget_range": "EUR 1,250 - 5,700",
            "facts": [
                ("d_visa_scope", "D visa scope", "D visa is connected to eligible Finnish residence-permit processes and should be checked against the applicant's actual permit category."),
                ("fast_track", "Fast-track route", "Some specialist, startup, manager, and family-related categories may use faster residence processing where eligibility is met."),
                ("residence_permit_first", "Residence permit context", "The D visa should not be treated as a standalone relocation route separate from the residence-permit basis."),
                ("family_context", "Family context", "Family members may require separate evidence and route-specific checks."),
                ("document_handling", "Document handling", "Foreign documents may require legalization, apostille, and translation depending on issuing and receiving authorities."),
            ],
            "documents": [
                ("Passport", "required", "Valid passport and identity evidence for each applicant."),
                ("Residence permit evidence", "required", "Residence-permit application, positive decision, or official route evidence depending on stage."),
                ("Purpose evidence", "required", "Employment, startup, study, family, or other qualifying residence-permit basis."),
                ("Family evidence", "conditional", "Marriage, birth, custody, or dependency evidence where family members are included."),
                ("Insurance or health coverage evidence", "conditional", "Coverage requirements depend on applicant category and stage."),
            ],
            "budget_items": [
                ("Residence and visa fees", "visa_fee", 120, 800, "EUR", "Official application fees vary by permit type and processing channel."),
                ("Document preparation", "document", 100, 700, "EUR", "Translation, legalization, apostille, and certified copy costs."),
                ("Insurance", "insurance", 100, 700, "EUR", "Insurance or health coverage preparation."),
                ("Initial arrival costs", "accommodation", 900, 3500, "EUR", "Travel, first accommodation, registration, and local setup buffer."),
            ],
        },
        ("PT", "entrepreneur-independent-work"): {
            "route_name": "Portugal entrepreneur and independent work pathway",
            "route_category": "business",
            "country_name": "Portugal",
            "summary": "For applicants preparing Portugal residency visa evidence for independent professional activity, entrepreneurial activity, or related business-purpose routes. Users should distinguish this from Startup Visa where relevant.",
            "budget_range": "EUR 1,600 - 6,100",
            "facts": [
                ("residency_visa", "Residency visa context", "Portugal national visa guidance includes residency visa documentation for applicants seeking longer residence routes."),
                ("independent_activity", "Independent professional activity", "Applicants may need evidence of contracts, service activity, qualifications, registration, or professional income depending on route."),
                ("entrepreneur_evidence", "Entrepreneur evidence", "Business plan, company documents, investment/funds, purpose, and economic activity evidence should be prepared."),
                ("startup_distinction", "Startup Visa distinction", "Startup Visa is a distinct entrepreneurship route and should not be mixed with general independent-work evidence without review."),
                ("residence_step", "Residence permit step", "A visa may be followed by residence-permit steps after arrival, depending on the approved pathway."),
                ("document_legalization", "Document legalization", "Foreign documents may need legalization/apostille and translation before being accepted."),
            ],
            "documents": [
                ("Passport", "required", "Valid passport and identity evidence."),
                ("Purpose evidence", "required", "Independent activity contracts, business plan, company documents, client evidence, or professional qualification evidence."),
                ("Proof of financial means", "required", "Bank statements, business income, sponsor support, savings, or other official funds evidence."),
                ("Accommodation evidence", "conditional", "Accommodation evidence may be requested depending on application stage and consular process."),
                ("Criminal record / civil documents", "conditional", "Civil or background documents may need legalization/apostille and translation."),
                ("Insurance evidence", "conditional", "Travel or health insurance may be required depending on the application stage."),
            ],
            "budget_items": [
                ("Visa and application fees", "visa_fee", 90, 450, "EUR", "Official fees vary by consulate, route, and service channel."),
                ("Document preparation", "document", 150, 900, "EUR", "Translation, apostille/legalization, notary, and certified copies."),
                ("Business evidence preparation", "business", 250, 1200, "EUR", "Business plan, contracts, company records, and professional evidence."),
                ("Insurance", "insurance", 80, 550, "EUR", "Travel or health insurance preparation."),
                ("Initial arrival costs", "accommodation", 1000, 3000, "EUR", "Travel, first accommodation, and arrival setup buffer."),
            ],
        },
    }

    route = route_map.get(key)
    if not route:
        return None

    return {
        "id": None,
        "route_code": route_code,
        "route_name": route["route_name"],
        "route_category": route["route_category"],
        "is_public": True,
        "country_id": None,
        "country_code": country_code,
        "country_name": route["country_name"],
        "active_version_id": None,
        "risk_level": "medium",
        "source_confidence": "high",
        "verified_at": None,
        "review_due_at": None,
        "freshness_status": "available_starter",
        "summary": route["summary"],
        "raw": {"source": "backend_fallback", "budget_range": route["budget_range"]},
        "facts": [
            {"fact_key": key, "fact_label": label, "fact_value": value, "fact_payload": {}, "display_order": index * 10}
            for index, (key, label, value) in enumerate(route["facts"], start=1)
        ],
        "documents": [
            {"document_name": name, "requirement_level": level, "applies_to": "applicant", "details": details, "display_order": index * 10}
            for index, (name, level, details) in enumerate(route["documents"], start=1)
        ],
        "budget_items": [
            {"item_name": name, "item_category": category, "amount_min": amount_min, "amount_max": amount_max, "currency_code": currency, "is_required": True, "notes": notes}
            for name, category, amount_min, amount_max, currency, notes in route["budget_items"]
        ],
        "insurance_requirements": [
            {"insurance_type": "Travel or health insurance", "is_required": True, "minimum_coverage_amount": None, "currency_code": "EUR", "details": "Confirm coverage, dates, destination, and minimum amount from the official route or consular instructions before purchase."}
        ],
    }


def _select(table: str, columns: str = "*", *, limit: Optional[int] = None):
    try:
        query = get_supabase().table(table).select(columns)
        if limit:
            query = query.limit(limit)
        response = query.execute()
        return response.data or []
    except Exception:
        return None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _freshness_status(version: Optional[Dict[str, Any]]) -> str:
    if not version:
        return "pending_review"
    status = version.get("status") or "draft"
    if status != "active":
        return status
    review_due = _parse_dt(version.get("review_due_at"))
    if review_due and review_due < datetime.now(timezone.utc):
        return "review_due"
    if not version.get("verified_at"):
        return "active_unverified"
    return "active"


def _first_row(response: Any) -> Optional[Dict[str, Any]]:
    rows = getattr(response, "data", None) or []
    return rows[0] if rows else None


def _route_versions(route_id: str, columns: str = "*") -> List[Dict[str, Any]]:
    try:
        response = (
            get_supabase()
            .table("relocation_route_versions")
            .select(columns)
            .eq("route_id", route_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def _route_summary_row(route: Dict[str, Any]) -> Dict[str, Any]:
    country = route.get("relocation_countries") or {}
    versions = route.get("relocation_route_versions") or []
    active_version = None
    active_version_id = route.get("active_version_id")

    for version in versions:
        if active_version_id and version.get("id") == active_version_id:
            active_version = version
            break
    if not active_version and versions:
        active_version = versions[0]

    return {
        "id": route.get("id"),
        "route_code": route.get("route_code"),
        "route_name": route.get("route_name"),
        "route_category": route.get("route_category"),
        "is_public": route.get("is_public"),
        "country_id": route.get("country_id"),
        "country_code": country.get("country_code"),
        "country_name": country.get("country_name"),
        "active_version_id": active_version_id,
        "risk_level": (active_version or {}).get("risk_level"),
        "source_confidence": (active_version or {}).get("source_confidence"),
        "verified_at": (active_version or {}).get("verified_at"),
        "review_due_at": (active_version or {}).get("review_due_at"),
        "freshness_status": _freshness_status(active_version),
        "summary": (active_version or {}).get("route_summary"),
    }


def _route_summary_rows(country_code: str = "", category: str = "") -> Optional[List[Dict[str, Any]]]:
    try:
        query = (
            get_supabase()
            .table("relocation_visa_routes")
            .select(
                "id,route_code,route_name,route_category,is_public,country_id,active_version_id,"
                "relocation_countries(country_code,country_name)"
            )
            .eq("is_public", True)
        )
        if category:
            query = query.eq("route_category", category)
        response = query.execute()
        rows = []
        for row in response.data or []:
            row["relocation_route_versions"] = _route_versions(
                row.get("id"),
                "id,status,risk_level,route_summary,source_confidence,verified_at,review_due_at,created_at",
            )
            rows.append(_route_summary_row(row))
        if country_code:
            rows = [row for row in rows if row.get("country_code") == country_code]
        return rows
    except Exception:
        return None


def _highest_risk(routes: List[Dict[str, Any]]) -> str:
    risks = [str(route.get("risk_level") or "").lower() for route in routes if route.get("risk_level")]
    if not risks:
        return "review required"
    return sorted(risks, key=lambda risk: RISK_WEIGHT.get(risk, 0), reverse=True)[0]


def _highest_confidence(routes: List[Dict[str, Any]]) -> str:
    labels = [str(route.get("source_confidence") or "").lower() for route in routes if route.get("source_confidence")]
    if not labels:
        return "source review required"
    return sorted(labels, key=lambda label: CONFIDENCE_WEIGHT.get(label, 0), reverse=True)[0]


def _freshness_label(routes: List[Dict[str, Any]]) -> str:
    statuses = {route.get("freshness_status") for route in routes}
    if "active" in statuses:
        return "active route available"
    if "review_due" in statuses:
        return "source review due"
    if "active_unverified" in statuses:
        return "active source review needed"
    if routes:
        return "review route before use"
    return "no route record yet"


def _country_comparison_rows(countries: List[Dict[str, Any]], routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for country in countries:
        country_code = country.get("country_code")
        country_routes = [route for route in routes if route.get("country_code") == country_code]
        categories = sorted({route.get("route_category") for route in country_routes if route.get("route_category")})
        verified_dates = sorted(
            [route.get("verified_at") for route in country_routes if route.get("verified_at")],
            reverse=True,
        )
        rows.append({
            **country,
            "routes": country_routes,
            "route_count": len(country_routes),
            "route_categories": categories,
            "risk_label": _highest_risk(country_routes),
            "source_confidence_label": _highest_confidence(country_routes),
            "freshness_label": _freshness_label(country_routes),
            "active_route_count": sum(1 for route in country_routes if route.get("freshness_status") == "active"),
            "review_due_route_count": sum(1 for route in country_routes if route.get("freshness_status") == "review_due"),
            "last_verified_at": verified_dates[0] if verified_dates else None,
        })
    return rows


@bp.get("/countries")
def countries():
    rows = _select("relocation_countries", "id,country_code,country_name,region,currency_code,official_language_codes,summary,is_active")
    if rows is None:
        rows = _fallback_countries()
    else:
        rows = [row for row in rows if row.get("is_active", True)]
    return jsonify({"ok": True, "countries": rows})


@bp.get("/routes")
def routes():
    country_code = (request.args.get("country_code") or "").strip().upper()
    category = (request.args.get("category") or "").strip()

    rows = _route_summary_rows(country_code, category)
    if rows is None:
        rows = _fallback_routes()
    return jsonify({"ok": True, "routes": rows})


@bp.get("/country-comparison")
def country_comparison():
    country_code = (request.args.get("country_code") or "").strip().upper()
    category = (request.args.get("category") or "").strip()

    countries = _select("relocation_countries", "id,country_code,country_name,region,currency_code,official_language_codes,summary,is_active")
    routes = _route_summary_rows(category=category)
    source_status = "database_backed"

    if countries is None or routes is None:
        countries = _fallback_countries()
        routes = _fallback_routes()
        source_status = "starter_fallback"
    else:
        countries = [country for country in countries if country.get("is_active", True)]

    if country_code:
        countries = [country for country in countries if country.get("country_code") == country_code]
        routes = [route for route in routes if route.get("country_code") == country_code]

    return jsonify({
        "ok": True,
        "source_status": source_status,
        "countries": _country_comparison_rows(countries, routes),
    })


@bp.get("/routes/by-code/<country_code>/<route_code>")
def route_detail_by_code(country_code: str, route_code: str):
    fallback = _fallback_route_detail(country_code, route_code)

    try:
        country_response = (
            get_supabase()
            .table("relocation_countries")
            .select("id")
            .eq("country_code", country_code.upper())
            .limit(1)
            .execute()
        )
        country = _first_row(country_response)
        if not country:
            if fallback:
                return jsonify({"ok": True, "route": fallback})
            return jsonify({"ok": False, "error": "country_not_found"}), 404

        route_response = (
            get_supabase()
            .table("relocation_visa_routes")
            .select("id")
            .eq("country_id", country.get("id"))
            .eq("route_code", route_code)
            .eq("is_public", True)
            .limit(1)
            .execute()
        )
        route = _first_row(route_response)
        if not route:
            if fallback:
                return jsonify({"ok": True, "route": fallback})
            return jsonify({"ok": False, "error": "route_not_found"}), 404

        return route_detail(route.get("id"))
    except Exception as exc:
        if fallback:
            return jsonify({"ok": True, "route": fallback, "fallback_reason": str(exc)})
        return jsonify({"ok": False, "error": "route_lookup_unavailable", "details": str(exc)}), 503


@bp.get("/routes/<route_id>")
def route_detail(route_id: str):
    try:
        route_response = (
            get_supabase()
            .table("relocation_visa_routes")
            .select(
                "id,route_code,route_name,route_category,is_public,country_id,active_version_id,created_at,updated_at,"
                "relocation_countries(id,country_code,country_name,region,currency_code)"
            )
            .eq("id", route_id)
            .limit(1)
            .execute()
        )
        route = _first_row(route_response)
        if not route:
            return jsonify({"ok": False, "error": "route_not_found"}), 404

        route["relocation_route_versions"] = _route_versions(route.get("id"))
        summary = _route_summary_row(route)
        active_version_id = summary.get("active_version_id")

        facts: List[Dict[str, Any]] = []
        documents: List[Dict[str, Any]] = []
        budget_items: List[Dict[str, Any]] = []
        insurance: List[Dict[str, Any]] = []

        if active_version_id:
            facts_response = (
                get_supabase()
                .table("relocation_route_facts")
                .select("fact_key,fact_label,fact_value,fact_payload,display_order")
                .eq("route_version_id", active_version_id)
                .order("display_order")
                .execute()
            )
            facts = facts_response.data or []

            documents_response = (
                get_supabase()
                .table("relocation_document_requirements")
                .select("document_name,requirement_level,applies_to,details,display_order")
                .eq("route_version_id", active_version_id)
                .order("display_order")
                .execute()
            )
            documents = documents_response.data or []

            budget_response = (
                get_supabase()
                .table("relocation_budget_items")
                .select("item_name,item_category,amount_min,amount_max,currency_code,is_required,notes")
                .or_(f"route_version_id.eq.{active_version_id},country_id.eq.{route.get('country_id')}")
                .execute()
            )
            budget_items = budget_response.data or []

            insurance_response = (
                get_supabase()
                .table("relocation_insurance_requirements")
                .select("insurance_type,is_required,minimum_coverage_amount,currency_code,details")
                .or_(f"route_version_id.eq.{active_version_id},country_id.eq.{route.get('country_id')}")
                .execute()
            )
            insurance = insurance_response.data or []

        return jsonify({
            "ok": True,
            "route": {
                **summary,
                "raw": route,
                "facts": facts,
                "documents": documents,
                "budget_items": budget_items,
                "insurance_requirements": insurance,
            },
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": "route_detail_unavailable", "details": str(exc)}), 503


@bp.post("/checklist")
def checklist():
    payload = request.get_json(silent=True) or {}
    route_version_id = payload.get("route_version_id")
    route_category = payload.get("route_category") or payload.get("goal") or "relocation"

    if route_version_id:
        try:
            response = (
                get_supabase()
                .table("relocation_document_requirements")
                .select("document_name,requirement_level,applies_to,details,display_order")
                .eq("route_version_id", route_version_id)
                .order("display_order")
                .execute()
            )
            if response.data:
                return jsonify({"ok": True, "checklist": response.data, "source_status": "route_version_backed"})
        except Exception:
            pass

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
    country_id = payload.get("country_id")
    route_version_id = payload.get("route_version_id")

    db_items = []
    try:
        query = get_supabase().table("relocation_budget_items").select("item_name,item_category,amount_min,amount_max,currency_code,is_required,notes")
        if route_version_id:
            query = query.eq("route_version_id", route_version_id)
        elif country_id:
            query = query.eq("country_id", country_id)
        db_items = query.execute().data or []
    except Exception:
        db_items = []

    base_items = db_items or [
        {"item_name": "Application and visa fees", "item_category": "visa_fee", "amount_min": 100, "amount_max": 600, "currency_code": currency},
        {"item_name": "Document preparation", "item_category": "document", "amount_min": 50, "amount_max": 400, "currency_code": currency},
        {"item_name": "Insurance", "item_category": "insurance", "amount_min": 80, "amount_max": 600, "currency_code": currency},
        {"item_name": "Flight and first arrival costs", "item_category": "flight", "amount_min": 500, "amount_max": 1500, "currency_code": currency},
        {"item_name": "Initial accommodation", "item_category": "accommodation", "amount_min": 800, "amount_max": 2500, "currency_code": currency},
    ]

    multiplier = max(1, 1 + (family_members * 0.55))
    total_min = sum(float(item.get("amount_min") or 0) for item in base_items) * multiplier
    total_max = sum(float(item.get("amount_max") or 0) for item in base_items) * multiplier

    return jsonify({
        "ok": True,
        "currency": currency,
        "items": base_items,
        "estimated_total_min": round(total_min, 2),
        "estimated_total_max": round(total_max, 2),
        "source_status": "database_backed" if db_items else "starter_estimate",
        "note": "Starter estimate only. Official proof-of-funds and fee rules must be verified per country and route.",
    })


@bp.get("/scholarships")
def scholarships():
    rows = _select("relocation_scholarships", "scholarship_name,provider_name,scholarship_url,deadline_date,funding_type,status,summary,last_verified_at")
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
            "route_version_id": payload.get("route_version_id"),
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
        report["storage_note"] = "Report generated but not saved. Check Supabase env configuration and table permissions."

    return jsonify({"ok": True, "report": report})
