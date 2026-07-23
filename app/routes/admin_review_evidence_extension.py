from __future__ import annotations

from typing import Any, Dict, List, Tuple

from flask import jsonify

from app.routes import admin_review_queue
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
    alert_rows = [
        row
        for row in _safe_rows("relocation_source_change_alerts", limit=120)
        if row.get("status") in {"open", "in_review"}
    ]

    evidence_items = [_evidence_item(row) for row in evidence_rows]
    source_items = [_source_alert_item(row) for row in alert_rows]
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    sections.insert(
        0,
        {
            "kind": "source_review_alert",
            "label": "Official-source review and change alerts",
            "ok": True,
            "error": None,
            "count": len(source_items),
            "items": source_items,
        },
    )
    sections.insert(
        1,
        {
            "kind": "evidence_pack",
            "label": "Evidence packs needing review",
            "ok": True,
            "error": None,
            "count": len(evidence_items),
            "items": evidence_items,
        },
    )
    payload["sections"] = sections

    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    counts["source_review_alert"] = len(source_items)
    counts["evidence_pack"] = len(evidence_items)
    payload["counts"] = counts

    queue_items = payload.get("queue_items") if isinstance(payload.get("queue_items"), list) else []
    previous_total = int(payload.get("total_open_items") or len(queue_items))
    queue_items.extend(source_items)
    queue_items.extend(evidence_items)
    queue_items.sort(key=lambda item: (int(item.get("score") or 0), item.get("created_at") or ""), reverse=True)
    payload["queue_items"] = queue_items[:100]
    payload["total_open_items"] = previous_total + len(source_items) + len(evidence_items)

    next_actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    for action in [
        "Review official-source change alerts before approving affected route versions or reports.",
        "Review high-risk or incomplete evidence packs without requesting raw documents through the general queue.",
    ]:
        if action not in next_actions:
            next_actions.insert(0, action)
    payload["next_actions"] = next_actions
    return jsonify(payload)
