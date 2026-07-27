from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request

from app.core.config import (
    AUTH_MAX_ACTIVE_SESSIONS_PER_EMAIL,
    AUTH_MAX_CODE_ATTEMPTS,
    AUTH_OTP_DEV_MODE,
    AUTH_OTP_EXPIRES_MINUTES,
    AUTH_OTP_MAX_REQUESTS_PER_EMAIL_WINDOW,
    AUTH_OTP_MAX_REQUESTS_PER_IP_WINDOW,
    AUTH_OTP_RECENT_SCAN_LIMIT,
    AUTH_OTP_REQUEST_COOLDOWN_SECONDS,
    AUTH_OTP_REQUEST_WINDOW_MINUTES,
    AUTH_SESSION_DAYS,
    ENV_MODE,
    FLASK_ENV,
    SECRET_KEY,
)
from app.services.email_delivery import deliver_login_code, email_delivery_status
from app.services.supabase_client import get_supabase

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_RE = re.compile(r"^\d{6}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


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


def _client_ip() -> str:
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    return (forwarded or request.remote_addr or "unknown")[:120]


def _metadata() -> Dict[str, Any]:
    return {
        "user_agent": _clean_text(request.headers.get("User-Agent"), 500),
        "remote_addr": _client_ip(),
    }


def _dev_code_allowed() -> bool:
    return bool(
        AUTH_OTP_DEV_MODE
        and ENV_MODE.lower() == "development"
        and FLASK_ENV.lower() == "development"
    )


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


def _window_retry_after(rows: List[Dict[str, Any]], now: datetime) -> int:
    parsed = [_parse_datetime(row.get("created_at")) for row in rows]
    created = [item for item in parsed if item]
    if not created:
        return AUTH_OTP_REQUEST_WINDOW_MINUTES * 60
    oldest = min(created)
    elapsed = max(0, int((now - oldest).total_seconds()))
    return max(1, AUTH_OTP_REQUEST_WINDOW_MINUTES * 60 - elapsed)


def _request_rate_limit(email: str) -> Optional[Dict[str, Any]]:
    now = _now()
    since = now - timedelta(minutes=AUTH_OTP_REQUEST_WINDOW_MINUTES)
    client_ip = _client_ip()

    email_response = (
        get_supabase()
        .table("relocation_auth_login_codes")
        .select("id,email,status,attempts,created_at,metadata")
        .eq("email", email)
        .gte("created_at", _iso(since))
        .order("created_at", desc=True)
        .limit(AUTH_OTP_RECENT_SCAN_LIMIT)
        .execute()
    )
    email_rows = email_response.data or []

    if email_rows:
        latest_at = _parse_datetime(email_rows[0].get("created_at"))
        if latest_at:
            elapsed = int((now - latest_at).total_seconds())
            if elapsed < AUTH_OTP_REQUEST_COOLDOWN_SECONDS:
                return {
                    "error": "otp_request_cooldown_active",
                    "retry_after_seconds": max(1, AUTH_OTP_REQUEST_COOLDOWN_SECONDS - elapsed),
                }

    if len(email_rows) >= AUTH_OTP_MAX_REQUESTS_PER_EMAIL_WINDOW:
        return {
            "error": "otp_email_request_limit_reached",
            "retry_after_seconds": _window_retry_after(email_rows, now),
        }

    if client_ip != "unknown":
        ip_response = (
            get_supabase()
            .table("relocation_auth_login_codes")
            .select("id,created_at,metadata")
            .gte("created_at", _iso(since))
            .order("created_at", desc=True)
            .limit(AUTH_OTP_RECENT_SCAN_LIMIT)
            .execute()
        )
        ip_rows = [
            row
            for row in (ip_response.data or [])
            if str((row.get("metadata") or {}).get("remote_addr") or "") == client_ip
        ]
        if len(ip_rows) >= AUTH_OTP_MAX_REQUESTS_PER_IP_WINDOW:
            return {
                "error": "otp_ip_request_limit_reached",
                "retry_after_seconds": _window_retry_after(ip_rows, now),
            }

    return None


def _expire_pending_codes(email: str) -> None:
    try:
        (
            get_supabase()
            .table("relocation_auth_login_codes")
            .update({"status": "expired"})
            .eq("email", email)
            .eq("status", "pending")
            .execute()
        )
    except Exception:
        pass


def _trim_active_sessions(email: str) -> None:
    try:
        response = (
            get_supabase()
            .table("relocation_user_sessions")
            .select("id,created_at")
            .eq("email", email)
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        for row in (response.data or [])[AUTH_MAX_ACTIVE_SESSIONS_PER_EMAIL:]:
            get_supabase().table("relocation_user_sessions").update({"status": "revoked"}).eq("id", row.get("id")).execute()
    except Exception:
        pass


@bp.get("/health")
def health():
    delivery = email_delivery_status()
    return jsonify(
        {
            "ok": True,
            "service": "MoveReady account auth",
            "otp_expires_minutes": AUTH_OTP_EXPIRES_MINUTES,
            "session_days": AUTH_SESSION_DAYS,
            "email_delivery_enabled": delivery["enabled"],
            "email_delivery_configured": delivery["configured"],
            "email_delivery_provider": delivery["provider"],
            "email_delivery_missing_configuration": delivery["missing_configuration"],
            "dev_code_allowed": _dev_code_allowed(),
            "request_limits": {
                "cooldown_seconds": AUTH_OTP_REQUEST_COOLDOWN_SECONDS,
                "window_minutes": AUTH_OTP_REQUEST_WINDOW_MINUTES,
                "maximum_per_email_window": AUTH_OTP_MAX_REQUESTS_PER_EMAIL_WINDOW,
                "maximum_per_ip_window": AUTH_OTP_MAX_REQUESTS_PER_IP_WINDOW,
            },
        }
    )


@bp.post("/request-code")
def request_code():
    payload = request.get_json(silent=True) or {}
    email = _clean_email(payload.get("email"))
    source_page = _clean_text(payload.get("source_page"), 240)

    if not email:
        return jsonify({"ok": False, "error": "valid_email_required"}), 400

    try:
        limited = _request_rate_limit(email)
    except Exception as exc:
        return jsonify({"ok": False, "error": "otp_rate_limit_check_unavailable", "details": str(exc)[:600]}), 503
    if limited:
        return jsonify({"ok": False, **limited}), 429

    _expire_pending_codes(email)

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
        return jsonify(
            {
                "ok": False,
                "stored": False,
                "error": "otp_storage_unavailable",
                "details": str(exc)[:600],
                "hint": "Run supabase/migrations/019_account_login_otp.sql and redeploy.",
            }
        ), 503

    delivery = deliver_login_code(email, code, AUTH_OTP_EXPIRES_MINUTES)
    delivery_ok = bool(delivery.get("ok"))
    dev_allowed = _dev_code_allowed()

    if not delivery_ok and not dev_allowed:
        try:
            get_supabase().table("relocation_auth_login_codes").update({"status": "expired"}).eq("id", stored.get("id") if stored else "").execute()
        except Exception:
            pass
        return jsonify(
            {
                "ok": False,
                "stored": True,
                "error": "otp_delivery_failed",
                "delivery_status": delivery.get("status") or "email_delivery_failed",
                "delivery_provider": delivery.get("provider"),
                "details": delivery.get("detail"),
                "hint": "Confirm EMAIL_OTP_PROVIDER, sender domain, and SMTP credentials, then request a new code.",
            }
        ), 503

    result: Dict[str, Any] = {
        "ok": True,
        "stored": True,
        "request_id": stored.get("id") if stored else None,
        "email": email,
        "expires_at": _iso(expires_at),
        "delivery_status": delivery.get("status") or ("sent" if delivery_ok else "development_code_only"),
        "delivery_provider": delivery.get("provider"),
    }
    if dev_allowed:
        result["dev_code"] = code
    return jsonify(result), 200 if delivery_ok else 202


@bp.post("/verify-code")
def verify_code():
    payload = request.get_json(silent=True) or {}
    email = _clean_email(payload.get("email"))
    code = _clean_text(payload.get("code"), 20)

    if not email or not code:
        return jsonify({"ok": False, "error": "email_and_code_required"}), 400
    if not CODE_RE.fullmatch(code):
        return jsonify({"ok": False, "error": "six_digit_code_required"}), 400

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
        return jsonify({"ok": False, "error": "otp_lookup_unavailable", "details": str(exc)[:600]}), 503

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
        return jsonify(
            {
                "ok": False,
                "error": "invalid_code",
                "attempts_remaining": max(AUTH_MAX_CODE_ATTEMPTS - attempts, 0),
            }
        ), 400

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
        _trim_active_sessions(email)
        return jsonify({"ok": True, "session_token": token, "session": _public_session(session or session_row)})
    except Exception as exc:
        return jsonify({"ok": False, "error": "session_create_failed", "details": str(exc)[:600]}), 503


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
        return jsonify({"ok": False, "error": "logout_failed", "details": str(exc)[:600]}), 503
    return jsonify({"ok": True, "logged_out": True})
