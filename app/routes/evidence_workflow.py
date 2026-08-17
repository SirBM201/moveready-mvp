from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from flask import Blueprint, jsonify, request

from app.routes import account_auth
from app.services.supabase_client import get_supabase


bp = Blueprint("evidence_workflow", __name__)
CONTRACT_VERSION = "b12-v1"

DOCUMENT_TYPES = [
    "passport",
    "bank_statement",
    "proof_of_funds",
    "employment_letter",
    "payslip",
    "academic_certificate",
    "academic_transcript",
    "admission_letter",
    "language_test",
    "birth_certificate",
    "marriage_certificate",
    "civil_document",
    "police_certificate",
    "insurance",
    "accommodation",
    "business_plan",
    "company_document",
    "founder_evidence",
    "travel_itinerary",
    "purpose_evidence",
    "relationship_evidence",
    "consent_or_custody_document",
    "medical_document",
    "refusal_record",
    "other",
]

OWNER_SCOPES = ["main_applicant", "spouse", "child", "dependant", "sponsor", "employer", "school", "other"]
DOCUMENT_STATUSES = [
    "available",
    "missing",
    "renewal_needed",
    "translation_pending",
    "legalization_pending",
    "correction_pending",
    "ready",
    "expired",
    "archived",
]
PROCESS_STATUSES = ["not_required", "unknown", "pending", "completed", "rejected"]
ROUTE_CATEGORIES = [
    "visitor",
    "study",
    "work",
    "startup",
    "business",
    "family",
    "digital_nomad",
    "scholarship",
    "permanent_residence",
    "other",
]
APPLICATION_STAGES = ["research", "preparation", "appointment_booked", "submitted", "decision_received", "archived"]
EVENT_TYPES = [
    "visa_refusal",
    "permit_refusal",
    "denied_admission",
    "admission_refusal",
    "startup_endorsement_refusal",
    "scholarship_refusal",
    "other",
]
VISA_STATUSES = ["valid", "cancelled", "revoked", "unknown", "not_applicable"]

FORBIDDEN_SENSITIVE_FIELDS = {
    "file",
    "file_content",
    "file_url",
    "document_number",
    "passport_number",
    "national_id_number",
    "bank_account_number",
    "card_number",
    "otp",
    "password",
    "private_key",
}

REASON_LIBRARY: Dict[str, Dict[str, Any]] = {
    "purpose_not_convincing": {
        "points": 25,
        "label": "Purpose or reason for travel was not convincing",
        "action": "Prepare a concise purpose narrative supported by documents that match the selected route.",
    },
    "intention_to_leave_not_proven": {
        "points": 30,
        "label": "Temporary intention or return plan was not accepted",
        "action": "Address the authority's concern with truthful employment, family, financial, property, study, or other return-context evidence where relevant.",
    },
    "insufficient_funds": {
        "points": 30,
        "label": "Funds were insufficient or unsuitable",
        "action": "Use the current official funds rule and explain income, savings history, sponsors, and any large deposits with traceable evidence.",
    },
    "incomplete_or_inconsistent_documents": {
        "points": 30,
        "label": "Documents were incomplete, inconsistent, or unreliable",
        "action": "Build a document-by-document repair table showing the old gap, corrected evidence, source, and verification status.",
    },
    "credibility_concern": {
        "points": 35,
        "label": "Credibility or interview answers were not accepted",
        "action": "Reconcile every statement with the forms and evidence. Do not invent explanations or hide contradictory facts.",
    },
    "travel_or_immigration_history": {
        "points": 25,
        "label": "Travel or immigration history raised concern",
        "action": "Prepare a complete chronology of applications, visas, refusals, denied admissions, overstays, departures, and current status.",
    },
    "weak_home_or_residence_ties": {
        "points": 20,
        "label": "Home-country or residence ties were considered weak",
        "action": "Explain current residence, work, family responsibilities, lawful status, and realistic return or onward plans without exaggeration.",
    },
    "employment_or_income_not_proven": {
        "points": 25,
        "label": "Employment, business, or income was not sufficiently proven",
        "action": "Use consistent employer, salary, tax, bank, business, contract, or client evidence and explain any unavailable document.",
    },
    "accommodation_or_itinerary_weak": {
        "points": 15,
        "label": "Accommodation or itinerary evidence was weak",
        "action": "Use verifiable, refundable, and route-appropriate plans. Avoid fabricated bookings.",
    },
    "insurance_or_health_requirement": {
        "points": 15,
        "label": "Insurance or health requirement was not met",
        "action": "Confirm the current coverage, dates, territory, wording, exclusions, and accepted insurer requirements.",
    },
    "route_eligibility_not_met": {
        "points": 40,
        "label": "The selected route's eligibility requirement was not met",
        "action": "Re-check the route before reapplying. A different route may be more suitable than trying to repackage the same facts.",
    },
    "business_viability_or_traction": {
        "points": 30,
        "label": "Business viability, innovation, team, market, or traction was weak",
        "action": "Map every decision concern to product evidence, customer validation, market data, team capability, financial assumptions, and measurable progress.",
    },
    "academic_fit_or_progression": {
        "points": 25,
        "label": "Academic fit, progression, grade, or study purpose was weak",
        "action": "Explain the programme fit, progression logic, entry requirements, funding, career use, and any field change truthfully.",
    },
    "misrepresentation_concern": {
        "points": 60,
        "label": "Misrepresentation, false information, or withheld facts were alleged or suspected",
        "action": "Do not reapply casually. Preserve the written decision and seek qualified legal advice before making further representations.",
    },
    "other": {
        "points": 15,
        "label": "Other stated reason",
        "action": "Convert the exact written reason into a specific evidence and explanation task before considering a new application.",
    },
}

BASE_REQUIREMENTS: List[Dict[str, Any]] = [
    {"key": "passport", "label": "Valid passport", "types": ["passport"], "level": "required"},
    {"key": "funds", "label": "Proof of funds and transaction history", "types": ["proof_of_funds", "bank_statement"], "level": "required"},
    {"key": "purpose", "label": "Purpose or route evidence", "types": ["purpose_evidence"], "level": "required"},
]

ROUTE_REQUIREMENTS: Dict[str, List[Dict[str, Any]]] = {
    "visitor": [
        {"key": "itinerary", "label": "Travel itinerary", "types": ["travel_itinerary"], "level": "required"},
        {"key": "accommodation", "label": "Accommodation evidence", "types": ["accommodation"], "level": "required"},
        {"key": "employment", "label": "Employment or income context", "types": ["employment_letter", "payslip", "company_document"], "level": "conditional"},
        {"key": "insurance", "label": "Travel insurance", "types": ["insurance"], "level": "conditional"},
    ],
    "study": [
        {"key": "admission", "label": "Admission or enrolment letter", "types": ["admission_letter"], "level": "required"},
        {"key": "academics", "label": "Academic certificates and transcripts", "types": ["academic_certificate", "academic_transcript"], "level": "required"},
        {"key": "language", "label": "Language evidence where required", "types": ["language_test"], "level": "conditional"},
        {"key": "insurance", "label": "Student or health insurance", "types": ["insurance"], "level": "conditional"},
        {"key": "accommodation", "label": "Accommodation plan", "types": ["accommodation"], "level": "conditional"},
    ],
    "scholarship": [
        {"key": "admission", "label": "Admission or programme evidence", "types": ["admission_letter"], "level": "conditional"},
        {"key": "academics", "label": "Academic certificates and transcripts", "types": ["academic_certificate", "academic_transcript"], "level": "required"},
        {"key": "language", "label": "Language evidence where required", "types": ["language_test"], "level": "conditional"},
        {"key": "purpose", "label": "Statement of purpose or scholarship case", "types": ["purpose_evidence"], "level": "required"},
    ],
    "work": [
        {"key": "employment", "label": "Employment offer or contract", "types": ["employment_letter"], "level": "required"},
        {"key": "qualifications", "label": "Qualifications and experience evidence", "types": ["academic_certificate", "employment_letter", "payslip"], "level": "conditional"},
        {"key": "police", "label": "Police certificate where required", "types": ["police_certificate"], "level": "conditional"},
        {"key": "insurance", "label": "Health or work insurance", "types": ["insurance"], "level": "conditional"},
    ],
    "startup": [
        {"key": "business_plan", "label": "Business or startup plan", "types": ["business_plan"], "level": "required"},
        {"key": "founder", "label": "Founder and team evidence", "types": ["founder_evidence", "employment_letter", "academic_certificate"], "level": "required"},
        {"key": "company", "label": "Company, product, or traction evidence", "types": ["company_document", "purpose_evidence"], "level": "required"},
    ],
    "business": [
        {"key": "business_plan", "label": "Business plan and financial assumptions", "types": ["business_plan"], "level": "required"},
        {"key": "company", "label": "Company and ownership evidence", "types": ["company_document"], "level": "required"},
        {"key": "income", "label": "Business income or funding evidence", "types": ["bank_statement", "proof_of_funds", "company_document"], "level": "required"},
    ],
    "digital_nomad": [
        {"key": "employment", "label": "Remote employment, contracts, or business evidence", "types": ["employment_letter", "company_document"], "level": "required"},
        {"key": "income", "label": "Recurring income and bank evidence", "types": ["bank_statement", "payslip", "proof_of_funds"], "level": "required"},
        {"key": "insurance", "label": "Health or travel insurance", "types": ["insurance"], "level": "conditional"},
        {"key": "accommodation", "label": "Accommodation evidence", "types": ["accommodation"], "level": "conditional"},
    ],
    "family": [
        {"key": "relationship", "label": "Relationship evidence", "types": ["relationship_evidence", "marriage_certificate", "birth_certificate"], "level": "required"},
        {"key": "civil", "label": "Civil-status documents", "types": ["civil_document", "marriage_certificate", "birth_certificate"], "level": "required"},
        {"key": "consent", "label": "Consent or custody evidence where relevant", "types": ["consent_or_custody_document"], "level": "conditional"},
        {"key": "insurance", "label": "Family insurance", "types": ["insurance"], "level": "conditional"},
    ],
    "permanent_residence": [
        {"key": "civil", "label": "Civil-status records", "types": ["civil_document", "marriage_certificate", "birth_certificate"], "level": "required"},
        {"key": "police", "label": "Police or background certificates", "types": ["police_certificate"], "level": "conditional"},
        {"key": "employment", "label": "Employment, tax, business, or residence history", "types": ["employment_letter", "payslip", "company_document", "bank_statement"], "level": "required"},
    ],
    "other": [],
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _text(value: Any, limit: int = 500) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _date(value: Any) -> Optional[date]:
    raw = _text(value, 40)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _string_list(value: Any, *, limit: int = 30, item_limit: int = 300) -> List[str]:
    if isinstance(value, str):
        raw: Sequence[Any] = value.replace("\r", "").replace(";", "\n").split("\n")
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    output: List[str] = []
    for item in raw:
        cleaned = _text(item, item_limit)
        if cleaned and cleaned not in output:
            output.append(cleaned)
        if len(output) >= limit:
            break
    return output


def _risk_level(score: int) -> str:
    if score >= 100:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _readiness_status(risk_level: str) -> str:
    if risk_level == "critical":
        return "qualified_review_required"
    if risk_level == "high":
        return "needs_attention"
    if risk_level == "medium":
        return "review_recommended"
    return "ready_to_continue"


def _auth_email() -> Tuple[Optional[str], Optional[str]]:
    try:
        token = account_auth._extract_session_token()
        if not token:
            return None, "session_token_required"
        session, error = account_auth._load_active_session(token)
        if not session:
            return None, error or "invalid_session"
        email = str(session.get("email") or "").strip().lower()
        return (email or None), (None if email else "session_email_missing")
    except Exception:
        return None, "session_validation_failed"


def _owned_profile_id(email: str, value: Any) -> Optional[str]:
    profile_id = _text(value, 80)
    if not profile_id:
        return None
    try:
        response = (
            get_supabase()
            .table("relocation_user_profiles")
            .select("id,email")
            .eq("id", profile_id)
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        return (response.data or {}).get("id")
    except Exception:
        return None


def _forbidden_fields(payload: Dict[str, Any]) -> List[str]:
    return sorted(key for key in FORBIDDEN_SENSITIVE_FIELDS if payload.get(key) not in (None, "", [], {}))


def _derived_document_status(row: Dict[str, Any]) -> str:
    stored = str(row.get("status") or "available")
    if stored == "archived":
        return stored
    expiry = _date(row.get("expiry_date"))
    if not expiry:
        return stored
    days = (expiry - date.today()).days
    if days < 0:
        return "expired"
    if days <= 180 and stored in {"available", "ready"}:
        return "renewal_needed"
    return stored


def _public_document(row: Dict[str, Any]) -> Dict[str, Any]:
    derived_status = _derived_document_status(row)
    expiry = _date(row.get("expiry_date"))
    return {
        "id": row.get("id"),
        "profile_id": row.get("profile_id"),
        "document_type": row.get("document_type"),
        "document_label": row.get("document_label"),
        "owner_scope": row.get("owner_scope"),
        "name_on_document": row.get("name_on_document"),
        "issuing_country": row.get("issuing_country"),
        "document_language": row.get("document_language"),
        "issue_date": row.get("issue_date"),
        "expiry_date": row.get("expiry_date"),
        "status": row.get("status"),
        "derived_status": derived_status,
        "days_until_expiry": (expiry - date.today()).days if expiry else None,
        "translation_status": row.get("translation_status"),
        "legalization_status": row.get("legalization_status"),
        "sensitive": bool(row.get("sensitive", True)),
        "notes": row.get("notes"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "storage_boundary": "Metadata only. No raw file or full document number is stored by this workflow.",
    }


def _public_pack(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "pack_ref": row.get("pack_ref"),
        "profile_id": row.get("profile_id"),
        "route_category": row.get("route_category"),
        "target_country": row.get("target_country"),
        "application_stage": row.get("application_stage"),
        "status": row.get("status"),
        "completeness_score": row.get("completeness_score"),
        "risk_level": row.get("risk_level"),
        "required_items": row.get("required_items") or [],
        "available_items": row.get("available_items") or [],
        "missing_items": row.get("missing_items") or [],
        "expiring_items": row.get("expiring_items") or [],
        "warnings": row.get("warnings") or [],
        "official_source_notes": row.get("official_source_notes"),
        "generated_from_inventory_at": row.get("generated_from_inventory_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "safety_note": "This pack is a readiness organizer. The current official checklist controls the actual application requirement.",
    }


def _inventory_for_email(email: str, *, include_archived: bool = False, limit: int = 250) -> List[Dict[str, Any]]:
    query = (
        get_supabase()
        .table("relocation_user_document_inventory")
        .select("*")
        .eq("email", email)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if not include_archived:
        query = query.neq("status", "archived")
    response = query.execute()
    return response.data or []


def _store_readiness_run(tool_slug: str, email: str, payload: Dict[str, Any], result: Dict[str, Any]) -> None:
    try:
        safe_payload = {**payload, "email": email}
        metadata = safe_payload.get("metadata") if isinstance(safe_payload.get("metadata"), dict) else {}
        safe_payload["metadata"] = {**metadata, "verified_session_email": email, "private_account_workflow": True}
        get_supabase().table("relocation_readiness_check_runs").insert(
            {
                "tool_slug": tool_slug,
                "status": "completed",
                "risk_level": result.get("risk_level"),
                "readiness_status": result.get("readiness_status"),
                "input_payload": safe_payload,
                "result_payload": result,
                "source_page": _text(payload.get("source_page"), 240),
            }
        ).execute()
        result["stored"] = True
    except Exception:
        result["stored"] = False
        result["storage_note"] = "The result was generated but could not be stored in private account history."


@bp.get("/options")
def options():
    return jsonify(
        {
            "ok": True,
            "contract_version": CONTRACT_VERSION,
            "document_types": DOCUMENT_TYPES,
            "owner_scopes": OWNER_SCOPES,
            "document_statuses": DOCUMENT_STATUSES,
            "process_statuses": PROCESS_STATUSES,
            "route_categories": ROUTE_CATEGORIES,
            "application_stages": APPLICATION_STAGES,
            "refusal_event_types": EVENT_TYPES,
            "visa_statuses": VISA_STATUSES,
            "refusal_reason_options": [
                {"key": key, "label": item["label"]} for key, item in REASON_LIBRARY.items()
            ],
            "storage_boundary": "MoveReady stores document metadata and readiness results only. Do not upload raw passports, bank statements, certificates, refusal letters, passwords, OTPs, card data, or private keys.",
        }
    )


@bp.get("/documents")
def my_documents():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    try:
        rows = _inventory_for_email(email, include_archived=_bool(request.args.get("include_archived")))
        public_rows = [_public_document(row) for row in rows]
        return jsonify(
            {
                "ok": True,
                "contract_version": CONTRACT_VERSION,
                "account_email": email,
                "document_count": len(public_rows),
                "documents": public_rows,
                "storage_boundary": "Metadata only. No raw file or full document number is stored.",
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": "document_inventory_unavailable", "details": str(exc)}), 503


@bp.post("/documents")
def create_document():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    forbidden = _forbidden_fields(payload)
    if forbidden:
        return jsonify(
            {
                "ok": False,
                "error": "raw_or_sensitive_document_field_not_allowed",
                "forbidden_fields": forbidden,
                "storage_boundary": "Store metadata only. Do not submit a raw file or full document number.",
            }
        ), 400

    document_type = _text(payload.get("document_type"), 80)
    document_label = _text(payload.get("document_label"), 180)
    owner_scope = _text(payload.get("owner_scope"), 40) or "main_applicant"
    status = _text(payload.get("status"), 40) or "available"
    translation_status = _text(payload.get("translation_status"), 40) or "unknown"
    legalization_status = _text(payload.get("legalization_status"), 40) or "unknown"

    if document_type not in DOCUMENT_TYPES:
        return jsonify({"ok": False, "error": "invalid_document_type", "allowed": DOCUMENT_TYPES}), 400
    if not document_label:
        return jsonify({"ok": False, "error": "document_label_required"}), 400
    if owner_scope not in OWNER_SCOPES:
        return jsonify({"ok": False, "error": "invalid_owner_scope", "allowed": OWNER_SCOPES}), 400
    if status not in DOCUMENT_STATUSES:
        return jsonify({"ok": False, "error": "invalid_document_status", "allowed": DOCUMENT_STATUSES}), 400
    if translation_status not in PROCESS_STATUSES or legalization_status not in PROCESS_STATUSES:
        return jsonify({"ok": False, "error": "invalid_processing_status", "allowed": PROCESS_STATUSES}), 400

    issue_date = _date(payload.get("issue_date"))
    expiry_date = _date(payload.get("expiry_date"))
    if issue_date and expiry_date and expiry_date < issue_date:
        return jsonify({"ok": False, "error": "expiry_date_before_issue_date"}), 400

    row = {
        "email": email,
        "profile_id": _owned_profile_id(email, payload.get("profile_id")),
        "document_type": document_type,
        "document_label": document_label,
        "owner_scope": owner_scope,
        "name_on_document": _text(payload.get("name_on_document"), 180),
        "issuing_country": _text(payload.get("issuing_country"), 120),
        "document_language": _text(payload.get("document_language"), 80),
        "issue_date": issue_date.isoformat() if issue_date else None,
        "expiry_date": expiry_date.isoformat() if expiry_date else None,
        "status": status,
        "translation_status": translation_status,
        "legalization_status": legalization_status,
        "sensitive": True,
        "notes": _text(payload.get("notes"), 1200),
        "metadata": {
            "source_page": _text(payload.get("source_page"), 240),
            "verified_account": True,
            "raw_file_stored": False,
            "full_document_number_stored": False,
        },
    }
    try:
        response = get_supabase().table("relocation_user_document_inventory").insert(row).execute()
        stored = (response.data or [None])[0]
        if not stored:
            return jsonify({"ok": False, "error": "document_inventory_not_stored"}), 503
        return jsonify({"ok": True, "document": _public_document(stored)})
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "error": "document_inventory_create_failed",
                "details": str(exc),
                "hint": "Apply supabase/migrations/027_evidence_inventory_and_packs.sql.",
            }
        ), 503


@bp.patch("/documents/<document_id>")
def update_document(document_id: str):
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    forbidden = _forbidden_fields(payload)
    if forbidden:
        return jsonify({"ok": False, "error": "raw_or_sensitive_document_field_not_allowed", "forbidden_fields": forbidden}), 400

    allowed_fields = {
        "document_label": (180, None),
        "owner_scope": (40, OWNER_SCOPES),
        "name_on_document": (180, None),
        "issuing_country": (120, None),
        "document_language": (80, None),
        "status": (40, DOCUMENT_STATUSES),
        "translation_status": (40, PROCESS_STATUSES),
        "legalization_status": (40, PROCESS_STATUSES),
        "notes": (1200, None),
    }
    updates: Dict[str, Any] = {}
    for field, (limit, choices) in allowed_fields.items():
        if field not in payload:
            continue
        value = _text(payload.get(field), limit)
        if choices is not None and value not in choices:
            return jsonify({"ok": False, "error": f"invalid_{field}", "allowed": choices}), 400
        updates[field] = value
    for field in ("issue_date", "expiry_date"):
        if field in payload:
            parsed = _date(payload.get(field))
            updates[field] = parsed.isoformat() if parsed else None
    if "profile_id" in payload:
        updates["profile_id"] = _owned_profile_id(email, payload.get("profile_id"))
    if not updates:
        return jsonify({"ok": False, "error": "no_update_fields"}), 400

    try:
        existing_response = (
            get_supabase()
            .table("relocation_user_document_inventory")
            .select("*")
            .eq("id", document_id)
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        existing = existing_response.data
        if not existing:
            return jsonify({"ok": False, "error": "document_not_found"}), 404
        issue_date = _date(updates.get("issue_date") if "issue_date" in updates else existing.get("issue_date"))
        expiry_date = _date(updates.get("expiry_date") if "expiry_date" in updates else existing.get("expiry_date"))
        if issue_date and expiry_date and expiry_date < issue_date:
            return jsonify({"ok": False, "error": "expiry_date_before_issue_date"}), 400
        response = (
            get_supabase()
            .table("relocation_user_document_inventory")
            .update(updates)
            .eq("id", document_id)
            .eq("email", email)
            .execute()
        )
        updated = (response.data or [existing])[0]
        return jsonify({"ok": True, "document": _public_document(updated)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "document_inventory_update_failed", "details": str(exc)}), 503


@bp.get("/packs")
def my_packs():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    try:
        response = (
            get_supabase()
            .table("relocation_evidence_packs")
            .select("*")
            .eq("email", email)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        rows = [_public_pack(row) for row in (response.data or [])]
        return jsonify({"ok": True, "contract_version": CONTRACT_VERSION, "account_email": email, "pack_count": len(rows), "evidence_packs": rows})
    except Exception as exc:
        return jsonify({"ok": False, "error": "evidence_packs_unavailable", "details": str(exc)}), 503


@bp.post("/packs/generate")
def generate_pack():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    route_category = _text(payload.get("route_category"), 80) or "other"
    application_stage = _text(payload.get("application_stage"), 80) or "research"
    if route_category not in ROUTE_CATEGORIES:
        return jsonify({"ok": False, "error": "invalid_route_category", "allowed": ROUTE_CATEGORIES}), 400
    if application_stage not in APPLICATION_STAGES:
        return jsonify({"ok": False, "error": "invalid_application_stage", "allowed": APPLICATION_STAGES}), 400

    try:
        inventory = _inventory_for_email(email)
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "error": "document_inventory_unavailable",
                "details": str(exc),
                "hint": "Apply migration 027 before generating evidence packs.",
            }
        ), 503

    requirements = [dict(item) for item in BASE_REQUIREMENTS]
    requirements.extend(dict(item) for item in ROUTE_REQUIREMENTS.get(route_category, []))
    inventory_public = [_public_document(row) for row in inventory]

    available: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    expiring: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for requirement in requirements:
        matching = [item for item in inventory_public if item.get("document_type") in requirement["types"]]
        ready = [
            item
            for item in matching
            if item.get("derived_status") in {"available", "ready"}
            and item.get("translation_status") not in {"pending", "rejected"}
            and item.get("legalization_status") not in {"pending", "rejected"}
        ]
        expiring_matches = [item for item in matching if item.get("derived_status") in {"renewal_needed", "expired"}]
        if ready:
            available.append({**requirement, "matching_documents": [item.get("document_label") for item in ready]})
        elif requirement.get("level") == "required":
            missing.append(requirement)
        else:
            warnings.append(f"Conditional check not ready: {requirement['label']}.")
        for item in expiring_matches:
            expiring.append(
                {
                    "requirement": requirement["label"],
                    "document_id": item.get("id"),
                    "document_label": item.get("document_label"),
                    "expiry_date": item.get("expiry_date"),
                    "days_until_expiry": item.get("days_until_expiry"),
                    "status": item.get("derived_status"),
                }
            )

    required_count = len([item for item in requirements if item.get("level") == "required"])
    available_required = len([item for item in available if item.get("level") == "required"])
    completeness = round((available_required / required_count) * 100) if required_count else 100
    risk_score = len(missing) * 30 + len([item for item in expiring if item.get("status") == "expired"]) * 25 + len(expiring) * 8
    if application_stage in {"appointment_booked", "submitted"} and missing:
        risk_score += 25
        warnings.append("Required evidence is missing at a late application stage.")
    if not _text(payload.get("official_source_notes"), 1600):
        risk_score += 10
        warnings.append("No current official checklist or source note was recorded for this pack.")

    risk_level = _risk_level(risk_score)
    pack_status = "ready" if not missing and not any(item.get("status") == "expired" for item in expiring) else "review_required"
    if application_stage == "submitted":
        pack_status = "submitted"

    row = {
        "pack_ref": f"MREP-{_now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}",
        "email": email,
        "profile_id": _owned_profile_id(email, payload.get("profile_id")),
        "route_category": route_category,
        "target_country": _text(payload.get("target_country"), 120),
        "application_stage": application_stage,
        "status": pack_status,
        "completeness_score": completeness,
        "risk_level": risk_level,
        "required_items": requirements,
        "available_items": available,
        "missing_items": missing,
        "expiring_items": expiring,
        "warnings": warnings,
        "official_source_notes": _text(payload.get("official_source_notes"), 1600),
        "generated_from_inventory_at": _now_iso(),
        "source_page": _text(payload.get("source_page"), 240) or "/evidence-pack",
        "metadata": {
            "verified_account": True,
            "inventory_document_count": len(inventory),
            "required_item_count": required_count,
            "available_required_count": available_required,
            "raw_files_stored": False,
        },
    }
    try:
        response = get_supabase().table("relocation_evidence_packs").insert(row).execute()
        stored = (response.data or [None])[0]
        if not stored:
            return jsonify({"ok": False, "error": "evidence_pack_not_stored"}), 503
        return jsonify({"ok": True, "contract_version": CONTRACT_VERSION, "evidence_pack": _public_pack(stored)})
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "error": "evidence_pack_create_failed",
                "details": str(exc),
                "hint": "Apply supabase/migrations/027_evidence_inventory_and_packs.sql.",
            }
        ), 503


@bp.post("/refusal-repair")
def refusal_repair():
    email, error = _auth_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401
    payload = request.get_json(silent=True) or {}
    forbidden = _forbidden_fields(payload)
    if forbidden:
        return jsonify({"ok": False, "error": "sensitive_field_not_allowed", "forbidden_fields": forbidden}), 400

    event_type = _text(payload.get("event_type"), 80) or "other"
    visa_status = _text(payload.get("visa_status_after_event"), 40) or "unknown"
    reasons = [item for item in _string_list(payload.get("reason_categories"), limit=20, item_limit=80) if item in REASON_LIBRARY]
    corrected_evidence = _string_list(payload.get("corrected_evidence"), limit=30, item_limit=400)
    written_decision_available = _bool(payload.get("written_decision_available"))
    disclosure_plan_prepared = _bool(payload.get("disclosure_plan_prepared"))
    redacted_confirmed = _bool(payload.get("decision_excerpt_redacted"))
    decision_excerpt = _text(payload.get("decision_excerpt"), 2500)

    if event_type not in EVENT_TYPES:
        return jsonify({"ok": False, "error": "invalid_event_type", "allowed": EVENT_TYPES}), 400
    if visa_status not in VISA_STATUSES:
        return jsonify({"ok": False, "error": "invalid_visa_status", "allowed": VISA_STATUSES}), 400
    if decision_excerpt and not redacted_confirmed:
        return jsonify(
            {
                "ok": False,
                "error": "redaction_confirmation_required",
                "message": "Remove passport numbers, addresses, bank details, case identifiers, barcodes, signatures, and third-party personal data before submitting an excerpt.",
            }
        ), 400

    findings: List[Dict[str, Any]] = []
    actions: List[str] = []
    score = 0

    if not written_decision_available:
        score += 25
        findings.append(
            {
                "severity": "high",
                "issue": "The written decision or official record is not available.",
                "action": "Request or retrieve the official decision record from the responsible authority where a lawful process exists. Do not reconstruct the reason from memory alone.",
            }
        )
    if visa_status == "unknown":
        score += 30
        findings.append(
            {
                "severity": "high",
                "issue": "The visa or permit status after the event is unknown.",
                "action": "Verify the current status with the issuing authority before relying on the visa for travel or Visa Power benefits.",
            }
        )
    elif visa_status in {"cancelled", "revoked"}:
        score += 50
        findings.append(
            {
                "severity": "critical",
                "issue": f"The visa or permit is recorded as {visa_status}.",
                "action": "Do not present it as valid or use it to claim travel benefits. Follow the issuing authority's current instructions.",
            }
        )
    if not disclosure_plan_prepared:
        score += 25
        findings.append(
            {
                "severity": "high",
                "issue": "A truthful future-disclosure plan has not been prepared.",
                "action": "Review the exact wording of future forms and disclose refusals, denied admission, cancellation, revocation, bans, or other events whenever the question requires it.",
            }
        )

    for reason in reasons:
        item = REASON_LIBRARY[reason]
        score += int(item["points"])
        findings.append({"reason": reason, "severity": "critical" if item["points"] >= 50 else "high" if item["points"] >= 30 else "medium", "issue": item["label"], "action": item["action"]})
        actions.append(item["action"])

    if event_type == "denied_admission":
        actions.insert(0, "Record this as denied admission or refusal at the border. Do not describe the trip as a successful entry into the country.")
    if not reasons:
        score += 15
        findings.append(
            {
                "severity": "medium",
                "issue": "No decision reason category was selected.",
                "action": "Obtain the written decision and convert each stated concern into a specific evidence or explanation task.",
            }
        )

    actions.extend(
        [
            "Create a chronology of the application, interview, travel or border event, decision, departure, and every later communication.",
            "Separate facts from assumptions: a refusal, denied admission, visa cancellation, and entry ban are different events and should not be treated as interchangeable without official evidence.",
            "Compare every old concern with a new evidence item, responsible owner, official source, and completion date.",
            "Do not submit fabricated bookings, edited statements, invented employment evidence, or explanations that conflict with the previous record.",
        ]
    )
    if "misrepresentation_concern" in reasons:
        actions.append("Seek qualified immigration legal advice before reapplying or sending a substantive response to the authority.")

    risk_level = _risk_level(score)
    result: Dict[str, Any] = {
        "ok": True,
        "event_type": event_type,
        "decision_date": _date(payload.get("decision_date")).isoformat() if _date(payload.get("decision_date")) else None,
        "issuing_country": _text(payload.get("issuing_country"), 120),
        "issuing_authority": _text(payload.get("issuing_authority"), 180),
        "visa_status_after_event": visa_status,
        "written_decision_available": written_decision_available,
        "risk_score": score,
        "risk_level": risk_level,
        "readiness_status": _readiness_status(risk_level),
        "findings": findings,
        "corrected_evidence": corrected_evidence,
        "repair_actions": list(dict.fromkeys(actions)),
        "decision_excerpt": decision_excerpt,
        "redaction_confirmed": bool(decision_excerpt and redacted_confirmed),
        "summary": "A structured refusal or denied-admission repair plan has been generated. It does not predict approval and does not replace the official decision or qualified legal advice.",
        "safety_note": "Do not hide the event, guess whether a ban exists, or rely on a visa whose status is uncertain. Use the exact questions on each future form and the current instructions of the responsible authority.",
    }
    safe_payload = {
        "event_type": event_type,
        "decision_date": result["decision_date"],
        "issuing_country": result["issuing_country"],
        "issuing_authority": result["issuing_authority"],
        "visa_status_after_event": visa_status,
        "written_decision_available": written_decision_available,
        "disclosure_plan_prepared": disclosure_plan_prepared,
        "reason_categories": reasons,
        "corrected_evidence": corrected_evidence,
        "decision_excerpt": decision_excerpt,
        "decision_excerpt_redacted": bool(decision_excerpt and redacted_confirmed),
        "source_page": _text(payload.get("source_page"), 240) or "/evidence-pack",
    }
    _store_readiness_run("refusal_repair_plan", email, safe_payload, result)
    return jsonify(result)
