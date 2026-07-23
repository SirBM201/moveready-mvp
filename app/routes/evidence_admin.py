from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from app.routes.evidence_workflow import _public_document, _public_pack
from app.services.supabase_client import get_supabase
from app.utils.admin_auth import require_admin_access


bp = Blueprint("evidence_admin", __name__)
PACK_STATUSES = {"draft", "review_required", "ready", "submitted", "stale", "archived"}


def _text(value: Any, limit: int = 500) -> Optional[str]:
    cleaned = str(value or "").strip()
    return cleaned[:limit] or None


@bp.get("/evidence-packs")
@require_admin_access
def evidence_packs():
    status = _text(request.args.get("status"), 40)
    risk_level = _text(request.args.get("risk_level"), 40)
    email = _text(request.args.get("email"), 255)
    try:
        limit = max(1, min(int(request.args.get("limit") or 100), 250))
    except (TypeError, ValueError):
        limit = 100
    try:
        query = (
            get_supabase()
            .table("relocation_evidence_packs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if risk_level:
            query = query.eq("risk_level", risk_level)
        if email:
            query = query.eq("email", email.lower())
        response = query.execute()
        rows = [
            {
                **_public_pack(row),
                "email": row.get("email"),
                "source_page": row.get("source_page"),
                "metadata": row.get("metadata") or {},
            }
            for row in (response.data or [])
        ]
        return jsonify({"ok": True, "pack_count": len(rows), "evidence_packs": rows})
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "error": "admin_evidence_packs_unavailable",
                "details": str(exc),
                "hint": "Apply supabase/migrations/027_evidence_inventory_and_packs.sql.",
            }
        ), 503


@bp.patch("/evidence-packs/<pack_id>")
@require_admin_access
def update_evidence_pack(pack_id: str):
    payload = request.get_json(silent=True) or {}
    status = _text(payload.get("status"), 40)
    if status not in PACK_STATUSES:
        return jsonify({"ok": False, "error": "invalid_evidence_pack_status", "allowed": sorted(PACK_STATUSES)}), 400
    updates: Dict[str, Any] = {"status": status}
    if "official_source_notes" in payload:
        updates["official_source_notes"] = _text(payload.get("official_source_notes"), 2000)
    try:
        response = (
            get_supabase()
            .table("relocation_evidence_packs")
            .update(updates)
            .eq("id", pack_id)
            .execute()
        )
        updated = (response.data or [None])[0]
        if not updated:
            return jsonify({"ok": False, "error": "evidence_pack_not_found"}), 404
        return jsonify({"ok": True, "evidence_pack": {**_public_pack(updated), "email": updated.get("email")}})
    except Exception as exc:
        return jsonify({"ok": False, "error": "evidence_pack_update_failed", "details": str(exc)}), 503


@bp.get("/document-inventory/expiring")
@require_admin_access
def expiring_documents():
    try:
        days = max(1, min(int(request.args.get("days") or 180), 730))
        limit = max(1, min(int(request.args.get("limit") or 150), 300))
    except (TypeError, ValueError):
        days = 180
        limit = 150
    today = date.today()
    cutoff = today + timedelta(days=days)
    try:
        response = (
            get_supabase()
            .table("relocation_user_document_inventory")
            .select("*")
            .neq("status", "archived")
            .not_.is_("expiry_date", "null")
            .lte("expiry_date", cutoff.isoformat())
            .order("expiry_date", desc=False)
            .limit(limit)
            .execute()
        )
        rows = []
        for row in response.data or []:
            public = _public_document(row)
            rows.append(
                {
                    **public,
                    "email": row.get("email"),
                    "expired": bool(public.get("days_until_expiry") is not None and int(public.get("days_until_expiry")) < 0),
                }
            )
        return jsonify(
            {
                "ok": True,
                "window_days": days,
                "document_count": len(rows),
                "documents": rows,
                "privacy_note": "This endpoint returns metadata only. It does not expose a raw file or full document number.",
            }
        )
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "error": "admin_expiring_documents_unavailable",
                "details": str(exc),
                "hint": "Apply supabase/migrations/027_evidence_inventory_and_packs.sql.",
            }
        ), 503
