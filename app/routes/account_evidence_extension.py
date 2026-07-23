from __future__ import annotations

from typing import Any, Dict, Tuple

from flask import jsonify

from app.routes import account
from app.routes.evidence_workflow import _public_document, _public_pack
from app.services.supabase_client import get_supabase


def _unwrap(result: Any) -> Tuple[Any, int]:
    if isinstance(result, tuple):
        response = result[0]
        status = int(result[1]) if len(result) > 1 else 200
        return response, status
    return result, 200


def _safe_documents(email: str, limit: int = 25) -> Dict[str, Any]:
    try:
        response = (
            get_supabase()
            .table("relocation_user_document_inventory")
            .select("*")
            .eq("email", email)
            .neq("status", "archived")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = [_public_document(row) for row in (response.data or [])]
        return {"ok": True, "rows": rows, "count": len(rows)}
    except Exception as exc:
        return {"ok": False, "rows": [], "count": 0, "error": str(exc)}


def _safe_packs(email: str, limit: int = 15) -> Dict[str, Any]:
    try:
        response = (
            get_supabase()
            .table("relocation_evidence_packs")
            .select("*")
            .eq("email", email)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = [_public_pack(row) for row in (response.data or [])]
        return {"ok": True, "rows": rows, "count": len(rows)}
    except Exception as exc:
        return {"ok": False, "rows": [], "count": 0, "error": str(exc)}


def account_summary_with_evidence():
    original_result = account.account_summary()
    response, status = _unwrap(original_result)
    if status != 200:
        return original_result

    try:
        payload = response.get_json()
    except Exception:
        return original_result
    if not isinstance(payload, dict) or not payload.get("ok"):
        return original_result

    email = str((payload.get("session") or {}).get("email") or "").strip().lower()
    if not email:
        return original_result

    documents = _safe_documents(email)
    packs = _safe_packs(email)
    sections = payload.get("sections") if isinstance(payload.get("sections"), dict) else {}
    sections["document_inventory"] = documents
    sections["evidence_packs"] = packs
    payload["sections"] = sections

    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    counts["document_inventory"] = int(documents.get("count") or 0)
    counts["evidence_packs"] = int(packs.get("count") or 0)
    payload["counts"] = counts

    next_actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    evidence_action = "Open Evidence Center to track document metadata, expiry, route evidence packs, and refusal-repair tasks."
    if evidence_action not in next_actions:
        next_actions.insert(5, evidence_action)
    payload["next_actions"] = next_actions
    payload["evidence_storage_boundary"] = "Account Center exposes document metadata and pack summaries only. Raw files and full document numbers are not stored by the Evidence Center."
    return jsonify(payload)
