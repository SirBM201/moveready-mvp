from __future__ import annotations

import html
import json
import logging
import os
import smtplib
import socket
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any, Dict, List, Optional, Tuple


MAILTRAP_PROVIDER_NAMES = {"mailtrap", "mailtrap_api", "mailtrap-api"}
MAILTRAP_SANDBOX_PROVIDER_NAMES = {"mailtrap_sandbox", "mailtrap-sandbox", "mailtrap_sandbox_api"}
logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name, "1" if default else "0").lower()
    return value in {"1", "true", "yes", "y", "on"}


def _public_failure(status: str, detail: Optional[str] = None, *, provider: Optional[str] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {"ok": False, "status": status}
    if provider:
        result["provider"] = provider
    if detail:
        result["detail"] = detail[:500]
    return result


def _sender_parts() -> Tuple[str, str]:
    raw = _env("EMAIL_OTP_FROM") or _env("EMAIL_FROM")
    name, email = parseaddr(raw)
    if not email and "@" in raw:
        email = raw.strip()
    return (name.strip() or _env("EMAIL_OTP_APP_NAME", "MoveReady"), email.strip())


def _reply_to_parts() -> Tuple[str, str]:
    raw = _env("EMAIL_OTP_REPLY_TO") or _env("EMAIL_REPLY_TO")
    name, email = parseaddr(raw)
    if not email and "@" in raw:
        email = raw.strip()
    return (name.strip(), email.strip())


def _mailtrap_token() -> str:
    return _env("MAILTRAP_API_TOKEN") or _env("MAILTRAP_API_KEY")


def _mailtrap_sandbox_token() -> str:
    return _env("MAILTRAP_SANDBOX_API_TOKEN") or _mailtrap_token()


def _mailtrap_sandbox_endpoint() -> str:
    explicit = _env("MAILTRAP_SANDBOX_API_URL")
    if explicit:
        return explicit
    account_id = _env("MAILTRAP_ACCOUNT_ID")
    inbox_id = _env("MAILTRAP_INBOX_ID")
    if account_id and inbox_id:
        return f"https://sandbox.api.mailtrap.io/api/send/{account_id}/{inbox_id}"
    return ""


def email_delivery_status() -> Dict[str, Any]:
    enabled = _env_bool("EMAIL_OTP_DELIVERY_ENABLED", False)
    provider = (_env("EMAIL_OTP_PROVIDER", "none") or "none").lower()
    missing: List[str] = []
    configured = False

    if provider in MAILTRAP_PROVIDER_NAMES:
        if not _mailtrap_token():
            missing.append("MAILTRAP_API_TOKEN")
        _sender_name, sender_email = _sender_parts()
        if not sender_email:
            missing.append("EMAIL_OTP_FROM")
        configured = not missing
        provider = "mailtrap"
    elif provider in MAILTRAP_SANDBOX_PROVIDER_NAMES:
        if not _mailtrap_sandbox_token():
            missing.append("MAILTRAP_SANDBOX_API_TOKEN")
        if not _mailtrap_sandbox_endpoint():
            missing.append("MAILTRAP_SANDBOX_API_URL_OR_ACCOUNT_AND_INBOX_ID")
        _sender_name, sender_email = _sender_parts()
        if not sender_email:
            missing.append("EMAIL_OTP_FROM")
        configured = not missing
        provider = "mailtrap_sandbox"
    elif provider == "resend":
        if not _env("RESEND_API_KEY"):
            missing.append("RESEND_API_KEY")
        _sender_name, sender_email = _sender_parts()
        if not sender_email:
            missing.append("EMAIL_OTP_FROM")
        configured = not missing
    elif provider == "smtp":
        if not _env("SMTP_HOST"):
            missing.append("SMTP_HOST")
        _sender_name, sender_email = _sender_parts()
        if not sender_email and not _env("SMTP_USERNAME"):
            missing.append("EMAIL_OTP_FROM")
        username = _env("SMTP_USERNAME")
        password = _env("SMTP_PASSWORD")
        if bool(username) != bool(password):
            missing.append("SMTP_USERNAME_AND_PASSWORD_MUST_BE_SET_TOGETHER")
        try:
            port = int(_env("SMTP_PORT", "587") or "587")
            if port <= 0 or port > 65535:
                raise ValueError("invalid port")
        except Exception:
            missing.append("SMTP_PORT")
        configured = not missing
    else:
        missing.append("EMAIL_OTP_PROVIDER")

    _sender_name, sender_email = _sender_parts()
    return {
        "enabled": enabled,
        "provider": provider,
        "configured": bool(enabled and configured),
        "provider_configuration_present": configured,
        "missing_configuration": missing,
        "sender_configured": bool(sender_email or _env("SMTP_USERNAME")),
        "login_url_configured": bool(_env("EMAIL_OTP_LOGIN_URL")),
        "transport": "https_api" if provider in {"mailtrap", "mailtrap_sandbox", "resend"} else ("smtp" if provider == "smtp" else "none"),
    }


def _message_body(code: str, expires_minutes: int) -> str:
    app_name = _env("EMAIL_OTP_APP_NAME", "MoveReady")
    login_url = _env("EMAIL_OTP_LOGIN_URL")
    lines = [f"Your {app_name} sign-in code is {code}.", "", f"This code expires in {expires_minutes} minutes.", "", "MoveReady staff will never ask you to send this code by email, chat, or phone.", "If you did not request this code, you can safely ignore this email."]
    if login_url:
        lines.extend(["", f"Login page: {login_url}"])
    return "\n".join(lines)


def _message_html(code: str, expires_minutes: int) -> str:
    app_name = html.escape(_env("EMAIL_OTP_APP_NAME", "MoveReady"))
    login_url = _env("EMAIL_OTP_LOGIN_URL")
    safe_login_url = html.escape(login_url, quote=True)
    safe_code = html.escape(code)
    login_link = f'<p><a href="{safe_login_url}">Open {app_name} login</a></p>' if login_url else ""
    return f"""<div style="font-family:Arial,sans-serif;line-height:1.55;color:#111827;max-width:560px"><p>Your {app_name} sign-in code is:</p><p style="font-size:28px;font-weight:700;letter-spacing:4px">{safe_code}</p><p>This code expires in {expires_minutes} minutes.</p>{login_link}<p style="color:#6b7280">MoveReady staff will never ask you to send this code by email, chat, or phone.</p><p style="color:#6b7280">If you did not request this code, you can safely ignore this email.</p></div>"""


def _subject() -> str:
    return f"Your {_env('EMAIL_OTP_APP_NAME', 'MoveReady')} sign-in code"


def _http_email_payload(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    from_name, from_email = _sender_parts()
    payload: Dict[str, Any] = {"from": {"email": from_email, "name": from_name or "MoveReady"}, "to": [{"email": to_email}], "subject": _subject(), "text": _message_body(code, expires_minutes), "html": _message_html(code, expires_minutes), "category": "authentication"}
    reply_name, reply_email = _reply_to_parts()
    if reply_email:
        payload["reply_to"] = {"email": reply_email, **({"name": reply_name} if reply_name else {})}
    return payload


def _post_mailtrap(endpoint: str, token: str, payload: Dict[str, Any], provider: str) -> Dict[str, Any]:
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "MoveReady-OTP/1.0"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed: Dict[str, Any] = {}
            try:
                candidate = json.loads(body) if body else {}
                parsed = candidate if isinstance(candidate, dict) else {}
            except Exception:
                pass
            return {"ok": True, "status": "sent", "provider": provider, "message_id": parsed.get("message_ids") or parsed.get("message_id") or parsed.get("id")}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return _public_failure(f"{provider}_http_{exc.code}", body or str(exc), provider=provider)
    except Exception as exc:
        return _public_failure(f"{provider}_send_failed", str(exc), provider=provider)


def _send_mailtrap(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    token = _mailtrap_token()
    _from_name, from_email = _sender_parts()
    if not token or not from_email:
        return _public_failure("mailtrap_not_configured", "MAILTRAP_API_TOKEN and EMAIL_OTP_FROM are required.", provider="mailtrap")
    return _post_mailtrap(_env("MAILTRAP_API_URL", "https://send.api.mailtrap.io/api/send"), token, _http_email_payload(to_email, code, expires_minutes), "mailtrap")


def _send_mailtrap_sandbox(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    token = _mailtrap_sandbox_token()
    endpoint = _mailtrap_sandbox_endpoint()
    _from_name, from_email = _sender_parts()
    if not token or not endpoint or not from_email:
        return _public_failure("mailtrap_sandbox_not_configured", "Sandbox API token, endpoint (or account/inbox IDs), and EMAIL_OTP_FROM are required.", provider="mailtrap_sandbox")
    return _post_mailtrap(endpoint, token, _http_email_payload(to_email, code, expires_minutes), "mailtrap_sandbox")


def _send_resend(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    api_key = _env("RESEND_API_KEY")
    from_name, from_email = _sender_parts()
    if not api_key or not from_email:
        return _public_failure("resend_not_configured", "RESEND_API_KEY and EMAIL_OTP_FROM are required.", provider="resend")
    payload: Dict[str, Any] = {"from": f"{from_name} <{from_email}>" if from_name else from_email, "to": [to_email], "subject": _subject(), "text": _message_body(code, expires_minutes), "html": _message_html(code, expires_minutes)}
    request = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(payload).encode("utf-8"), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": "MoveReady-OTP/1.0"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                message_id = (json.loads(body) or {}).get("id")
            except Exception:
                message_id = None
            return {"ok": True, "status": "sent", "provider": "resend", "message_id": message_id}
    except Exception as exc:
        return _public_failure("resend_send_failed", str(exc), provider="resend")


def _smtp_timeout_seconds() -> float:
    try:
        return min(max(float(_env("SMTP_TIMEOUT_SECONDS", "8") or "8"), 2.0), 20.0)
    except Exception:
        return 8.0


def _smtp_failure(phase: str, exc: Exception) -> Dict[str, Any]:
    detail = f"SMTP {phase} failed: {exc.__class__.__name__}: {exc}"
    logger.warning("MoveReady OTP %s", detail)
    return _public_failure("smtp_send_failed", detail, provider="smtp")


def _send_smtp(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    host = _env("SMTP_HOST")
    try:
        port = int(_env("SMTP_PORT", "587") or "587")
    except Exception:
        return _public_failure("smtp_not_configured", "SMTP_PORT must be a valid integer.", provider="smtp")
    username, password = _env("SMTP_USERNAME"), _env("SMTP_PASSWORD")
    from_name, from_email = _sender_parts()
    if not from_email:
        from_email = username
    use_ssl = _env_bool("SMTP_USE_SSL", False)
    use_tls = _env_bool("SMTP_USE_TLS", not use_ssl)
    timeout = _smtp_timeout_seconds()
    if not host or not from_email:
        return _public_failure("smtp_not_configured", "SMTP_HOST and EMAIL_OTP_FROM are required.", provider="smtp")
    if bool(username) != bool(password):
        return _public_failure("smtp_not_configured", "SMTP_USERNAME and SMTP_PASSWORD must be set together.", provider="smtp")
    message = EmailMessage(); message["Subject"] = _subject(); message["From"] = f"{from_name} <{from_email}>" if from_name else from_email; message["To"] = to_email; message.set_content(_message_body(code, expires_minutes)); message.add_alternative(_message_html(code, expires_minutes), subtype="html")
    server: Optional[smtplib.SMTP] = None; phase = "connect"
    try:
        server = smtplib.SMTP_SSL(host=host, port=port, timeout=timeout, context=ssl.create_default_context()) if use_ssl else smtplib.SMTP(host=host, port=port, timeout=timeout)
        if server.sock is not None: server.sock.settimeout(timeout)
        if use_tls and not use_ssl:
            phase = "starttls"; server.ehlo(); server.starttls(context=ssl.create_default_context()); server.sock.settimeout(timeout) if server.sock else None; server.ehlo()
        if username and password:
            phase = "authenticate"; server.login(username, password)
        phase = "send"; server.send_message(message); phase = "quit"
        try: server.quit()
        except Exception: server.close()
        server = None
        return {"ok": True, "status": "sent", "provider": "smtp"}
    except Exception as exc:
        return _smtp_failure(phase, exc)
    finally:
        if server is not None:
            try: server.close()
            except Exception: pass


def deliver_login_code(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    readiness = email_delivery_status()
    if not readiness["enabled"]:
        return {"ok": False, "status": "email_delivery_not_enabled", "provider": readiness["provider"]}
    if not readiness["configured"]:
        return _public_failure("email_delivery_not_configured", ", ".join(readiness["missing_configuration"]), provider=readiness["provider"])
    provider = readiness["provider"]
    if provider == "mailtrap": return _send_mailtrap(to_email, code, expires_minutes)
    if provider == "mailtrap_sandbox": return _send_mailtrap_sandbox(to_email, code, expires_minutes)
    if provider == "resend": return _send_resend(to_email, code, expires_minutes)
    if provider == "smtp": return _send_smtp(to_email, code, expires_minutes)
    return _public_failure("email_provider_not_configured", "Set EMAIL_OTP_PROVIDER to mailtrap, mailtrap_sandbox, resend, or smtp.", provider=provider)
