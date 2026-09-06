from __future__ import annotations

from flask import Blueprint, jsonify

from app.routes import account_auth
from app.services.billing_entitlements import account_billing_state, has_entitlement

bp = Blueprint("billing_access", __name__)


def _authenticated_email():
    token = account_auth._auth._extract_session_token()
    if not token:
        return None, "session_token_required"
    session, error = account_auth._auth._load_active_session(token)
    if not session:
        return None, error or "invalid_session"
    email = str(session.get("email") or "").strip().lower()
    return (email or None), (None if email else "session_email_missing")


@bp.get("/access")
def billing_access():
    email, error = _authenticated_email()
    if not email:
        return jsonify({"ok": False, "error": error}), 401
    try:
        return jsonify({"ok": True, **account_billing_state(email)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "billing_access_unavailable", "details": str(exc)}), 503


@bp.get("/access/<feature_code>")
def feature_access(feature_code: str):
    email, error = _authenticated_email()
    if not email:
        return jsonify({"ok": False, "error": error}), 401
    try:
        allowed = has_entitlement(email, feature_code)
        return jsonify({"ok": True, "feature_code": feature_code, "allowed": allowed})
    except Exception as exc:
        return jsonify({"ok": False, "error": "entitlement_check_unavailable", "details": str(exc)}), 503
