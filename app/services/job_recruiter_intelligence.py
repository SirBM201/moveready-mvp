from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

CONTRACT_VERSION = "b19.12.1-v1"
RELATIONSHIP_STATES = ("not_contacted", "connection_requested", "connected", "contacted", "responded", "follow_up", "inactive")


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def normalize_recruiter_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (_text(value) or "").casefold()).strip()


def normalize_email(value: Any) -> str | None:
    value = _text(value)
    return value.casefold() if value and "@" in value else None


def recruiter_identity(payload: Mapping[str, Any]) -> dict[str, Any]:
    name = _text(payload.get("recruiter_name") or payload.get("name"))
    if not name:
        raise ValueError("recruiter_name_required")
    email = normalize_email(payload.get("email_address") or payload.get("email"))
    employer_id = _text(payload.get("employer_id") or payload.get("canonical_employer_id") or payload.get("company_id"))
    organization = _text(payload.get("recruitment_company") or payload.get("company_name") or payload.get("organization"))
    normalized_name = normalize_recruiter_name(name)
    basis = "user_recorded_email" if email else "normalized_name_and_employer"
    material = f"email:{email}" if email else f"name:{normalized_name}|employer:{(employer_id or organization or '').casefold()}"
    return {
        "contract_version": CONTRACT_VERSION,
        "canonical_key": hashlib.sha256(material.encode("utf-8")).hexdigest()[:32],
        "recruiter_name": name,
        "normalized_name": normalized_name,
        "email_address": email,
        "employer_id": employer_id,
        "organization": organization,
        "identity_basis": basis,
        "safety": {
            "identity_is_user_recorded_not_verified": True,
            "private_contact_discovery_allowed": False,
            "employment_relationship_inferred": False,
            "response_or_interest_inferred": False,
        },
    }


def relationship_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    state = _text(payload.get("connection_status")) or "not_contacted"
    if state not in RELATIONSHIP_STATES:
        raise ValueError("unsupported_recruiter_relationship_state")
    return {
        "state": state,
        "connected": bool(payload.get("connected")) or state in {"connected", "contacted", "responded", "follow_up"},
        "last_contacted_at": _text(payload.get("last_contacted_at")),
        "follow_up_date": _text(payload.get("follow_up_date")),
        "safety": {
            "state_is_recorded_not_inferred": True,
            "connected_does_not_mean_endorsement": True,
            "response_does_not_mean_job_interest": True,
        },
    }
