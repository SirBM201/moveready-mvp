from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase

bp = Blueprint("reports", __name__)


def _clean_text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _public_report(row: Dict[str, Any]) -> Dict[str, Any]:
    payload = row.get("report_payload") or {}
    input_payload = row.get("input_payload") or {}
    return {
        "id": row.get("id"),
        "report_ref": row.get("report_ref"),
        "status": row.get("status"),
        "report_title": row.get("report_title"),
        "risk_level": row.get("risk_level"),
        "route_version_id": row.get("route_version_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "generated_at": row.get("generated_at"),
        "email": row.get("email") or input_payload.get("email"),
        "phone": row.get("phone") or input_payload.get("phone"),
        "goal": input_payload.get("goal") or input_payload.get("main_goal"),
        "route_category": input_payload.get("route_category"),
        "current_country": input_payload.get("current_country"),
        "target_country": input_payload.get("target_country"),
        "available_funds_amount": input_payload.get("available_funds_amount"),
        "available_funds_currency": input_payload.get("available_funds_currency") or input_payload.get("currency"),
        "family_members_count": input_payload.get("family_members_count"),
        "readiness_score": row.get("readiness_score") or payload.get("readiness_score"),
        "readiness_level": row.get("readiness_level") or payload.get("readiness_level"),
        "source_status": row.get("source_status") or payload.get("source_status"),
        "source_confidence": row.get("source_confidence") or payload.get("source_confidence"),
        "report_payload": payload,
    }


def _contact_matches(row: Dict[str, Any], *, email: Optional[str], phone: Optional[str]) -> bool:
    payload = row.get("input_payload") or {}
    if email:
        lookup_email = email.lower()
        if str(row.get("email") or "").strip().lower() == lookup_email:
            return True
        if str(payload.get("email") or "").strip().lower() == lookup_email:
            return True
    if phone:
        if str(row.get("phone") or "").strip() == phone:
            return True
        if str(payload.get("phone") or "").strip() == phone:
            return True
    return False


@bp.get("/", strict_slashes=False)
def list_reports():
    report_ref = _clean_text(request.args.get("report_ref"), 120)
    email = _clean_text(request.args.get("email"), 255)
    phone = _clean_text(request.args.get("phone"), 80)
    limit = min(max(int(request.args.get("limit") or 25), 1), 50)

    if not report_ref and not email and not phone:
        return jsonify({"ok": False, "error": "report_ref_email_or_phone_required"}), 400

    try:
        query = (
            get_supabase()
            .table("relocation_generated_reports")
            .select("*")
            .order("created_at", desc=True)
            .limit(100 if (email or phone) else limit)
        )
        if report_ref:
            query = query.eq("report_ref", report_ref)
        response = query.execute()
        rows: List[Dict[str, Any]] = response.data or []
        if email or phone:
            rows = [row for row in rows if _contact_matches(row, email=email, phone=phone)]
        rows = rows[:limit]
        return jsonify({"ok": True, "reports": [_public_report(row) for row in rows]})
    except Exception as exc:
        return jsonify({"ok": False, "error": "reports_unavailable", "details": str(exc)}), 503


@bp.get("/<report_ref>")
def get_report(report_ref: str):
    try:
        response = (
            get_supabase()
            .table("relocation_generated_reports")
            .select("*")
            .eq("report_ref", report_ref)
            .limit(1)
            .execute()
        )
        row = (response.data or [None])[0]
        if not row:
            return jsonify({"ok": False, "error": "report_not_found"}), 404
        return jsonify({"ok": True, "report": _public_report(row)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "report_lookup_unavailable", "details": str(exc)}), 503
