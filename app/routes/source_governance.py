from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access


public_bp = Blueprint("source_governance_public", __name__)
admin_bp = Blueprint("source_governance_admin", __name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _text(value: Any, limit: int = 500) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


def _int(value: Any, default: int, minimum: int = 1, maximum: int = 3650) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return min(max(parsed, minimum), maximum)


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


def _is_due(value: Any, now: Optional[datetime] = None) -> bool:
    parsed = _parse_datetime(value)
    return bool(parsed and parsed <= (now or _now()))


def _age_days(value: Any) -> Optional[int]:
    parsed = _parse_datetime(value)
    if not parsed:
        return None
    return max(0, int((_now() - parsed).total_seconds() // 86400))


def _load_sources(limit: int = 1500) -> List[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_trusted_sources")
        .select("*")
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return response.data or []


def _load_route_versions(limit: int = 1500) -> List[Dict[str, Any]]:
    response = (
        get_supabase()
        .table("relocation_route_versions")
        .select("id,route_id,version_label,status,risk_level,source_confidence,verified_at,review_due_at,approved_at,updated_at")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def _public_source_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source_type": row.get("source_type"),
        "reliability_level": row.get("reliability_level"),
        "status": row.get("status"),
        "last_checked_age_days": _age_days(row.get("last_checked_at")),
        "review_due": _is_due(row.get("next_review_due_at")),
    }


def _source_review_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "country_id": row.get("country_id"),
        "source_name": row.get("source_name"),
        "source_url": row.get("source_url"),
        "source_type": row.get("source_type"),
        "owner_organization": row.get("owner_organization"),
        "reliability_level": row.get("reliability_level"),
        "status": row.get("status"),
        "review_frequency_days": row.get("review_frequency_days"),
        "last_checked_at": row.get("last_checked_at"),
        "last_checked_age_days": _age_days(row.get("last_checked_at")),
        "next_review_due_at": row.get("next_review_due_at"),
        "review_due": _is_due(row.get("next_review_due_at")),
        "notes": row.get("notes"),
        "updated_at": row.get("updated_at"),
    }


def _route_review_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "route_id": row.get("route_id"),
        "version_label": row.get("version_label"),
        "status": row.get("status"),
        "risk_level": row.get("risk_level"),
        "source_confidence": row.get("source_confidence"),
        "verified_at": row.get("verified_at"),
        "verified_age_days": _age_days(row.get("verified_at")),
        "review_due_at": row.get("review_due_at"),
        "review_due": _is_due(row.get("review_due_at")),
        "approved_at": row.get("approved_at"),
        "updated_at": row.get("updated_at"),
    }


def _existing_open_due_alert(source_id: str) -> Optional[Dict[str, Any]]:
    try:
        response = (
            get_supabase()
            .table("relocation_source_change_alerts")
            .select("id,status,alert_type,created_at")
            .eq("source_id", source_id)
            .eq("alert_type", "review_due")
            .in_("status", ["open", "in_review"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return (response.data or [None])[0]
    except Exception:
        return None


def _create_review_due_alert(source: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    if _existing_open_due_alert(str(source.get("id"))):
        return False, "existing_open_alert"
    try:
        get_supabase().table("relocation_source_change_alerts").insert(
            {
                "source_id": source.get("id"),
                "alert_type": "review_due",
                "severity": "high" if source.get("reliability_level") == "low" or source.get("status") == "needs_review" else "medium",
                "status": "open",
                "summary": f"Source review is due: {source.get('source_name') or source.get('source_url')}",
            }
        ).execute()
        return True, None
    except Exception as exc:
        return False, str(exc)


@public_bp.get("/summary")
def public_summary():
    try:
        sources = _load_sources()
        routes = _load_route_versions()
        active_sources = [item for item in sources if item.get("status") in {"active", "watching", "needs_review"}]
        due_sources = [item for item in active_sources if _is_due(item.get("next_review_due_at"))]
        unchecked_sources = [item for item in active_sources if not item.get("last_checked_at")]
        needs_review_sources = [item for item in active_sources if item.get("status") == "needs_review"]
        due_routes = [item for item in routes if item.get("status") == "active" and _is_due(item.get("review_due_at"))]
        low_confidence_routes = [item for item in routes if item.get("status") == "active" and item.get("source_confidence") == "low"]
        source_types: Dict[str, int] = {}
        reliability: Dict[str, int] = {}
        for item in active_sources:
            source_type = str(item.get("source_type") or "other")
            source_types[source_type] = source_types.get(source_type, 0) + 1
            level = str(item.get("reliability_level") or "unknown")
            reliability[level] = reliability.get(level, 0) + 1

        if due_sources or due_routes or needs_review_sources:
            status = "review_attention_required"
        elif unchecked_sources:
            status = "initial_review_incomplete"
        else:
            status = "source_governance_current"

        return jsonify(
            {
                "ok": True,
                "service": "MoveReady source freshness",
                "status": status,
                "generated_at": _now_iso(),
                "counts": {
                    "active_sources": len(active_sources),
                    "sources_due_for_review": len(due_sources),
                    "sources_never_checked": len(unchecked_sources),
                    "sources_marked_needs_review": len(needs_review_sources),
                    "active_route_versions": len([item for item in routes if item.get("status") == "active"]),
                    "route_versions_due_for_review": len(due_routes),
                    "low_confidence_active_routes": len(low_confidence_routes),
                },
                "source_types": source_types,
                "reliability_levels": reliability,
                "sample_health": [_public_source_summary(item) for item in active_sources[:12]],
                "public_note": "This page reports review freshness and source confidence. It does not claim that every rule is unchanged or that a route will be approved.",
                "admin_review_endpoint": "/api/admin/source-governance/queue",
            }
        )
    except Exception:
        return jsonify(
            {
                "ok": True,
                "service": "MoveReady source freshness",
                "status": "source_health_temporarily_unavailable",
                "generated_at": _now_iso(),
                "counts": {},
                "source_types": {},
                "reliability_levels": {},
                "sample_health": [],
                "public_note": "Source-health data is temporarily unavailable. Route guidance should remain fail closed where current official verification is missing.",
            }
        )


@admin_bp.get("/source-governance/queue")
@require_admin_access
def review_queue():
    try:
        limit = max(1, min(int(request.args.get("limit") or 200), 500))
    except (TypeError, ValueError):
        limit = 200
    try:
        sources = _load_sources(limit=1500)
        routes = _load_route_versions(limit=1500)
        source_rows = [_source_review_row(item) for item in sources if item.get("status") != "retired"]
        route_rows = [_route_review_row(item) for item in routes if item.get("status") in {"active", "pending_review"}]
        source_rows.sort(key=lambda item: (not bool(item.get("review_due")), item.get("next_review_due_at") or "9999"))
        route_rows.sort(key=lambda item: (not bool(item.get("review_due")), item.get("review_due_at") or "9999"))
        due_sources = [item for item in source_rows if item.get("review_due") or item.get("status") == "needs_review" or not item.get("last_checked_at")]
        due_routes = [item for item in route_rows if item.get("review_due") or item.get("source_confidence") == "low"]
        return jsonify(
            {
                "ok": True,
                "generated_at": _now_iso(),
                "source_count": len(source_rows),
                "route_version_count": len(route_rows),
                "due_source_count": len(due_sources),
                "due_route_count": len(due_routes),
                "sources": source_rows[:limit],
                "route_versions": route_rows[:limit],
                "priority_sources": due_sources[:limit],
                "priority_route_versions": due_routes[:limit],
                "next_actions": [
                    "Open the official source and confirm whether the rule, fee, deadline, eligibility, or process changed.",
                    "Record a snapshot title and content hash or review note before marking the source checked.",
                    "Update affected route versions and reports before resolving a content-change alert.",
                    "Retire unavailable or replaced sources rather than silently keeping stale guidance active.",
                ],
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": "source_governance_queue_unavailable", "details": str(exc)}), 503


@admin_bp.post("/source-governance/scan-due")
@require_admin_access
def scan_due():
    try:
        sources = _load_sources()
    except Exception as exc:
        return jsonify({"ok": False, "error": "source_scan_unavailable", "details": str(exc)}), 503

    due_sources = [
        item
        for item in sources
        if item.get("status") in {"active", "watching", "needs_review"}
        and (not item.get("last_checked_at") or _is_due(item.get("next_review_due_at")) or item.get("status") == "needs_review")
    ]
    created = 0
    skipped = 0
    errors: List[Dict[str, Any]] = []
    for source in due_sources:
        ok, error = _create_review_due_alert(source)
        if ok:
            created += 1
        elif error == "existing_open_alert":
            skipped += 1
        else:
            errors.append({"source_id": source.get("id"), "source_name": source.get("source_name"), "error": error})

    return jsonify(
        {
            "ok": not errors,
            "status": "completed" if not errors else "completed_with_errors",
            "generated_at": _now_iso(),
            "due_source_count": len(due_sources),
            "alerts_created": created,
            "existing_alerts_skipped": skipped,
            "errors": errors,
        }
    ), (200 if not errors else 207)


@admin_bp.post("/source-governance/sources/<source_id>/mark-checked")
@require_admin_access
def mark_checked(source_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        source_response = (
            get_supabase()
            .table("relocation_trusted_sources")
            .select("*")
            .eq("id", source_id)
            .maybe_single()
            .execute()
        )
        source = source_response.data
        if not source:
            return jsonify({"ok": False, "error": "source_not_found"}), 404

        checked_at = _now()
        frequency = _int(payload.get("review_frequency_days"), int(source.get("review_frequency_days") or 30), 1, 3650)
        next_due = checked_at + timedelta(days=frequency)
        source_status = _text(payload.get("status"), 40) or "active"
        if source_status not in {"active", "watching", "needs_review", "retired"}:
            return jsonify({"ok": False, "error": "invalid_source_status"}), 400

        updates = {
            "status": source_status,
            "review_frequency_days": frequency,
            "last_checked_at": checked_at.isoformat(),
            "next_review_due_at": next_due.isoformat(),
            "notes": _text(payload.get("notes"), 2000) if "notes" in payload else source.get("notes"),
        }
        updated_response = (
            get_supabase()
            .table("relocation_trusted_sources")
            .update(updates)
            .eq("id", source_id)
            .execute()
        )
        updated = (updated_response.data or [source | updates])[0]

        snapshot_created = False
        change_alert_created = False
        snapshot_title = _text(payload.get("snapshot_title"), 300)
        content_hash = _text(payload.get("content_hash"), 200)
        extracted_text = _text(payload.get("extracted_text"), 12000)
        structured_payload = payload.get("structured_payload") if isinstance(payload.get("structured_payload"), dict) else {}

        if snapshot_title or content_hash or extracted_text or structured_payload:
            previous_response = (
                get_supabase()
                .table("relocation_source_snapshots")
                .select("id,content_hash,captured_at,status")
                .eq("source_id", source_id)
                .order("captured_at", desc=True)
                .limit(1)
                .execute()
            )
            previous = (previous_response.data or [None])[0]
            changed = bool(content_hash and previous and previous.get("content_hash") and previous.get("content_hash") != content_hash)
            snapshot_response = get_supabase().table("relocation_source_snapshots").insert(
                {
                    "source_id": source_id,
                    "captured_at": checked_at.isoformat(),
                    "content_hash": content_hash,
                    "snapshot_title": snapshot_title or f"Manual review {checked_at.date().isoformat()}",
                    "extracted_text": extracted_text,
                    "structured_payload": structured_payload,
                    "status": "changed" if changed else "reviewed",
                    "reviewed_at": checked_at.isoformat(),
                    "reviewed_by": _text(payload.get("reviewed_by"), 180) or "MoveReady admin",
                    "notes": _text(payload.get("snapshot_notes"), 1600),
                }
            ).execute()
            snapshot = (snapshot_response.data or [None])[0]
            snapshot_created = bool(snapshot)
            if changed and snapshot:
                get_supabase().table("relocation_source_change_alerts").insert(
                    {
                        "source_id": source_id,
                        "old_snapshot_id": previous.get("id"),
                        "new_snapshot_id": snapshot.get("id"),
                        "alert_type": "content_changed",
                        "severity": "high",
                        "status": "open",
                        "summary": f"Content hash changed for {source.get('source_name') or source.get('source_url')}. Review affected route versions and reports.",
                    }
                ).execute()
                change_alert_created = True

        try:
            get_supabase().table("relocation_source_change_alerts").update(
                {"status": "resolved", "resolved_at": checked_at.isoformat()}
            ).eq("source_id", source_id).eq("alert_type", "review_due").in_("status", ["open", "in_review"]).execute()
        except Exception:
            pass

        return jsonify(
            {
                "ok": True,
                "source": _source_review_row(updated),
                "snapshot_created": snapshot_created,
                "content_change_alert_created": change_alert_created,
                "safety_note": "Marking a source checked does not automatically update affected route facts, reports, deadlines, or user alerts. Review and approve those records separately.",
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": "source_mark_checked_failed", "details": str(exc)}), 503
