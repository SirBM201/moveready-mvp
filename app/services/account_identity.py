from __future__ import annotations

from typing import Optional, Tuple


def get_verified_session_email() -> Optional[str]:
    """Return the email from a valid MoveReady session token, if present.

    Public endpoints may still support contact-based lookup for MVP users.
    When a valid session token is present, this helper lets the endpoint prefer
    the verified account email and ignore user-supplied email values.
    """
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


def choose_contact_email(payload_email: Optional[str]) -> Tuple[Optional[str], str, Optional[str]]:
    """Choose verified-session email when available, otherwise fallback email.

    Returns `(email, identity_source, verified_email)`.
    """
    verified_email = get_verified_session_email()
    if verified_email:
        return verified_email, "verified_session", verified_email
    cleaned = str(payload_email or "").strip().lower() or None
    return cleaned, "contact_lookup", None
