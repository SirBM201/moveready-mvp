from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.core.config import (
    AUTH_MAX_CODE_ATTEMPTS,
    AUTH_OTP_DEV_MODE,
    AUTH_OTP_EXPIRES_MINUTES,
    AUTH_SESSION_DAYS,
    EMAIL_OTP_DELIVERY_ENABLED,
    ENV_MODE,
    FLASK_ENV,
    SECRET_KEY,
)
from app.services.supabase_client import get_supabase

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _clean_text(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _clean_email(value: Any) -> Optional[str]:
    email = _clean_text(value, 255)
    if not email:
        return None
    email = email.lower()
    if not EMAIL_RE.match(email):
        return None
    return email


def _hash_value(value: str) -> str:
    secret = (SECRET_KEY or "").encode("utf-8")
    return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _code_hash(email: str, code: str) -> str:
    return _hash_value(f"otp:{email}:{code}")


def _token_hash(token: str) -> str:
    return _hash_value(f"session:{token}")


def _metadata() -> Dict[str, Any]:
    return {
        "user_agent": request.headers.get("User-Agent"),
        "remote_addr": request.headers.get("X-Forwarded-For") or request.remote_addr,
    }


def _dev_code_allowed() -> bool:
    return bool(AUTH_OTP_DEV_MODE or ENV_MODE == "development" or FLASK_ENV == "development")


def _extract_session_token() -> Optional[str]:
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return _clean_text(request.headers.get("X-MoveReady-Session"), 500)


def _load_active_session(token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    token_hash = _token_hash(token)
    try:
        response = (
            get_supabase()
            .table("relocation_user_sessions")
            .select("*")
            .eq("token_hash", token_hash)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        session = (response.data or [None])[0]
        if not session:
            return None, "session_not_found"
        expires_at = _parse_datetime(session.get("expires_at"))
        if not expires_at or expires_at <= _now():
            get_supabase().table("relocation_user_sessions").update({"status": "expired"}).eq("id", session.get("id")).execute()
            return None, "session_expired"
        return session, None
    except Exception:
        return None, "session_lookup_unavailable"


def _public_session(session: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": session.get("id"),
        "email": session.get("email"),
        "status": session.get("status"),
        "created_at": session.get("created_at"),
        "expires_at": session.get("expires_at"),
        "last_seen_at": session.get("last_seen_at"),
    }


@bp.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "MoveReady account auth",
        "otp_expires_minutes": AUTH_OTP_EXPIRES_MINUTES,
        "session_days": AUTH_SESSION_DAYS,
        "email_delivery_enabled": EMAIL_OTP_DELIVERY_ENABLED,
        "dev_code_allowed": _dev_code_allowed(),
    })


@bp.post("/request-code")
def request_code():
    payload = request.get_json(silent=True) or {}
    email = _clean_email(payload.get("email"))
    source_page = _clean_text(payload.get("source_page"), 240)

    if not email:
        return jsonify({"ok": False, "error": "valid_email_required"}), 400

    code = f"{secrets.randbelow(1000000):06d}"
    expires_at = _now() + timedelta(minutes=AUTH_OTP_EXPIRES_MINUTES)
    row = {
        "email": email,
        "code_hash": _code_hash(email, code),
        "status": "pending",
        "attempts": 0,
        "expires_at": _iso(expires_at),
        "source_page": source_page,
        "metadata": _metadata(),
    }

    try:
        response = get_supabase().table("relocation_auth_login_codes").insert(row).execute()
        stored = (response.data or [None])[0]
    except Exception as exc:
        return jsonify({
            "ok": False,
            "stored": False,
            "error": "otp_storage_unavailable",
            "details": str(exc),
            "hint": "Run supabase/migrations/019_account_login_otp.sql and redeploy.",
        }), 503

    result: Dict[str, Any] = {
        "ok": True,
        "stored": True,
        "request_id": stored.get("id") if stored else None,
        "email": email,
        "expires_at": _iso(expires_at),
        "delivery_status": "queued" if EMAIL_OTP_DELIVERY_ENABLED else "email_delivery_not_configured",
    }
    if _dev_code_allowed():
        result["dev_code"] = code
    return jsonify(result), 202 if not EMAIL_OTP_DELIVERY_ENABLED else 200


@bp.post("/verify-code")
def verify_code():
    payload = request.get_json(silent=True) or {}
    email = _clean_email(payload.get("email"))
    code = _clean_text(payload.get("code"), 20)

    if not email or not code:
        return jsonify({"ok": False, "error": "email_and_code_required"}), 400

    try:
        response = (
            get_supabase()
            .table("relocation_auth_login_codes")
            .select("*")
            .eq("email", email)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        login_code = (response.data or [None])[0]
    except Exception as exc:
        return jsonify({"ok": False, "error": "otp_lookup_unavailable", "details": str(exc)}), 503

    if not login_code:
        return jsonify({"ok": False, "error": "code_not_found"}), 404

    code_id = login_code.get("id")
    expires_at = _parse_datetime(login_code.get("expires_at"))
    if not expires_at or expires_at <= _now():
        get_supabase().table("relocation_auth_login_codes").update({"status": "expired"}).eq("id", code_id).execute()
        return jsonify({"ok": False, "error": "code_expired"}), 400

    expected_hash = login_code.get("code_hash") or ""
    attempts = int(login_code.get("attempts") or 0)
    if not hmac.compare_digest(expected_hash, _code_hash(email, code)):
        attempts += 1
        status = "locked" if attempts >= AUTH_MAX_CODE_ATTEMPTS else "pending"
        get_supabase().table("relocation_auth_login_codes").update({"attempts": attempts, "status": status}).eq("id", code_id).execute()
        return jsonify({"ok": False, "error": "invalid_code", "attempts_remaining": max(AUTH_MAX_CODE_ATTEMPTS - attempts, 0)}), 400

    token = secrets.token_urlsafe(48)
    session_expires_at = _now() + timedelta(days=AUTH_SESSION_DAYS)
    session_row = {
        "email": email,
        "token_hash": _token_hash(token),
        "status": "active",
        "expires_at": _iso(session_expires_at),
        "last_seen_at": _iso(_now()),
        "metadata": _metadata(),
    }

    try:
        get_supabase().table("relocation_auth_login_codes").update({"status": "used", "used_at": _iso(_now())}).eq("id", code_id).execute()
        session_response = get_supabase().table("relocation_user_sessions").insert(session_row).execute()
        session = (session_response.data or [None])[0]
        return jsonify({"ok": True, "session_token": token, "session": _public_session(session or session_row)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "session_create_failed", "details": str(exc)}), 503


@bp.get("/me")
def me():
    token = _extract_session_token()
    if not token:
        return jsonify({"ok": False, "error": "session_token_required"}), 401
    session, error = _load_active_session(token)
    if not session:
        return jsonify({"ok": False, "error": error or "invalid_session"}), 401
    try:
        get_supabase().table("relocation_user_sessions").update({"last_seen_at": _iso(_now())}).eq("id", session.get("id")).execute()
    except Exception:
        pass
    return jsonify({"ok": True, "session": _public_session(session)})


@bp.post("/logout")
def logout():
    token = _extract_session_token()
    if not token:
        return jsonify({"ok": True, "logged_out": False})
    session, _error = _load_active_session(token)
    if not session:
        return jsonify({"ok": True, "logged_out": False})
    try:
        get_supabase().table("relocation_user_sessions").update({"status": "revoked"}).eq("id", session.get("id")).execute()
    except Exception as exc:
        return jsonify({"ok": False, "error": "logout_failed", "details": str(exc)}), 503
    return jsonify({"ok": True, "logged_out": True})
