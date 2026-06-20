from __future__ import annotations

from typing import Optional

from flask import request

ACCOUNT_WRITE_PREFIXES = (
    "/api/profiles",
    "/api/saved-routes",
    "/api/watchlist/subscriptions",
    "/api/timeline",
    "/api/platform/service-interest",
    "/api/relocation/reports",
)


def _is_account_write_request() -> bool:
    if request.method not in {"POST", "PATCH"}:
        return False
    path = request.path.rstrip("/")
    return any(path.startswith(prefix) for prefix in ACCOUNT_WRITE_PREFIXES)


def _verified_email() -> Optional[str]:
    try:
        from app.routes import account_auth

        token = account_auth._extract_session_token()
        if not token:
            return None
        session, _error = account_auth._load_active_session(token)
        if not session:
            return None
        email = str(session.get("email") or "").strip().lower()
        return email or None
    except Exception:
        return None


def attach_verified_session_email_to_json() -> None:
    """Attach verified account email to account-owned writes.

    The MVP still supports contact-based email/phone lookup. When a valid session
    token is present, user-owned writes should be tied to the verified account
    email instead of trusting a manually typed email field.
    """
    if not _is_account_write_request():
        return None

    email = _verified_email()
    if not email:
        return None

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None

    payload["email"] = email
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["identity_source"] = "verified_session"
    metadata["verified_session_email"] = email
    payload["metadata"] = metadata
    return None
