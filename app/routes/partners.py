from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase

bp = Blueprint("partners", __name__)

PROVIDER_TYPES = [
    {"code": "courier", "label": "Courier and document delivery"},
    {"code": "insurance", "label": "Insurance provider"},
    {"code": "legalization", "label": "Notary, apostille, attestation, or legalization"},
    {"code": "translation", "label": "Document translation"},
    {"code": "expert_review", "label": "Expert or consultant review"},
    {"code": "admission_support", "label": "Admission or scholarship support"},
    {"code": "accommodation", "label": "Accommodation support"},
    {"code": "airport_pickup", "label": "Airport pickup"},
    {"code": "settlement", "label": "Post-arrival settlement support"},
    {"code": "other", "label": "Other trusted service"},
]

ALLOWED_PROVIDER_TYPES = {item["code"] for item in PROVIDER_TYPES}
ALLOWED_CHANNELS = {"email", "whatsapp", "telegram", "phone"}
PROVIDER_LABELS = {item["code"]: item["label"] for item in PROVIDER_TYPES}


def _clean_text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _clean_list(value: Any, limit: int = 12) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list):
        items = value
    else:
        return []
    cleaned = []
    for item in items:
        text = _clean_text(item, 80)
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _public_provider(row: Dict[str, Any]) -> Dict[str, Any]:
    provider_type = row.get("provider_type") or "other"
    return {
        "id": row.get("id"),
        "provider_type": provider_type,
        "provider_label": PROVIDER_LABELS.get(provider_type, "Trusted service"),
        "business_name": row.get("business_name"),
        "website_url": row.get("website_url"),
        "country": row.get("country"),
        "city": row.get("city"),
        "service_countries": row.get("service_countries") or [],
        "service_summary": row.get("service_summary"),
        "credentials_summary": row.get("credentials_summary"),
        "preferred_contact_channel": row.get("preferred_contact_channel"),
        "public_status": "approved",
        "created_at": row.get("created_at"),
    }


@bp.get("/provider-types")
def provider_types():
    return jsonify({"ok": True, "provider_types": PROVIDER_TYPES})


@bp.get("/approved")
def approved_providers():
    provider_type = _clean_text(request.args.get("provider_type"), 80)
    base_country = _clean_text(request.args.get("country"), 120)

    try:
        query = (
            get_supabase()
            .table("relocation_partner_applications")
            .select(
                "id,provider_type,business_name,website_url,country,city,service_countries,"
                "service_summary,credentials_summary,preferred_contact_channel,created_at"
            )
            .eq("status", "approved")
            .order("created_at", desc=True)
            .limit(60)
        )
        if provider_type in ALLOWED_PROVIDER_TYPES:
            query = query.eq("provider_type", provider_type)
        if base_country:
            query = query.eq("country", base_country)

        response = query.execute()
        providers = [_public_provider(row) for row in (response.data or [])]
        return jsonify({"ok": True, "approved_providers": providers})
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": "approved_provider_directory_unavailable",
            "details": str(exc),
        }), 503


@bp.post("/applications")
def create_partner_application():
    payload = request.get_json(silent=True) or {}
    provider_type = _clean_text(payload.get("provider_type"), 80) or "other"
    business_name = _clean_text(payload.get("business_name"), 180)
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)
    consent_to_contact = bool(payload.get("consent_to_contact"))

    if provider_type not in ALLOWED_PROVIDER_TYPES:
        provider_type = "other"
    if not business_name:
        return jsonify({"ok": False, "error": "business_name_required"}), 400
    if not email and not phone:
        return jsonify({"ok": False, "error": "contact_required"}), 400
    if not consent_to_contact:
        return jsonify({"ok": False, "error": "contact_consent_required"}), 400

    preferred_channel = _clean_text(payload.get("preferred_contact_channel"), 40) or "email"
    if preferred_channel not in ALLOWED_CHANNELS:
        preferred_channel = "email"

    row = {
        "provider_type": provider_type,
        "business_name": business_name,
        "contact_name": _clean_text(payload.get("contact_name"), 180),
        "email": email,
        "phone": phone,
        "website_url": _clean_text(payload.get("website_url"), 255),
        "country": _clean_text(payload.get("country"), 120),
        "city": _clean_text(payload.get("city"), 120),
        "service_countries": _clean_list(payload.get("service_countries")),
        "service_summary": _clean_text(payload.get("service_summary"), 1400),
        "credentials_summary": _clean_text(payload.get("credentials_summary"), 1400),
        "compliance_notes": _clean_text(payload.get("compliance_notes"), 1400),
        "pricing_notes": _clean_text(payload.get("pricing_notes"), 800),
        "preferred_contact_channel": preferred_channel,
        "consent_to_contact": consent_to_contact,
        "source_page": _clean_text(payload.get("source_page"), 240),
        "metadata": {
            "user_agent": request.headers.get("User-Agent"),
            "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
        },
    }

    try:
        response = get_supabase().table("relocation_partner_applications").insert(row).execute()
        stored = (response.data or [None])[0]
        return jsonify({"ok": True, "stored": True, "partner_application": stored})
    except Exception as exc:
        return jsonify({
            "ok": False,
            "stored": False,
            "error": "partner_application_storage_unavailable",
            "details": str(exc),
        }), 503
