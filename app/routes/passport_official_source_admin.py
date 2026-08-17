from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.passport_official_source_reviews import (
    expire_due_reviews,
    list_review_candidates,
    record_review,
    review_history,
)
from app.utils.admin_auth import require_admin_access

bp = Blueprint("passport_official_source_admin", __name__)


@bp.get("/passport-official-sources/reviews")
@require_admin_access
def review_queue():
    try:
        rows = list_review_candidates(request.args.get("status", ""), request.args.get("limit", 100))
        return jsonify({"ok": True, "review_candidates": rows, "count": len(rows)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "passport_official_source_review_queue_failed", "detail": str(exc)[:300]}), 503


@bp.get("/passport-official-sources/<mapping_id>/reviews")
@require_admin_access
def mapping_review_history(mapping_id: str):
    try:
        rows = review_history(mapping_id, request.args.get("limit", 100))
        return jsonify({"ok": True, "mapping_id": mapping_id, "reviews": rows, "count": len(rows)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "passport_official_source_review_history_failed", "detail": str(exc)[:300]}), 503


@bp.post("/passport-official-sources/<mapping_id>/review")
@require_admin_access
def submit_mapping_review(mapping_id: str):
    try:
        mapping = record_review(mapping_id, request.get_json(silent=True) or {})
        return jsonify({"ok": True, "mapping": mapping})
    except ValueError as exc:
        return jsonify({"ok": False, "error": "invalid_review_request", "detail": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": "passport_official_source_review_failed", "detail": str(exc)[:300]}), 409


@bp.post("/passport-official-sources/reviews/expire")
@require_admin_access
def expire_reviews():
    try:
        changed = expire_due_reviews()
        return jsonify({"ok": True, "expired_count": changed})
    except Exception as exc:
        return jsonify({"ok": False, "error": "passport_official_source_expiry_failed", "detail": str(exc)[:300]}), 503
