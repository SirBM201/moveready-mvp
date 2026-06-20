from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access

bp = Blueprint("admin_review_queue", __name__)

HIGH_PRIORITIES = {"high", "critical", "urgent"}
HIGH_RISKS = {"high", "medium"}


def _bounded_limit(value: Any, default: int = 25, maximum: int = 50) -> int:
    try:
        return max(1, min(int(value), maximum))
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _safe_number(value: Any, fallback: int = 0) -> int:
    try:
        if value in (None, ""):
            return fallback
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _created_at(row: Dict[str, Any]) -> str:
    return _safe_text(row.get("created_at") or row.get("generated_at") or row.get("updated_at"))


def _age_hours(row: Dict[str, Any]) -> Optional[int]:
    value = _created_at(row)
    if not value:
        return None
    try:
        created = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return max(0, int((datetime.now(timezone.utc) - created).total_seconds() // 3600))
    except Exception:
        return None


def _priority_score(kind: str, row: Dict[str, Any]) -> int:
    score = 0
    status = _safe_text(row.get("status") or row.get("availability_status")).lower()
    priority = _safe_text(row.get("priority")).lower()
    risk = _safe_text(row.get("risk_level")).lower()

    if status in {"new", "open", "generated"}:
        score += 20
    if priority in HIGH_PRIORITIES:
        score += 25
    if risk == "high":
        score += 25
    elif risk == "medium":
        score += 10
    if kind in {"service_request", "partner_application"}:
        score += 15
    age = _age_hours(row)
    if age is not None:
        score += min(age // 24, 20)
    return score


def _safe_select(table: str, *, limit: int, order_by: str = "created_at", desc: bool = True) -> Dict[str, Any]:
    try:
        response = (
            get_supabase()
            .table(table)
            .select("*")
            .order(order_by, desc=desc)
            .limit(limit)
            .execute()
        )
        return {"ok": True, "rows": response.data or [], "error": None}
    except Exception as exc:
        return {"ok": False, "rows": [], "error": str(exc)}


def _summary(row: Dict[str, Any], payload: Dict[str, Any]) -> Optional[str]:
    for field in ("notes", "message", "summary", "description", "internal_notes"):
        value = _safe_text(row.get(field))
        if value:
            return value[:600]
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    if sections:
        first = sections[0] if isinstance(sections[0], dict) else {}
        value = _safe_text(first.get("section_content") or first.get("body"))
        if value:
            return value[:600]
    return None


def _detail_href(kind: str, row: Dict[str, Any], payload: Dict[str, Any]) -> str:
    if kind == "generated_report":
        ref = _safe_text(row.get("report_ref") or payload.get("report_ref"))
        return f"/report-detail?ref={quote(ref)}" if ref else "/my-reports"
    if kind == "service_request":
        return "/service-requests"
    if kind == "saved_route":
        return "/saved-routes"
    if kind == "watchlist":
        return "/watchlist"
    if kind == "timeline_event":
        return "/timeline"
    if kind == "user_profile":
        return "/dashboard#profile-dashboard"
    if kind == "partner_application":
        return "/admin#partner-applications"
    if kind == "review_task":
        return "/admin#review-queue"
    return "/admin"


def _compact(kind: str, row: Dict[str, Any]) -> Dict[str, Any]:
    payload = row.get("report_payload") if isinstance(row.get("report_payload"), dict) else {}
    input_payload = row.get("input_payload") if isinstance(row.get("input_payload"), dict) else {}

    title = (
        row.get("request_title")
        or row.get("service_label")
        or row.get("service_slug")
        or row.get("report_title")
        or row.get("report_ref")
        or row.get("saved_title")
        or row.get("watch_title")
        or row.get("event_title")
        or row.get("full_name")
        or row.get("company_name")
        or row.get("source_name")
        or kind.replace("_", " ").title()
    )

    full_name = row.get("full_name") or input_payload.get("full_name") or input_payload.get("name")
    email = row.get("email") or input_payload.get("email")
    phone = row.get("phone") or input_payload.get("phone")
    target_country = row.get("target_country") or input_payload.get("target_country") or input_payload.get("targetCountry")
    route_category = row.get("route_category") or row.get("main_goal") or input_payload.get("route_category") or input_payload.get("main_goal")
    report_ref = row.get("report_ref") or payload.get("report_ref")

    return {
        "kind": kind,
        "id": row.get("id"),
        "title": _safe_text(title, kind.replace("_", " ").title()),
        "status": row.get("status") or row.get("availability_status") or "unknown",
        "priority": row.get("priority") or row.get("risk_level") or payload.get("risk_level") or "medium",
        "risk_level": row.get("risk_level") or payload.get("risk_level"),
        "report_ref": report_ref,
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "target_country": target_country,
        "route_category": route_category,
        "country_code": row.get("country_code") or input_payload.get("country_code"),
        "source_page": row.get("source_page") or input_payload.get("source_page"),
        "created_at": _created_at(row),
        "age_hours": _age_hours(row),
        "score": _priority_score(kind, row),
        "summary": _summary(row, payload),
        "detail_href": _detail_href(kind, row, payload),
        "record": row,
    }


def _section(kind: str, label: str, table: str, *, limit: int, predicate=None, order_by: str = "created_at", desc: bool = True) -> Dict[str, Any]:
    result = _safe_select(table, limit=limit, order_by=order_by, desc=desc)
    rows: List[Dict[str, Any]] = result["rows"]
    if predicate:
        rows = [row for row in rows if predicate(row)]
    items = [_compact(kind, row) for row in rows]
    return {
        "kind": kind,
        "label": label,
        "ok": result["ok"],
        "error": result["error"],
        "count": len(items),
        "items": items,
    }


def _status_in(*statuses: str):
    allowed = {status.lower() for status in statuses}

    def predicate(row: Dict[str, Any]) -> bool:
        return _safe_text(row.get("status") or row.get("availability_status")).lower() in allowed

    return predicate


def _report_needs_review(row: Dict[str, Any]) -> bool:
    status = _safe_text(row.get("status")).lower()
    risk = _safe_text(row.get("risk_level")).lower()
    return status in {"generated", "stale"} or risk in HIGH_RISKS


def _timeline_needs_attention(row: Dict[str, Any]) -> bool:
    status = _safe_text(row.get("status")).lower()
    priority = _safe_text(row.get("priority")).lower()
    return status in {"pending", "in_progress", "missed"} or priority in {"high", "critical"}


@bp.get("/review-queue")
@require_admin_access
def review_queue():
    limit = _bounded_limit(request.args.get("limit"), default=25, maximum=50)

    sections = [
        _section("review_task", "Manual review tasks", "relocation_admin_review_tasks", limit=limit, predicate=_status_in("open", "in_progress")),
        _section("service_request", "Service requests", "relocation_service_interest_requests", limit=limit, predicate=_status_in("new", "reviewing")),
        _section("generated_report", "Generated reports", "relocation_generated_reports", limit=limit, predicate=_report_needs_review),
        _section("partner_application", "Partner applications", "relocation_partner_applications", limit=limit, predicate=_status_in("new", "screening", "waitlist")),
        _section("user_profile", "User profiles", "relocation_user_profiles", limit=limit, predicate=_status_in("new", "reviewing")),
        _section("saved_route", "Saved routes", "relocation_saved_routes", limit=limit, predicate=_status_in("active")),
        _section("watchlist", "Watchlist alerts", "relocation_watchlist_subscriptions", limit=limit, predicate=_status_in("active")),
        _section("timeline_event", "Timeline events", "relocation_timeline_events", limit=limit, predicate=_timeline_needs_attention, order_by="created_at", desc=True),
    ]

    queue_items = []
    for section in sections:
        queue_items.extend(section["items"])
    queue_items.sort(key=lambda item: (_safe_number(item.get("score")), item.get("created_at") or ""), reverse=True)

    errors = {section["kind"]: section["error"] for section in sections if not section["ok"]}
    counts = {section["kind"]: section["count"] for section in sections}

    return jsonify({
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "total_open_items": len(queue_items),
        "sections": sections,
        "queue_items": queue_items[: max(limit, 10)],
        "errors": errors,
        "next_actions": [
            "Review service requests before provider handoff.",
            "Check high-risk reports before sharing or selling expert review.",
            "Screen partner applications before assigning user records.",
            "Keep watchlist and timeline records private until delivery channels are approved.",
        ],
    })
