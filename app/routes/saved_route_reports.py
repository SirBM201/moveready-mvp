from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from app.services.report_generator import build_readiness_report
from app.services.supabase_client import get_supabase

bp = Blueprint("saved_route_reports", __name__)


def _clean_text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _number(value: Any, fallback: float = 0) -> float:
    try:
        if value in (None, ""):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _integer(value: Any, fallback: int = 0) -> int:
    try:
        if value in (None, ""):
            return fallback
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _first_row(response: Any) -> Optional[Dict[str, Any]]:
    rows = getattr(response, "data", None) or []
    return rows[0] if rows else None


def _pick(*values: Any, fallback: Any = None) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return fallback


def _load_saved_route(saved_route_id: str, *, email: Optional[str], phone: Optional[str]) -> Optional[Dict[str, Any]]:
    query = (
        get_supabase()
        .table("relocation_saved_routes")
        .select("*")
        .eq("id", saved_route_id)
        .limit(1)
    )
    if email:
        query = query.eq("email", email)
    if phone:
        query = query.eq("phone", phone)
    return _first_row(query.execute())


def _latest_profile(email: Optional[str]) -> Dict[str, Any]:
    if not email:
        return {}
    try:
        response = (
            get_supabase()
            .table("relocation_user_profiles")
            .select("*")
            .eq("email", email)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return _first_row(response) or {}
    except Exception:
        return {}


def _report_input(saved_route: Dict[str, Any], profile: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    main_goal = _pick(
        payload.get("main_goal"),
        payload.get("goal"),
        saved_route.get("main_goal"),
        saved_route.get("route_category"),
        profile.get("main_goal"),
        profile.get("route_category"),
        fallback="relocation",
    )
    route_category = _pick(payload.get("route_category"), saved_route.get("route_category"), profile.get("route_category"), main_goal, fallback="relocation")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    metadata = {
        **metadata,
        "saved_route_id": saved_route.get("id"),
        "saved_route_title": saved_route.get("saved_title"),
        "saved_route_code": saved_route.get("route_code"),
        "generated_from": "saved_route_report_endpoint",
        "trust_notice": "advisory_only_no_approval_guarantee",
    }
    return {
        "full_name": _pick(payload.get("full_name"), saved_route.get("full_name"), profile.get("full_name"), fallback=""),
        "email": _pick(payload.get("email"), saved_route.get("email"), profile.get("email"), fallback=""),
        "phone": _pick(payload.get("phone"), saved_route.get("phone"), profile.get("phone"), fallback=""),
        "preferred_contact_channel": _pick(payload.get("preferred_contact_channel"), profile.get("preferred_contact_channel"), fallback="email"),
        "consent_to_contact": True,
        "goal": main_goal,
        "main_goal": main_goal,
        "route_category": route_category,
        "current_country": _pick(payload.get("current_country"), saved_route.get("current_country"), profile.get("current_country"), fallback=""),
        "target_country": _pick(payload.get("target_country"), saved_route.get("target_country"), profile.get("target_country"), fallback=""),
        "available_funds_amount": _number(_pick(payload.get("available_funds_amount"), profile.get("available_funds_amount"), fallback=0), 0),
        "available_funds_currency": _pick(payload.get("available_funds_currency"), profile.get("available_funds_currency"), payload.get("currency"), fallback="EUR"),
        "family_members_count": _integer(_pick(payload.get("family_members_count"), profile.get("family_members_count"), fallback=0), 0),
        "timeline_months": _integer(_pick(payload.get("timeline_months"), profile.get("timeline_months"), fallback=0), 0),
        "has_previous_refusal": _bool(_pick(payload.get("has_previous_refusal"), profile.get("has_previous_refusal"), fallback=False)),
        "route_id": saved_route.get("route_id"),
        "route_version_id": _pick(payload.get("route_version_id"), saved_route.get("route_version_id")),
        "country_id": saved_route.get("country_id"),
        "country_code": saved_route.get("country_code"),
        "source_page": _pick(payload.get("source_page"), saved_route.get("source_page"), fallback="/saved-routes"),
        "metadata": metadata,
    }


def _report_row(report: Dict[str, Any], report_input: Dict[str, Any], saved_route: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "report_ref": report["report_ref"],
        "status": "generated",
        "report_title": report["report_title"],
        "risk_level": report["risk_level"],
        "route_version_id": report_input.get("route_version_id"),
        "input_payload": report_input,
        "report_payload": report,
        "email": _clean_text(report_input.get("email"), 255),
        "phone": _clean_text(report_input.get("phone"), 80),
        "full_name": _clean_text(report_input.get("full_name"), 180),
        "readiness_score": report.get("readiness_score"),
        "readiness_level": report.get("readiness_level"),
        "source_status": report.get("source_status"),
        "source_confidence": report.get("source_confidence"),
        "report_sections": report.get("sections") or [],
        "metadata": {
            "saved_route_id": saved_route.get("id"),
            "saved_route_title": saved_route.get("saved_title"),
            "generated_from": "saved_route_endpoint",
        },
    }


def _minimal_report_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "report_ref": row["report_ref"],
        "status": row["status"],
        "report_title": row["report_title"],
        "risk_level": row["risk_level"],
        "route_version_id": row.get("route_version_id"),
        "input_payload": row["input_payload"],
        "report_payload": row["report_payload"],
    }


@bp.post("/<saved_route_id>")
def create_from_saved_route(saved_route_id: str):
    payload = request.get_json(silent=True) or {}
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)
    if not email and not phone:
        return jsonify({"ok": False, "error": "email_or_phone_required"}), 400

    try:
        saved_route = _load_saved_route(saved_route_id, email=email, phone=phone)
        if not saved_route:
            return jsonify({"ok": False, "error": "saved_route_not_found"}), 404

        profile = _latest_profile(email)
        report_input = _report_input(saved_route, profile, payload)
        report = build_readiness_report(report_input)
        row = _report_row(report, report_input, saved_route)

        try:
            response = get_supabase().table("relocation_generated_reports").insert(row).execute()
        except Exception:
            response = get_supabase().table("relocation_generated_reports").insert(_minimal_report_row(row)).execute()

        stored = (response.data or [None])[0]
        report["stored"] = bool(stored)
        if stored:
            report["id"] = stored.get("id")
        return jsonify({"ok": True, "report": report, "saved_route": saved_route})
    except Exception as exc:
        return jsonify({"ok": False, "error": "saved_route_report_failed", "details": str(exc)}), 500
