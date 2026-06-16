from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return jsonify({"ok": True, "status": "healthy", "service": "moveready-api"})


@bp.get("/api/health")
def api_health():
    return jsonify({"ok": True, "status": "healthy", "service": "moveready-api"})
