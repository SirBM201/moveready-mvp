from __future__ import annotations

from typing import Any, Mapping

CONTRACT_VERSION = "b19.12.2-v1"
CHANNELS = {"email", "linkedin", "phone", "in_person", "other"}
PURPOSES = {"introduction", "vacancy_question", "application_follow_up", "interview_follow_up", "networking"}


def outreach_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    channel = str(payload.get("channel") or "").strip().casefold()
    purpose = str(payload.get("purpose") or "").strip().casefold()
    if channel not in CHANNELS:
        raise ValueError("unsupported_outreach_channel")
    if purpose not in PURPOSES:
        raise ValueError("unsupported_outreach_purpose")
    consent_confirmed = payload.get("user_confirmed") is True
    destination = str(payload.get("destination") or "").strip() or None
    ready = bool(consent_confirmed and destination)
    return {
        "contract_version": CONTRACT_VERSION,
        "channel": channel,
        "purpose": purpose,
        "destination": destination,
        "ready_for_manual_send": ready,
        "blocking_reasons": ([] if consent_confirmed else ["user_confirmation_required"]) + ([] if destination else ["recorded_destination_required"]),
        "safety": {
            "automatic_send": False,
            "user_must_review_and_send": True,
            "credentials_collected": False,
            "private_contact_discovery": False,
            "delivery_or_response_not_inferred": True,
        },
    }


def outreach_brief(payload: Mapping[str, Any]) -> dict[str, Any]:
    facts = [str(value).strip() for value in payload.get("verified_candidate_facts") or [] if str(value).strip()]
    vacancy = str(payload.get("vacancy_title") or "").strip() or None
    return {
        "contract_version": CONTRACT_VERSION,
        "recruiter_name": str(payload.get("recruiter_name") or "").strip() or None,
        "vacancy_title": vacancy,
        "verified_candidate_facts": facts,
        "requested_topic": str(payload.get("requested_topic") or "").strip() or None,
        "drafting_rules": {
            "fabricate_relationship": False,
            "fabricate_referral": False,
            "fabricate_qualifications": False,
            "claim_sponsorship": False,
            "claim_vacancy_availability_without_evidence": False,
        },
        "safety": {"draft_is_not_sent": True, "manual_review_required": True},
    }
