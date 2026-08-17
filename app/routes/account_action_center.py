from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.routes import account_auth, application_cases
from app.services.job_actions import build_job_actions
from app.services.supabase_client import get_supabase


bp = Blueprint("account_action_center", __name__)

CONTRACT_VERSION = "b13-v1"
PRIORITY_SCORE = {"low": 20, "medium": 45, "high": 75, "critical": 100}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any, limit: int = 500) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _hours_until(value: Any) -> Optional[float]:
    parsed = _parse_datetime(value)
    if not parsed:
        parsed_date = _parse_date(value)
        if parsed_date:
            parsed = datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
    if not parsed:
        return None
    return round((parsed - _now()).total_seconds() / 3600, 2)


def _auth_email() -> Tuple[Optional[str], Optional[Any]]:
    token = account_auth._auth._extract_session_token()
    if not token:
        return None, (jsonify({"ok": False, "error": "session_token_required"}), 401)
    session, error = account_auth._auth._load_active_session(token)
    if not session:
        return None, (jsonify({"ok": False, "error": error or "invalid_session"}), 401)
    email = str(session.get("email") or "").strip().lower()
    if not email:
        return None, (jsonify({"ok": False, "error": "session_email_missing"}), 401)
    return email, None


def _safe_rows(
    table: str,
    email: str,
    *,
    order_by: str = "created_at",
    owner_column: str = "email",
    limit: int = 250,
) -> Dict[str, Any]:
    try:
        response = (
            get_supabase()
            .table(table)
            .select("*")
            .eq(owner_column, email)
            .order(order_by, desc=True)
            .limit(limit)
            .execute()
        )
        return {"ok": True, "rows": response.data or [], "error": None}
    except Exception:
        logging.exception("Action Center source unavailable: %s", table)
        return {"ok": False, "rows": [], "error": "source_unavailable"}


def _priority_for_hours(hours: Optional[float], *, overdue_critical: bool = True) -> str:
    if hours is None:
        return "medium"
    if hours < 0:
        return "critical" if overdue_critical else "high"
    if hours <= 72:
        return "critical"
    if hours <= 336:
        return "high"
    if hours <= 720:
        return "medium"
    return "low"


def _item(
    *,
    kind: str,
    record_id: Any,
    title: str,
    summary: str,
    priority: str,
    href: str,
    status: Any = None,
    due_at: Any = None,
    created_at: Any = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    hours = _hours_until(due_at)
    score = PRIORITY_SCORE.get(priority, 45)
    if hours is not None:
        if hours < 0:
            score += 40
        elif hours <= 72:
            score += 30
        elif hours <= 336:
            score += 15
    return {
        "kind": kind,
        "id": record_id,
        "title": title,
        "summary": summary,
        "priority": priority,
        "status": status,
        "due_at": due_at,
        "hours_until_due": hours,
        "href": href,
        "score": score,
        "created_at": created_at,
        "metadata": metadata or {},
    }


def _application_alert_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("status") != "open":
            continue
        priority = str(row.get("severity") or "medium")
        items.append(_item(
            kind="application_alert",
            record_id=row.get("id"),
            title=_text(row.get("title"), 180) or "Application alert",
            summary=_text(row.get("summary"), 700) or "Review the application alert.",
            priority=priority if priority in PRIORITY_SCORE else "medium",
            href="/application-alerts",
            status=row.get("status"),
            due_at=row.get("due_at"),
            created_at=row.get("created_at"),
            metadata={"alert_type": row.get("alert_type")},
        ))
    return items


def _application_case_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("status") in {"archived"}:
            continue
        public = application_cases._public_case(row)
        stage = str(public.get("application_stage") or "research")
        source_status = str(public.get("source_status") or "review_required")
        hours = public.get("hours_until_deadline")
        reasons: List[str] = []
        priority = str(public.get("risk_level") or "medium")

        if hours is not None and float(hours) <= 720:
            reasons.append(f"Deadline: {public.get('next_deadline_at')}")
            priority = _priority_for_hours(float(hours))
        if stage == "additional_documents_requested":
            reasons.append("Additional documents were requested")
            priority = "critical" if hours is not None and float(hours) <= 72 else "high"
        if stage == "refused":
            reasons.append("A refusal result needs factual review and next-step planning")
            priority = "high"
        if source_status in {"stale", "unavailable"}:
            reasons.append(f"Official source is {source_status}")
            priority = "critical" if source_status == "unavailable" else "high"
        elif source_status == "review_required" and stage not in {"research", "preparing"}:
            reasons.append("Official source needs review before the next action")
            priority = "high"
        if public.get("status") == "attention_required":
            reasons.append("Case status requires attention")
            priority = "high" if priority != "critical" else priority

        if not reasons:
            continue
        items.append(_item(
            kind="application_case",
            record_id=row.get("id"),
            title=_text(public.get("case_title"), 180) or _text(public.get("case_ref"), 180) or "Application case",
            summary=". ".join(reasons) + ".",
            priority=priority if priority in PRIORITY_SCORE else "medium",
            href="/applications",
            status=public.get("application_stage"),
            due_at=public.get("next_deadline_at"),
            created_at=row.get("created_at"),
            metadata={"case_ref": public.get("case_ref"), "source_status": source_status},
        ))
    return items


def _timeline_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "pending")
        if status in {"done", "cancelled", "archived"}:
            continue
        due_at = row.get("due_date")
        hours = _hours_until(due_at)
        priority = str(row.get("priority") or "medium")
        if status == "missed":
            priority = "critical"
        elif hours is not None and hours <= 720:
            time_priority = _priority_for_hours(hours)
            if PRIORITY_SCORE.get(time_priority, 0) > PRIORITY_SCORE.get(priority, 0):
                priority = time_priority
        elif hours is None and priority not in {"high", "critical"}:
            continue
        items.append(_item(
            kind="timeline",
            record_id=row.get("id"),
            title=_text(row.get("event_title"), 180) or "Timeline task",
            summary=_text(row.get("event_notes"), 700) or "Review and complete this account timeline task.",
            priority=priority if priority in PRIORITY_SCORE else "medium",
            href="/timeline",
            status=status,
            due_at=due_at,
            created_at=row.get("created_at"),
            metadata={"event_type": row.get("event_type")},
        ))
    return items


def _document_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    attention_statuses = {
        "missing": "Document is missing",
        "renewal_needed": "Renewal is needed",
        "translation_pending": "Translation is pending",
        "legalization_pending": "Legalization is pending",
        "correction_pending": "Correction is pending",
        "expired": "Document is expired",
    }
    for row in rows:
        status = str(row.get("status") or "available")
        if status == "archived":
            continue
        expiry = row.get("expiry_date")
        hours = _hours_until(expiry)
        reason = attention_statuses.get(status)
        priority = "medium"
        if status in {"missing", "expired"}:
            priority = "critical"
        elif status in {"renewal_needed", "correction_pending"}:
            priority = "high"
        elif status in {"translation_pending", "legalization_pending"}:
            priority = "high"
        elif hours is not None and hours <= 4320:
            reason = f"Document expires on {expiry}"
            priority = _priority_for_hours(hours, overdue_critical=True)
        if not reason:
            continue
        items.append(_item(
            kind="document",
            record_id=row.get("id"),
            title=_text(row.get("document_label"), 180) or _text(row.get("document_type"), 180) or "Document metadata",
            summary=f"{reason}. Confirm the route-specific validity, translation, legalization, and receiving-authority requirements.",
            priority=priority,
            href="/evidence-pack",
            status=status,
            due_at=expiry,
            created_at=row.get("created_at"),
            metadata={"document_type": row.get("document_type"), "owner_scope": row.get("owner_scope")},
        ))
    return items


def _evidence_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "draft")
        risk = str(row.get("risk_level") or "medium")
        completeness = int(row.get("completeness_score") or 0)
        missing = row.get("missing_items") if isinstance(row.get("missing_items"), list) else []
        if status in {"ready", "submitted", "archived"} and risk not in {"high", "critical"} and completeness >= 100:
            continue
        if status == "stale" or risk == "critical":
            priority = "critical"
        elif status == "review_required" or risk == "high" or completeness < 60:
            priority = "high"
        else:
            priority = "medium"
        missing_labels = [str(item.get("label") or item.get("key") or "item") for item in missing[:5] if isinstance(item, dict)]
        summary = f"Completeness {completeness}%. Status: {status.replace('_', ' ')}."
        if missing_labels:
            summary += f" Missing: {', '.join(missing_labels)}."
        items.append(_item(
            kind="evidence_pack",
            record_id=row.get("id"),
            title=_text(row.get("pack_ref"), 180) or "Evidence pack",
            summary=summary,
            priority=priority,
            href="/evidence-pack",
            status=status,
            created_at=row.get("created_at"),
            metadata={"risk_level": risk, "completeness_score": completeness},
        ))
    return items


def _quote_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "draft")
        if status not in {"sent", "accepted", "payment_pending", "disputed"}:
            continue
        if status == "disputed":
            priority = "critical"
            summary = "A commercial quote or payment is disputed. Review the scope, reference, evidence, refund terms, and support case."
        elif status == "payment_pending":
            priority = "high"
            summary = "Payment is pending. Verify the approved checkout process, amount, currency, reference, and refund terms before paying."
        elif status == "sent":
            priority = "medium"
            summary = "A quote is ready for review. Check deliverables, exclusions, provider, separated fees, expiry, and refund terms."
        else:
            priority = "medium"
            summary = "The quote was accepted. Review the next verified payment or fulfillment step."
        items.append(_item(
            kind="quote",
            record_id=row.get("id"),
            title=_text(row.get("quote_ref"), 180) or _text(row.get("service_title"), 180) or "Commercial quote",
            summary=summary,
            priority=priority,
            href="/billing",
            status=status,
            due_at=row.get("expires_at"),
            created_at=row.get("created_at"),
            metadata={"currency": row.get("currency"), "total_amount": row.get("total_amount")},
        ))
    return items


def _handoff_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "draft")
        if status in {"completed", "cancelled"}:
            continue
        if status == "pending_user_consent":
            priority = "high"
            summary = "Review the exact provider, purpose, shared fields, privacy terms, and delivery channel before consenting."
        elif status in {"blocked", "disputed"}:
            priority = "critical"
            summary = "The provider handoff is blocked or disputed. Review the consent, delivery, provider, payment, and support records."
        elif status in {"ready_to_share", "consent_confirmed"}:
            priority = "medium"
            summary = "Consent is recorded. Confirm the exact approved fields and delivery controls before any sharing occurs."
        else:
            continue
        items.append(_item(
            kind="handoff",
            record_id=row.get("id"),
            title=_text(row.get("handoff_ref"), 180) or _text(row.get("service_title"), 180) or "Provider handoff",
            summary=summary,
            priority=priority,
            href="/support-center",
            status=status,
            created_at=row.get("created_at"),
            metadata={"provider_name": row.get("provider_name"), "service_slug": row.get("service_slug")},
        ))
    return items


def _support_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "open")
        if status not in {"waiting_user", "escalated"}:
            continue
        priority = str(row.get("priority") or "medium")
        if status == "escalated" and priority != "critical":
            priority = "high"
        items.append(_item(
            kind="support_case",
            record_id=row.get("id"),
            title=_text(row.get("subject"), 180) or _text(row.get("case_ref"), 180) or "Support case",
            summary="MoveReady is waiting for your response." if status == "waiting_user" else "This support case is escalated and needs review.",
            priority=priority if priority in PRIORITY_SCORE else "medium",
            href="/support-center",
            status=status,
            created_at=row.get("created_at"),
            metadata={"case_ref": row.get("case_ref"), "case_type": row.get("case_type")},
        ))
    return items


def _privacy_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "received")
        if status not in {"identity_verification_required", "waiting_user"}:
            continue
        request_type = str(row.get("request_type") or "other")
        items.append(_item(
            kind="privacy_request",
            record_id=row.get("id"),
            title=_text(row.get("request_ref"), 180) or "Privacy request",
            summary="Identity reverification or user information is required before this privacy request can continue.",
            priority="high" if request_type in {"account_deletion", "consent_withdrawal"} else "medium",
            href="/settings#privacy",
            status=status,
            created_at=row.get("created_at"),
            metadata={"request_type": request_type},
        ))
    return items


def _job_items(applications: List[Dict[str, Any]], recruiters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        _item(
            kind=str(action.get("kind") or "job_follow_up"),
            record_id=action.get("id"),
            title=_text(action.get("title"), 180) or "Job-search follow-up",
            summary=_text(action.get("summary"), 700) or "Review the Jobs workspace follow-up.",
            priority=str(action.get("priority") or "medium"),
            href=str(action.get("href") or "/jobs"),
            status=action.get("status"),
            due_at=action.get("due_at"),
            created_at=action.get("created_at"),
            metadata=action.get("metadata") if isinstance(action.get("metadata"), dict) else {},
        )
        for action in build_job_actions(applications, recruiters)
    ]


def _active_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in rows if str(row.get("status") or "active").lower() not in {"archived", "closed"}]


def _attention_count(actions: List[Dict[str, Any]], kinds: set[str]) -> int:
    return sum(
        1
        for action in actions
        if action.get("kind") in kinds and action.get("priority") in {"critical", "high"}
    )


def _engine(
    *,
    key: str,
    phase: str,
    title: str,
    state: str,
    summary: str,
    href: str,
    action_label: str,
    record_count: int,
    attention_count: int = 0,
) -> Dict[str, Any]:
    return {
        "key": key,
        "phase": phase,
        "title": title,
        "state": state,
        "summary": summary,
        "href": href,
        "action_label": action_label,
        "record_count": record_count,
        "attention_count": attention_count,
    }


def _engine_statuses(loaded: Dict[str, List[Dict[str, Any]]], actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    profiles = _active_rows(loaded.get("profiles", []))
    profile = profiles[0] if profiles else {}
    routes = _active_rows(loaded.get("saved_routes", []))
    job_profiles = _active_rows(loaded.get("job_profiles", []))
    job_records = [*loaded.get("job_applications", []), *loaded.get("job_recruiters", [])]
    language_profiles = loaded.get("language_profiles", [])
    language_attempts = loaded.get("language_attempts", [])
    documents = _active_rows(loaded.get("documents", []))
    packs = _active_rows(loaded.get("evidence_packs", []))
    cases = _active_rows(loaded.get("application_cases", []))

    job_attention = _attention_count(actions, {"job_application_follow_up", "job_recruiter_follow_up"})
    document_attention = _attention_count(actions, {"document", "evidence_pack"})
    application_attention = _attention_count(actions, {"application_alert", "application_case", "timeline"})

    has_job_activity = bool(job_profiles or job_records)
    has_route = bool(routes)
    has_passport_context = bool(profile.get("nationality"))
    has_financial_context = profile.get("available_funds_amount") not in (None, "")

    return [
        _engine(
            key="jobs",
            phase="FIND",
            title="Jobs",
            state="attention" if job_attention else "active" if has_job_activity else "needs_assessment",
            summary=(
                f"{job_attention} career follow-up action(s) need attention."
                if job_attention
                else "Your private job-search profile or tracked activity is connected."
                if has_job_activity
                else "Set your search scope before treating any vacancy as a realistic international opportunity."
            ),
            href="/jobs",
            action_label="Review Jobs",
            record_count=len(job_profiles) + len(job_records),
            attention_count=job_attention,
        ),
        _engine(
            key="route_finder",
            phase="FIND",
            title="Route Finder",
            state="active" if has_route else "not_started" if profiles else "needs_assessment",
            summary=(
                f"{len(routes)} saved route or country option(s) are available to the other engines."
                if has_route
                else "Find and save a source-backed route before planning evidence or execution."
            ),
            href="/find",
            action_label="Open Route Finder",
            record_count=len(routes),
        ),
        _engine(
            key="passport",
            phase="QUALIFY",
            title="Passport",
            state="ready" if has_passport_context else "needs_assessment",
            summary=(
                "Nationality context is saved; verify current destination access and personal-history conditions."
                if has_passport_context
                else "Add nationality to your profile before using passport-access results for planning."
            ),
            href="/passport-index" if has_passport_context else "/dashboard#profile-dashboard",
            action_label="Check passport access" if has_passport_context else "Complete profile context",
            record_count=1 if has_passport_context else 0,
        ),
        _engine(
            key="language",
            phase="QUALIFY",
            title="Language",
            state="active" if language_profiles or language_attempts else "needs_assessment",
            summary=(
                f"Language preparation is connected with {len(language_attempts)} recent practice attempt(s)."
                if language_profiles or language_attempts
                else "Set a target exam and level before relying on language preparation progress."
            ),
            href="/language-coach",
            action_label="Open Language Coach",
            record_count=len(language_profiles) + len(language_attempts),
        ),
        _engine(
            key="financial_readiness",
            phase="QUALIFY",
            title="Financial Readiness",
            state="ready" if has_financial_context and has_route else "needs_assessment",
            summary=(
                "A saved route and profile funds are available for a planning-only readiness check."
                if has_financial_context and has_route
                else "Add profile funds and save a route; official proof-of-funds rules still require source verification."
            ),
            href="/budget-calculator",
            action_label="Check financial readiness",
            record_count=(1 if has_financial_context else 0) + len(routes),
        ),
        _engine(
            key="documents",
            phase="MOVE",
            title="Documents",
            state="attention" if document_attention else "active" if documents or packs else "not_started",
            summary=(
                f"{document_attention} document or evidence action(s) need attention."
                if document_attention
                else f"{len(documents)} document record(s) and {len(packs)} evidence pack(s) are connected."
                if documents or packs
                else "Start with metadata only after you have a serious route; do not upload raw identity documents."
            ),
            href="/evidence-pack",
            action_label="Review documents",
            record_count=len(documents) + len(packs),
            attention_count=document_attention,
        ),
        _engine(
            key="applications",
            phase="MOVE",
            title="Applications",
            state="attention" if application_attention else "active" if cases else "not_started",
            summary=(
                f"{application_attention} application or timeline action(s) need attention."
                if application_attention
                else f"{len(cases)} live application case(s) are connected."
                if cases
                else "Create a private case only when a real application or execution process begins."
            ),
            href="/applications",
            action_label="Review applications" if cases else "Open Application Center",
            record_count=len(cases),
            attention_count=application_attention,
        ),
    ]


def _fallback_action(
    *,
    kind: str,
    title: str,
    summary: str,
    href: str,
    engine_key: str,
) -> Dict[str, Any]:
    return {
        **_item(
            kind=kind,
            record_id=None,
            title=title,
            summary=summary,
            priority="medium",
            href=href,
            status="recommended",
        ),
        "source": "orchestration_fallback",
        "engine_key": engine_key,
        "reason": "Foundational account step",
    }


def _primary_action(loaded: Dict[str, List[Dict[str, Any]]], actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    profiles = _active_rows(loaded.get("profiles", []))
    routes = _active_rows(loaded.get("saved_routes", []))

    urgent = next((action for action in actions if action.get("priority") in {"critical", "high"}), None)
    if urgent:
        return {**urgent, "source": "ranked_record", "reason": "Highest-ranked blocker or time-sensitive record"}
    if not profiles:
        return _fallback_action(
            kind="profile_foundation",
            title="Create your MoveReady profile",
            summary="Save one private profile so Route Finder and the qualification engines use the same facts.",
            href="/onboarding",
            engine_key="profile",
        )
    if not routes:
        return _fallback_action(
            kind="route_foundation",
            title="Find and save a realistic route",
            summary="Compare source-backed options before preparing route-specific evidence, funds, or execution steps.",
            href="/find",
            engine_key="route_finder",
        )
    if actions:
        return {**actions[0], "source": "ranked_record", "reason": "Highest-ranked recorded follow-up"}

    goal = str(profiles[0].get("main_goal") or "").lower()
    if goal in {"work", "opportunity"} and not _active_rows(loaded.get("job_profiles", [])):
        return _fallback_action(
            kind="jobs_foundation",
            title="Set your international job-search scope",
            summary="Record where you can work and which countries you are targeting before reviewing vacancy matches.",
            href="/jobs",
            engine_key="jobs",
        )
    if not loaded.get("language_profiles"):
        return _fallback_action(
            kind="language_foundation",
            title="Set your language target",
            summary="Choose the relevant exam and target level so preparation gaps remain tied to your goal.",
            href="/language-coach",
            engine_key="language",
        )
    if not _active_rows(loaded.get("documents", [])) and not _active_rows(loaded.get("evidence_packs", [])):
        return _fallback_action(
            kind="documents_foundation",
            title="Start your route-specific evidence checklist",
            summary="Record metadata and missing requirements without uploading raw identity documents.",
            href="/evidence-pack",
            engine_key="documents",
        )
    return _fallback_action(
        kind="journey_review",
        title="Review your complete journey",
        summary="Your foundations are connected. Review every recorded stage before starting a new application step.",
        href="/my-journey",
        engine_key="journey",
    )


@bp.get("/action-center")
def action_center():
    email, error_response = _auth_email()
    if error_response:
        return error_response

    try:
        limit = max(10, min(int(request.args.get("limit") or 150), 300))
    except Exception:
        limit = 150

    sources = {
        "profiles": ("relocation_user_profiles", "updated_at"),
        "saved_routes": ("relocation_saved_routes", "updated_at"),
        "job_profiles": ("relocation_job_search_profiles", "updated_at"),
        "language_profiles": ("relocation_language_profiles", "updated_at"),
        "language_attempts": ("relocation_language_attempts", "attempted_at"),
        "application_alerts": ("relocation_application_case_alerts", "updated_at"),
        "application_cases": ("relocation_application_cases", "updated_at"),
        "timeline": ("relocation_timeline_events", "updated_at"),
        "documents": ("relocation_user_document_inventory", "updated_at"),
        "evidence_packs": ("relocation_evidence_packs", "updated_at"),
        "quotes": ("relocation_commercial_quotes", "updated_at"),
        "handoffs": ("relocation_service_handoffs", "updated_at"),
        "support_cases": ("relocation_support_cases", "updated_at"),
        "privacy_requests": ("relocation_privacy_requests", "updated_at", "email"),
        "job_applications": ("relocation_job_applications", "updated_at", "email"),
        "job_recruiters": ("relocation_job_recruiters", "updated_at", "owner_email"),
    }
    loaded: Dict[str, List[Dict[str, Any]]] = {}
    errors: Dict[str, str] = {}
    for name, source in sources.items():
        table, order_by, *owner_columns = source
        result = _safe_rows(table, email or "", order_by=order_by, owner_column=owner_columns[0] if owner_columns else "email")
        loaded[name] = result["rows"]
        if not result["ok"]:
            errors[name] = result["error"]

    sections: Dict[str, List[Dict[str, Any]]] = {
        "application_alerts": _application_alert_items(loaded["application_alerts"]),
        "application_cases": _application_case_items(loaded["application_cases"]),
        "timeline": _timeline_items(loaded["timeline"]),
        "documents": _document_items(loaded["documents"]),
        "evidence_packs": _evidence_items(loaded["evidence_packs"]),
        "quotes": _quote_items(loaded["quotes"]),
        "handoffs": _handoff_items(loaded["handoffs"]),
        "support_cases": _support_items(loaded["support_cases"]),
        "privacy_requests": _privacy_items(loaded["privacy_requests"]),
        "jobs": _job_items(loaded["job_applications"], loaded["job_recruiters"]),
    }

    actions: List[Dict[str, Any]] = []
    for items in sections.values():
        actions.extend(items)
    actions.sort(
        key=lambda item: (
            int(item.get("score") or 0),
            -(float(item.get("hours_until_due")) if item.get("hours_until_due") is not None else 999999),
            str(item.get("created_at") or ""),
        ),
        reverse=True,
    )

    counts_by_priority = {priority: 0 for priority in PRIORITY_SCORE}
    for item in actions:
        priority = str(item.get("priority") or "medium")
        counts_by_priority[priority] = counts_by_priority.get(priority, 0) + 1

    engine_statuses = _engine_statuses(loaded, actions)
    primary_action = _primary_action(loaded, actions)

    return jsonify({
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "account_email": email,
        "generated_at": _now().isoformat(),
        "journey_model": {
            "name": "FIND_QUALIFY_MOVE",
            "phases": [
                {"key": "FIND", "label": "Find a realistic opportunity and route"},
                {"key": "QUALIFY", "label": "Check passport, language, and financial readiness"},
                {"key": "MOVE", "label": "Prepare documents and track real applications"},
            ],
        },
        "primary_action": primary_action,
        "engine_statuses": engine_statuses,
        "action_count": min(len(actions), limit),
        "counts_by_priority": counts_by_priority,
        "counts_by_section": {name: len(items) for name, items in sections.items()},
        "actions": actions[:limit],
        "sections": sections,
        "partial_errors": errors,
        "empty_state": "No urgent account action was detected. Continue to verify official sources and review your account before spending or submitting." if not actions else None,
        "safety_note": "The B13 dashboard orchestrates existing private records and profile context without creating a duplicate store. Ready means ready for the next planning check, not eligible, approved, funded, hired, admitted, or authorized. Confirm current official sources before spending, submitting, booking, or relying on a deadline.",
    })
