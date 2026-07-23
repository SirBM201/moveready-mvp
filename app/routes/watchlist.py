from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.core.config import OPPORTUNITY_ALERTS_ENABLED, WHATSAPP_ALERTS_ENABLED
from app.routes import account_auth
from app.services.supabase_client import get_supabase


bp = Blueprint("watchlist", __name__)

ALERT_TYPES = [
    {"code": "opens", "label": "Application opens"},
    {"code": "closing_soon", "label": "Closing soon"},
    {"code": "results_open", "label": "Results/check status opens"},
    {"code": "eligibility_change", "label": "Eligibility changes"},
    {"code": "document_change", "label": "Document requirement changes"},
    {"code": "funds_change", "label": "Proof-of-funds changes"},
    {"code": "fee_change", "label": "Fee changes"},
    {"code": "review_due", "label": "Source review due"},
]

WATCH_TYPES = {"route", "opportunity", "scholarship", "country", "service"}
CHANNELS = {"email", "whatsapp", "telegram", "phone", "in_app"}
STATUSES = {"active", "paused", "unsubscribed", "closed", "spam"}

OPPORTUNITY_COLUMNS = (
    "id,opportunity_code,country_code,country_name,opportunity_name,opportunity_type,"
    "route_category,availability_status,official_url,result_check_url,summary,eligibility_summary,"
    "application_window_summary,safety_notes,source_confidence,last_verified_at,next_review_due_at,tags,is_public"
)


def _clean_text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _clean_list(value: Any, allowed: Optional[set[str]] = None, limit: int = 12) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        cleaned = _clean_text(item, 80)
        if not cleaned:
            continue
        if allowed and cleaned not in allowed:
            continue
        if cleaned not in out:
            out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def _verified_session_email() -> Tuple[Optional[str], Optional[str]]:
    try:
        token = account_auth._auth._extract_session_token()
        if not token:
            return None, "session_token_required"
        session, error = account_auth._auth._load_active_session(token)
        if not session:
            return None, error or "invalid_session"
        email = str(session.get("email") or "").strip().lower()
        if not email:
            return None, "session_email_missing"
        return email, None
    except Exception:
        return None, "session_validation_failed"


def _parse_date(value: Any) -> Optional[date]:
    raw = _clean_text(value, 60)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return date.fromisoformat(raw[:10])
        except Exception:
            return None


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _opportunity_match(subscription: Dict[str, Any], opportunity: Dict[str, Any]) -> int:
    watch_type = _lower(subscription.get("watch_type"))
    watch_code = _lower(subscription.get("watch_code"))
    watch_title = _lower(subscription.get("watch_title"))
    target_country = _lower(subscription.get("target_country"))
    route_or_goal = _lower(subscription.get("route_or_goal"))

    opportunity_code = _lower(opportunity.get("opportunity_code"))
    opportunity_name = _lower(opportunity.get("opportunity_name"))
    country_name = _lower(opportunity.get("country_name"))
    route_category = _lower(opportunity.get("route_category"))

    score = 0
    if watch_code and watch_code == opportunity_code:
        score += 100
    if watch_title and (watch_title == opportunity_name or watch_title in opportunity_name or opportunity_name in watch_title):
        score += 60
    if watch_type == "country" and target_country and target_country == country_name:
        score += 50
    if watch_type in {"route", "scholarship"} and route_or_goal:
        if route_or_goal == route_category:
            score += 50
        elif route_or_goal in opportunity_name or route_or_goal in route_category:
            score += 30
    if target_country and target_country == country_name:
        score += 15
    return score


def _alert_event(opportunity: Dict[str, Any]) -> Tuple[str, str, str]:
    status = _lower(opportunity.get("availability_status"))
    if status in {"open", "available", "accepting_applications"}:
        return "opens", "Applications appear open", "The opportunity is currently marked open. Confirm the official page and exact deadline before applying."
    if status in {"closing_soon", "closing", "deadline_soon"}:
        return "closing_soon", "Application window may be closing soon", "Check the official deadline, timezone, payment, submission, and document-completion requirements immediately."
    if status in {"results_open", "results", "result_check_open"}:
        return "results_open", "Result or status checking appears open", "Use only the official result or status-check page and keep your reference or confirmation number private."
    if status in {"paused", "closed", "cap_reached"}:
        return "eligibility_change", "Availability is limited or closed", "The opportunity is currently marked paused, closed, or capped. Do not pay anyone claiming to bypass the official status."
    return "review_due", "Monitoring continues", "No confirmed opening event is stored. Re-check the official source before relying on dates or availability."


def _source_review_state(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    due = _parse_date(opportunity.get("next_review_due_at"))
    verified = _parse_date(opportunity.get("last_verified_at"))
    is_due = bool(due and due <= today)
    age_days = (today - verified).days if verified else None
    return {
        "last_verified_at": opportunity.get("last_verified_at"),
        "next_review_due_at": opportunity.get("next_review_due_at"),
        "review_due": is_due,
        "verification_age_days": age_days,
        "source_stale": bool(age_days is None or age_days > 45),
    }


def _public_subscription(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "watch_type": row.get("watch_type"),
        "watch_code": row.get("watch_code"),
        "watch_title": row.get("watch_title"),
        "preferred_channel": row.get("preferred_channel"),
        "target_country": row.get("target_country"),
        "route_or_goal": row.get("route_or_goal"),
        "alert_types": row.get("alert_types") or [],
        "status": row.get("status") or "active",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@bp.get("/options")
def watchlist_options():
    return jsonify(
        {
            "ok": True,
            "watch_types": sorted(WATCH_TYPES),
            "channels": sorted(CHANNELS),
            "alert_types": ALERT_TYPES,
            "delivery_status": {
                "in_app": "available_for_verified_accounts",
                "email": "controlled_rollout" if OPPORTUNITY_ALERTS_ENABLED else "not_enabled",
                "whatsapp": "controlled_rollout" if WHATSAPP_ALERTS_ENABLED else "not_enabled",
                "telegram": "not_enabled",
                "phone": "manual_review_only",
            },
        }
    )


@bp.get("/inbox")
def watchlist_inbox():
    email, error = _verified_session_email()
    if not email:
        return jsonify({"ok": False, "error": error or "session_required"}), 401

    try:
        subscriptions_response = (
            get_supabase()
            .table("relocation_watchlist_subscriptions")
            .select("*")
            .eq("email", email)
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        subscriptions = subscriptions_response.data or []
    except Exception as exc:
        return jsonify({"ok": False, "error": "watchlist_inbox_unavailable", "details": str(exc)}), 503

    try:
        opportunities_response = (
            get_supabase()
            .table("relocation_opportunities")
            .select(OPPORTUNITY_COLUMNS)
            .eq("is_public", True)
            .limit(200)
            .execute()
        )
        opportunities = opportunities_response.data or []
    except Exception:
        opportunities = []

    alerts: List[Dict[str, Any]] = []
    monitored_items: List[Dict[str, Any]] = []

    for subscription in subscriptions:
        public_subscription = _public_subscription(subscription)
        requested_alerts = set(subscription.get("alert_types") or [])
        ranked = sorted(
            (
                (_opportunity_match(subscription, opportunity), opportunity)
                for opportunity in opportunities
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        best_score, best_opportunity = ranked[0] if ranked else (0, None)

        monitored = {
            "subscription": public_subscription,
            "match_status": "matched_public_opportunity" if best_opportunity and best_score > 0 else "subscription_active_no_database_match",
            "match_score": best_score,
            "opportunity": best_opportunity,
        }
        monitored_items.append(monitored)

        if not best_opportunity or best_score <= 0:
            continue

        event_type, title, message = _alert_event(best_opportunity)
        review_state = _source_review_state(best_opportunity)
        should_include = event_type in requested_alerts or review_state["review_due"] or review_state["source_stale"]
        if not should_include:
            continue

        alert_types = [event_type]
        if review_state["review_due"] and "review_due" not in alert_types:
            alert_types.append("review_due")

        alerts.append(
            {
                "id": f"{subscription.get('id')}:{best_opportunity.get('opportunity_code') or best_opportunity.get('id')}",
                "subscription_id": subscription.get("id"),
                "alert_types": alert_types,
                "severity": "high" if event_type == "closing_soon" or review_state["source_stale"] else "medium",
                "title": title,
                "message": message,
                "watch_title": subscription.get("watch_title") or subscription.get("watch_code"),
                "opportunity_code": best_opportunity.get("opportunity_code"),
                "opportunity_name": best_opportunity.get("opportunity_name"),
                "country_name": best_opportunity.get("country_name"),
                "availability_status": best_opportunity.get("availability_status"),
                "official_url": best_opportunity.get("official_url"),
                "result_check_url": best_opportunity.get("result_check_url"),
                "source_confidence": best_opportunity.get("source_confidence"),
                "review_state": review_state,
                "preferred_channel": subscription.get("preferred_channel"),
                "delivery_channel": "in_app",
                "delivery_status": "displayed_in_verified_account",
                "safety_note": best_opportunity.get("safety_notes") or "Confirm the official source before applying, paying, travelling, or sharing personal information.",
            }
        )

    alerts.sort(
        key=lambda item: (
            1 if item.get("severity") == "high" else 0,
            str(item.get("opportunity_name") or ""),
        ),
        reverse=True,
    )

    return jsonify(
        {
            "ok": True,
            "account_email": email,
            "subscription_count": len(subscriptions),
            "alert_count": len(alerts),
            "alerts": alerts,
            "monitored_items": monitored_items,
            "delivery_status": {
                "in_app": "available",
                "email": "controlled_rollout" if OPPORTUNITY_ALERTS_ENABLED else "not_enabled",
                "whatsapp": "controlled_rollout" if WHATSAPP_ALERTS_ENABLED else "not_enabled",
                "telegram": "not_enabled",
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "safety_note": "In-app alerts summarize stored source records. Open the official source and confirm the current rule, deadline, timezone, eligibility, fees, documents, quota, and result-check process.",
        }
    )


@bp.post("/subscriptions")
def create_subscription():
    payload = request.get_json(silent=True) or {}
    watch_type = _clean_text(payload.get("watch_type"), 40) or "route"
    preferred_channel = _clean_text(payload.get("preferred_channel"), 40) or "email"
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)
    consent_to_contact = bool(payload.get("consent_to_contact"))

    if watch_type not in WATCH_TYPES:
        return jsonify({"ok": False, "error": "invalid_watch_type", "allowed_watch_types": sorted(WATCH_TYPES)}), 400
    if preferred_channel not in CHANNELS:
        return jsonify({"ok": False, "error": "invalid_channel", "allowed_channels": sorted(CHANNELS)}), 400
    if not email and not phone:
        return jsonify({"ok": False, "error": "contact_required"}), 400
    if not consent_to_contact:
        return jsonify({"ok": False, "error": "contact_consent_required"}), 400

    alert_types = _clean_list(payload.get("alert_types"), {item["code"] for item in ALERT_TYPES})
    if not alert_types:
        alert_types = ["opens", "closing_soon", "eligibility_change"]

    row = {
        "watch_type": watch_type,
        "watch_code": _clean_text(payload.get("watch_code"), 120),
        "watch_title": _clean_text(payload.get("watch_title"), 180),
        "full_name": _clean_text(payload.get("full_name"), 180),
        "email": email,
        "phone": phone,
        "preferred_channel": preferred_channel,
        "current_country": _clean_text(payload.get("current_country"), 120),
        "target_country": _clean_text(payload.get("target_country"), 120),
        "route_or_goal": _clean_text(payload.get("route_or_goal"), 180),
        "alert_types": alert_types,
        "consent_to_contact": consent_to_contact,
        "source_page": _clean_text(payload.get("source_page"), 240),
        "metadata": {
            "user_agent": request.headers.get("User-Agent"),
            "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
        },
    }

    try:
        response = get_supabase().table("relocation_watchlist_subscriptions").insert(row).execute()
        stored = (response.data or [None])[0]
        return jsonify({"ok": True, "stored": True, "subscription": stored})
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "stored": False,
                "error": "watchlist_storage_unavailable",
                "details": str(exc),
            }
        ), 503


@bp.patch("/subscriptions/<subscription_id>")
def update_subscription(subscription_id: str):
    payload = request.get_json(silent=True) or {}
    status = _clean_text(payload.get("status"), 40)
    email = _clean_text(payload.get("email"), 255)
    phone = _clean_text(payload.get("phone"), 80)

    if status not in STATUSES:
        return jsonify({"ok": False, "error": "invalid_status", "allowed_statuses": sorted(STATUSES)}), 400
    if not email and not phone:
        return jsonify({"ok": False, "error": "contact_required"}), 400

    try:
        query = get_supabase().table("relocation_watchlist_subscriptions").update({"status": status}).eq("id", subscription_id)
        if email:
            query = query.eq("email", email)
        if phone:
            query = query.eq("phone", phone)
        response = query.execute()
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "subscription_not_found"}), 404
        return jsonify({"ok": True, "subscription": updated})
    except Exception as exc:
        return jsonify({"ok": False, "error": "watchlist_update_failed", "details": str(exc)}), 500
