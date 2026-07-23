from __future__ import annotations

from typing import Any, Dict, List, Tuple

from flask import jsonify

from app.routes import admin_review_queue, application_cases
from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access


def _unwrap(result: Any) -> Tuple[Any, int]:
    if isinstance(result, tuple):
        response = result[0]
        status = int(result[1]) if len(result) > 1 else 200
        return response, status
    return result, 200


def _safe_rows(table: str, limit: int = 100) -> List[Dict[str, Any]]:
    try:
        response = (
            get_supabase()
            .table(table)
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def _evidence_item(row: Dict[str, Any]) -> Dict[str, Any]:
    missing = row.get("missing_items") if isinstance(row.get("missing_items"), list) else []
    warnings = row.get("warnings") if isinstance(row.get("warnings"), list) else []
    score = 55
    if row.get("risk_level") == "critical":
        score += 45
    elif row.get("risk_level") == "high":
        score += 30
    if row.get("status") == "review_required":
        score += 20
    age_hours = admin_review_queue._age_hours(row)
    return {
        "kind": "evidence_pack",
        "id": row.get("id"),
        "title": row.get("pack_ref") or "Evidence pack",
        "status": row.get("status") or "unknown",
        "priority": row.get("risk_level") or "medium",
        "risk_level": row.get("risk_level"),
        "full_name": None,
        "email": row.get("email"),
        "target_country": row.get("target_country"),
        "route_category": row.get("route_category"),
        "created_at": row.get("created_at"),
        "age_hours": age_hours,
        "score": score + min(age_hours or 0, 240) // 24,
        "summary": (
            f"Completeness {row.get('completeness_score') or 0}%. "
            f"Missing: {', '.join(str(item.get('label') or item.get('key') or 'item') for item in missing[:8]) or 'none recorded'}. "
            f"Warnings: {' '.join(str(item) for item in warnings[:4]) or 'none recorded'}."
        ),
        "detail_href": "/admin#evidence-review",
        "record": row,
    }


def _source_alert_item(row: Dict[str, Any]) -> Dict[str, Any]:
    severity = str(row.get("severity") or "medium")
    score = 50 + ({"low": 0, "medium": 10, "high": 25, "critical": 40}.get(severity, 10))
    age_hours = admin_review_queue._age_hours(row)
    return {
        "kind": "source_review_alert",
        "id": row.get("id"),
        "title": str(row.get("summary") or row.get("alert_type") or "Source review alert"),
        "status": row.get("status") or "open",
        "priority": severity,
        "risk_level": severity,
        "created_at": row.get("created_at"),
        "age_hours": age_hours,
        "score": score + min(age_hours or 0, 240) // 24,
        "summary": str(row.get("summary") or "Official source review or content-change attention is required."),
        "detail_href": "/admin#source-governance",
        "record": row,
    }


def _application_case_needs_attention(row: Dict[str, Any]) -> bool:
    public = application_cases._public_case(row)
    hours = public.get("hours_until_deadline")
    stage = str(public.get("application_stage") or "")
    source_status = str(public.get("source_status") or "")
    return bool(
        public.get("status") == "attention_required"
        or public.get("risk_level") in {"high", "critical"}
        or stage in {"additional_documents_requested", "refused"}
        or (hours is not None and float(hours) <= 336)
        or source_status in {"stale", "unavailable"}
        or (
            source_status == "review_required"
            and stage in {
                "appointment_booked",
                "submitted",
                "biometrics_completed",
                "interview_scheduled",
                "additional_documents_requested",
                "decision_pending",
            }
        )
    )


def _application_case_item(row: Dict[str, Any]) -> Dict[str, Any]:
    public = application_cases._public_case(row)
    risk = str(public.get("risk_level") or "medium")
    score = 60 + ({"low": 0, "medium": 10, "high": 30, "critical": 50}.get(risk, 10))
    stage = str(public.get("application_stage") or "")
    hours = public.get("hours_until_deadline")
    if stage == "additional_documents_requested":
        score += 30
    elif stage == "refused":
        score += 40
    if hours is not None:
        if float(hours) < 0:
            score += 40
        elif float(hours) <= 72:
            score += 30
        elif float(hours) <= 336:
            score += 15
    age_hours = admin_review_queue._age_hours(row)
    warnings = public.get("warnings") if isinstance(public.get("warnings"), list) else []
    return {
        "kind": "application_case",
        "id": row.get("id"),
        "title": public.get("case_title") or public.get("case_ref") or "Application case",
        "status": public.get("status") or "unknown",
        "priority": risk,
        "risk_level": risk,
        "email": row.get("email"),
        "target_country": public.get("target_country"),
        "route_category": public.get("route_category"),
        "created_at": row.get("created_at"),
        "age_hours": age_hours,
        "score": score + min(age_hours or 0, 240) // 24,
        "summary": (
            f"Stage: {str(public.get('application_stage') or 'unknown').replace('_', ' ')}. "
            f"Source: {str(public.get('source_status') or 'unknown').replace('_', ' ')}. "
            f"Deadline: {public.get('next_deadline_at') or 'not recorded'}. "
            f"Warnings: {' '.join(str(item) for item in warnings[:4]) or 'none recorded'}."
        ),
        "detail_href": "/admin#application-cases",
        "record": row,
    }


def _application_alert_item(row: Dict[str, Any]) -> Dict[str, Any]:
    severity = str(row.get("severity") or "medium")
    age_hours = admin_review_queue._age_hours(row)
    score = 65 + ({"low": 0, "medium": 10, "high": 30, "critical": 50}.get(severity, 10))
    return {
        "kind": "application_alert",
        "id": row.get("id"),
        "title": row.get("title") or row.get("alert_type") or "Application alert",
        "status": row.get("status") or "open",
        "priority": severity,
        "risk_level": severity,
        "email": row.get("email"),
        "created_at": row.get("created_at"),
        "age_hours": age_hours,
        "score": score + min(age_hours or 0, 240) // 24,
        "summary": str(row.get("summary") or "Application deadline, source, payment, or decision attention is required."),
        "detail_href": "/admin/application-alerts",
        "record": row,
    }


def _privacy_request_item(row: Dict[str, Any]) -> Dict[str, Any]:
    request_type = str(row.get("request_type") or "other")
    priority = str(row.get("priority") or "normal")
    age_hours = admin_review_queue._age_hours(row)
    score = 70 + ({"low": 0, "normal": 10, "high": 30, "urgent": 50}.get(priority, 10))
    if request_type in {"account_deletion", "consent_withdrawal"}:
        score += 25
    return {
        "kind": "privacy_request",
        "id": row.get("id"),
        "title": row.get("request_ref") or "Privacy request",
        "status": row.get("status") or "received",
        "priority": priority,
        "risk_level": "high" if request_type in {"account_deletion", "consent_withdrawal"} else "medium",
        "email": row.get("email"),
        "created_at": row.get("created_at"),
        "age_hours": age_hours,
        "score": score + min(age_hours or 0, 240) // 24,
        "summary": (
            f"Type: {request_type.replace('_', ' ')}. "
            f"Scope: {row.get('requested_scope') or 'not specified'}. "
            f"Identity reverification: {'required' if row.get('identity_reverification_required') else 'not required'}."
        ),
        "detail_href": "/admin#privacy-requests",
        "record": row,
    }


@require_admin_access
def review_queue_with_evidence():
    original_result = admin_review_queue.review_queue()
    response, status = _unwrap(original_result)
    if status != 200:
        return original_result

    try:
        payload = response.get_json()
    except Exception:
        return original_result
    if not isinstance(payload, dict) or not payload.get("ok"):
        return original_result

    evidence_rows = [
        row
        for row in _safe_rows("relocation_evidence_packs", limit=120)
        if row.get("status") in {"draft", "review_required", "stale"}
        or row.get("risk_level") in {"high", "critical"}
    ]
    source_rows = [
        row
        for row in _safe_rows("relocation_source_change_alerts", limit=120)
        if row.get("status") in {"open", "in_review"}
    ]
    application_rows = [
        row
        for row in _safe_rows("relocation_application_cases", limit=180)
        if row.get("status") != "archived" and _application_case_needs_attention(row)
    ]
    application_alert_rows = [
        row
        for row in _safe_rows("relocation_application_case_alerts", limit=180)
        if row.get("status") == "open" and row.get("severity") in {"high", "critical"}
    ]
    privacy_rows = [
        row
        for row in _safe_rows("relocation_privacy_requests", limit=180)
        if row.get("status") in {"received", "identity_verification_required", "reviewing", "in_progress"}
    ]

    source_items = [_source_alert_item(row) for row in source_rows]
    application_items = [_application_case_item(row) for row in application_rows]
    application_alert_items = [_application_alert_item(row) for row in application_alert_rows]
    privacy_items = [_privacy_request_item(row) for row in privacy_rows]
    evidence_items = [_evidence_item(row) for row in evidence_rows]

    additions = [
        ("privacy_request", "Privacy, access, correction, restriction, consent, and deletion requests", privacy_items),
        ("application_alert", "High and critical application alerts", application_alert_items),
        ("source_review_alert", "Official-source review and change alerts", source_items),
        ("application_case", "Application cases needing attention", application_items),
        ("evidence_pack", "Evidence packs needing review", evidence_items),
    ]

    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    for index, (kind, label, items) in enumerate(additions):
        sections.insert(index, {
            "kind": kind,
            "label": label,
            "ok": True,
            "error": None,
            "count": len(items),
            "items": items,
        })
    payload["sections"] = sections

    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    for kind, _label, items in additions:
        counts[kind] = len(items)
    payload["counts"] = counts

    queue_items = payload.get("queue_items") if isinstance(payload.get("queue_items"), list) else []
    previous_total = int(payload.get("total_open_items") or len(queue_items))
    for _kind, _label, items in additions:
        queue_items.extend(items)
    queue_items.sort(key=lambda item: (int(item.get("score") or 0), item.get("created_at") or ""), reverse=True)
    payload["queue_items"] = queue_items[:150]
    payload["total_open_items"] = previous_total + sum(len(items) for _kind, _label, items in additions)

    next_actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    for action in [
        "Review privacy and deletion requests with identity reverification, scope, retention, backup, provider-copy, billing, dispute, and completion evidence controls.",
        "Review high and critical application alerts before their deadline, source, payment, or decision risk escalates.",
        "Review application cases with overdue or near deadlines, additional-document requests, refusals, stale sources, or high risk.",
        "Review official-source change alerts before approving affected route versions or reports.",
        "Review high-risk or incomplete evidence packs without requesting raw documents through the general queue.",
    ]:
        if action not in next_actions:
            next_actions.insert(0, action)
    payload["next_actions"] = next_actions
    return jsonify(payload)
