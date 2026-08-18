from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify

from app.routes import account_auth, account_controls, watchlist
from app.services.job_actions import build_job_actions
from app.services.smart_alerts import (
    CONTRACT_VERSION,
    PRIORITY_RANK,
    alert,
    dedupe_and_rank,
    normalize_preferences,
    parse_datetime,
)
from app.services.supabase_client import get_supabase


bp = Blueprint("smart_alerts", __name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    owner_column: str = "email",
    order_by: str = "created_at",
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
        logging.exception("Smart Alert source unavailable: %s", table)
        return {"ok": False, "rows": [], "error": "source_unavailable"}


def _safe_public_opportunities() -> Dict[str, Any]:
    try:
        response = (
            get_supabase()
            .table("relocation_opportunities")
            .select(watchlist.OPPORTUNITY_COLUMNS)
            .eq("is_public", True)
            .limit(200)
            .execute()
        )
        return {"ok": True, "rows": response.data or [], "error": None}
    except Exception:
        logging.exception("Smart Alert public opportunity source unavailable")
        return {"ok": False, "rows": [], "error": "source_unavailable"}


def _account_preferences(email: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        row = account_controls._load_preferences(email) or {}
        public = account_controls._public_preferences(row, email)
        return public, normalize_preferences(public.get("smart_alert_preferences"))
    except Exception:
        logging.exception("Smart Alert preferences unavailable")
        public = account_controls._public_preferences(None, email)
        return public, normalize_preferences(None)


def _job_alerts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    priorities = {"warning": "high", "action": "medium", "info": "low"}
    for row in rows:
        alert_type = str(row.get("alert_type") or "")
        if row.get("status") != "unread" or alert_type == "scan_failed":
            continue
        result.append(alert(
            category="jobs",
            source="job_alert",
            record_id=row.get("id"),
            marker=row.get("dedupe_key") or row.get("created_at"),
            priority=priorities.get(str(row.get("severity") or "info"), "medium"),
            title=row.get("title") or "Job monitoring update",
            summary=row.get("summary") or "Review the employer's official vacancy source.",
            href="/jobs/automation",
            detected_at=row.get("created_at"),
            official_url=row.get("source_url"),
            metadata={"alert_type": alert_type},
        ))
    return result


def _job_followup_alerts(applications: List[Dict[str, Any]], recruiters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        alert(
            category="jobs",
            source="job_followup",
            record_id=item.get("id"),
            marker=item.get("due_at"),
            priority=str(item.get("priority") or "medium"),
            title=item.get("title") or "Job-search follow-up",
            summary=item.get("summary") or "Review the private Jobs follow-up.",
            href=item.get("href") or "/jobs",
            due_at=item.get("due_at"),
            detected_at=item.get("created_at"),
            metadata={"kind": item.get("kind")},
        )
        for item in build_job_actions(applications, recruiters)
    ]


def _application_alerts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("status") != "open":
            continue
        result.append(alert(
            category="applications",
            source="application_alert",
            record_id=row.get("id"),
            marker=row.get("alert_key") or row.get("due_at") or row.get("last_detected_at"),
            priority=str(row.get("severity") or "medium"),
            title=row.get("title") or "Application alert",
            summary=row.get("summary") or "Review the application case and current authority instruction.",
            href="/application-alerts",
            due_at=row.get("due_at"),
            detected_at=row.get("last_detected_at") or row.get("created_at"),
            metadata={"alert_type": row.get("alert_type")},
        ))
    return result


def _document_alerts(rows: List[Dict[str, Any]], lead_days: int) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for row in rows:
        if str(row.get("status") or "") == "archived":
            continue
        expiry = parse_datetime(row.get("expiry_date"))
        if not expiry:
            continue
        days = (expiry.date() - _now().date()).days
        if days > lead_days:
            continue
        document_type = str(row.get("document_type") or "document").replace("_", " ")
        label = document_type.title()
        if days < 0:
            priority, timing = "critical", f"expired {abs(days)} day(s) ago"
        elif days <= 14:
            priority, timing = "critical", f"expires in {days} day(s)"
        elif days <= 60:
            priority, timing = "high", f"expires in {days} day(s)"
        else:
            priority, timing = "medium", f"expires in {days} day(s)"
        result.append(alert(
            category="document_expiry",
            source="document_metadata",
            record_id=row.get("id"),
            marker=row.get("expiry_date"),
            priority=priority,
            title=f"{label} {timing}",
            summary="Confirm renewal timing, minimum passport validity, blank-page, translation, legalization, and destination rules before relying on this document.",
            href="/evidence-pack",
            due_at=row.get("expiry_date"),
            detected_at=row.get("updated_at") or row.get("created_at"),
            metadata={"document_type": row.get("document_type"), "days_until_expiry": days},
        ))
    return result


def _language_alerts(
    profiles: List[Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    mistakes: List[Dict[str, Any]],
    inactive_days: int,
) -> List[Dict[str, Any]]:
    if not profiles:
        return []
    due_mistakes = [
        row for row in mistakes
        if not row.get("mastered_at") and (parse_datetime(row.get("next_review_at")) or datetime.max.replace(tzinfo=timezone.utc)) <= _now()
    ]
    if due_mistakes:
        return [alert(
            category="language",
            source="language_review",
            record_id=profiles[0].get("id"),
            marker=f"due:{_now().date().isoformat()}:{len(due_mistakes)}",
            priority="medium",
            title=f"{len(due_mistakes)} language review item(s) are due",
            summary="Continue the selected English, French, or combined practice plan. Practice indicators are not official exam scores.",
            href="/language-coach",
            due_at=_now().isoformat(),
            detected_at=_now().isoformat(),
            metadata={"due_review_count": len(due_mistakes)},
        )]

    latest = parse_datetime((attempts[0] if attempts else {}).get("attempted_at"))
    inactive = (_now() - latest).days if latest else None
    if latest and inactive is not None and inactive < inactive_days:
        return []
    return [alert(
        category="language",
        source="language_momentum",
        record_id=profiles[0].get("id"),
        marker=f"inactive:{_now().date().isoformat()}",
        priority="medium",
        title="Resume your language preparation",
        summary=(
            f"No practice attempt has been recorded for {inactive} day(s). Continue only the language plan you selected."
            if inactive is not None
            else "No practice attempt is recorded yet. Start with the private diagnostic for your selected language."
        ),
        href="/language-coach",
        detected_at=_now().isoformat(),
        metadata={"inactive_days": inactive},
    )]


def _evidence_alerts(rows: List[Dict[str, Any]], refresh_days: int) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "draft")
        if status in {"archived", "submitted"}:
            continue
        updated = parse_datetime(row.get("generated_from_inventory_at") or row.get("updated_at") or row.get("created_at"))
        age = (_now() - updated).days if updated else refresh_days + 1
        risk = str(row.get("risk_level") or "medium")
        if status != "stale" and age < refresh_days:
            continue
        priority = "critical" if risk == "critical" else "high" if status == "stale" or risk == "high" else "medium"
        result.append(alert(
            category="evidence_refresh",
            source="evidence_pack",
            record_id=row.get("id"),
            marker=f"{status}:{updated.date().isoformat() if updated else 'unknown'}",
            priority=priority,
            title=f"Refresh evidence pack {row.get('pack_ref') or ''}".strip(),
            summary=f"This metadata-only pack is {age} day(s) old or marked {status.replace('_', ' ')}. Recheck the current official checklist before submission.",
            href="/evidence-pack",
            detected_at=row.get("updated_at") or row.get("created_at"),
            metadata={"status": status, "risk_level": risk, "age_days": age},
        ))
    return result


def _watch_alerts(subscriptions: List[Dict[str, Any]], opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for subscription in subscriptions:
        if str(subscription.get("status") or "active") != "active":
            continue
        ranked = sorted(
            ((watchlist._opportunity_match(subscription, opportunity), opportunity) for opportunity in opportunities),
            key=lambda item: item[0],
            reverse=True,
        )
        score, opportunity = ranked[0] if ranked else (0, None)
        if not opportunity or score <= 0:
            continue
        event_type, title, message = watchlist._alert_event(opportunity)
        review = watchlist._source_review_state(opportunity)
        requested = set(subscription.get("alert_types") or [])
        if event_type not in requested and not review["review_due"] and not review["source_stale"]:
            continue
        priority = "high" if event_type == "closing_soon" or review["source_stale"] else "medium"
        result.append(alert(
            category="verified_rule_changes",
            source="watchlist",
            record_id=subscription.get("id"),
            marker=f"{opportunity.get('id')}:{event_type}:{opportunity.get('last_verified_at')}",
            priority=priority,
            title=title,
            summary=message,
            href="/watchlist",
            detected_at=opportunity.get("last_verified_at"),
            official_url=opportunity.get("official_url"),
            metadata={
                "event_type": event_type,
                "watch_title": subscription.get("watch_title"),
                "source_confidence": opportunity.get("source_confidence"),
                "review_due": review["review_due"],
                "source_stale": review["source_stale"],
            },
        ))
    return result


def _alert_enabled(row: Dict[str, Any], account: Dict[str, Any], smart: Dict[str, Any]) -> bool:
    category = str(row.get("category") or "")
    if category == "verified_rule_changes":
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        source_signal = bool(metadata.get("review_due") or metadata.get("source_stale"))
        opportunity_signal = str(metadata.get("event_type") or "") != "review_due"
        return bool(
            (source_signal and account.get("source_change_alerts_enabled", True))
            or (opportunity_signal and account.get("opportunity_alerts_enabled", False))
        )
    checks = {
        "jobs": smart["jobs_enabled"],
        "applications": smart["application_followups_enabled"] and bool(account.get("application_deadline_alerts_enabled", True)),
        "document_expiry": bool(account.get("document_expiry_alerts_enabled", True)),
        "language": smart["language_reminders_enabled"],
        "evidence_refresh": smart["evidence_refresh_enabled"],
    }
    return bool(checks.get(category, False))


@bp.get("/smart-alerts")
def smart_alert_inbox():
    email, error_response = _auth_email()
    if error_response:
        return error_response

    source_specs = {
        "job_alerts": ("relocation_job_alerts", "created_at", "email"),
        "job_applications": ("relocation_job_applications", "updated_at", "email"),
        "job_recruiters": ("relocation_job_recruiters", "updated_at", "owner_email"),
        "application_alerts": ("relocation_application_case_alerts", "updated_at", "email"),
        "documents": ("relocation_user_document_inventory", "updated_at", "email"),
        "evidence_packs": ("relocation_evidence_packs", "updated_at", "email"),
        "language_profiles": ("relocation_language_profiles", "updated_at", "email"),
        "language_attempts": ("relocation_language_attempts", "attempted_at", "email"),
        "language_mistakes": ("relocation_language_mistakes", "next_review_at", "email"),
        "watchlist": ("relocation_watchlist_subscriptions", "updated_at", "email"),
    }
    loaded: Dict[str, List[Dict[str, Any]]] = {}
    errors: Dict[str, str] = {}
    for name, (table, order_by, owner_column) in source_specs.items():
        result = _safe_rows(table, email or "", order_by=order_by, owner_column=owner_column)
        loaded[name] = result["rows"]
        if not result["ok"]:
            errors[name] = result["error"]
    opportunities = _safe_public_opportunities()
    if not opportunities["ok"]:
        errors["verified_rule_changes"] = opportunities["error"]

    account_preferences, smart_preferences = _account_preferences(email or "")
    candidates: List[Dict[str, Any]] = []
    candidates.extend(_job_alerts(loaded["job_alerts"]))
    candidates.extend(_job_followup_alerts(loaded["job_applications"], loaded["job_recruiters"]))
    candidates.extend(_application_alerts(loaded["application_alerts"]))
    candidates.extend(_document_alerts(loaded["documents"], smart_preferences["document_expiry_lead_days"]))
    candidates.extend(_language_alerts(
        loaded["language_profiles"],
        loaded["language_attempts"],
        loaded["language_mistakes"],
        smart_preferences["language_inactive_days"],
    ))
    candidates.extend(_evidence_alerts(loaded["evidence_packs"], smart_preferences["evidence_refresh_days"]))
    candidates.extend(_watch_alerts(loaded["watchlist"], opportunities["rows"]))

    ranked = dedupe_and_rank(candidates)
    enabled = [row for row in ranked if _alert_enabled(row, account_preferences, smart_preferences)]
    if smart_preferences["critical_only"]:
        enabled = [row for row in enabled if row.get("priority") == "critical"]
    visible = enabled if account_preferences.get("in_app_notifications_enabled", True) else []

    counts_by_priority = {priority: 0 for priority in PRIORITY_RANK}
    counts_by_category: Dict[str, int] = {}
    for row in visible:
        priority = str(row.get("priority") or "medium")
        category = str(row.get("category") or "other")
        counts_by_priority[priority] = counts_by_priority.get(priority, 0) + 1
        counts_by_category[category] = counts_by_category.get(category, 0) + 1

    return jsonify({
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "account_email": email,
        "generated_at": _now().isoformat(),
        "alert_count": len(visible),
        "candidate_count": len(ranked),
        "suppressed_count": max(0, len(ranked) - len(visible)),
        "counts_by_priority": counts_by_priority,
        "counts_by_category": counts_by_category,
        "primary_alert": visible[0] if visible else None,
        "alerts": visible,
        "preferences": {
            "in_app_notifications_enabled": account_preferences.get("in_app_notifications_enabled", True),
            "source_change_alerts_enabled": account_preferences.get("source_change_alerts_enabled", True),
            "application_deadline_alerts_enabled": account_preferences.get("application_deadline_alerts_enabled", True),
            "document_expiry_alerts_enabled": account_preferences.get("document_expiry_alerts_enabled", True),
            "opportunity_alerts_enabled": account_preferences.get("opportunity_alerts_enabled", False),
            "smart_alert_preferences": smart_preferences,
        },
        "delivery_status": {
            "in_app": "available" if account_preferences.get("in_app_notifications_enabled", True) else "disabled_by_user",
            "email": "not_enabled",
            "whatsapp": "not_enabled",
            "sms": "not_enabled",
            "telegram": "not_enabled",
            "push": "not_enabled",
        },
        "partial_errors": errors,
        "empty_state": (
            "In-app alerts are disabled in account preferences."
            if not account_preferences.get("in_app_notifications_enabled", True)
            else "No enabled launch-critical alert currently needs action."
            if not visible
            else None
        ),
        "safety_note": "B14 consolidates existing private records and verified-account watches. It does not scrape a live authority account, create a duplicate alert store, send an external message, or replace an official deadline, notice, source, employer, exam result, passport rule, visa condition, or application decision.",
    })
