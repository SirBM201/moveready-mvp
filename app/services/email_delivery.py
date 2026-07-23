from __future__ import annotations

import html
import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any, Dict, List, Optional


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
        result["detail"] = detail[:240]
    return result


def email_delivery_status() -> Dict[str, Any]:
    enabled = _env_bool("EMAIL_OTP_DELIVERY_ENABLED", False)
    provider = (_env("EMAIL_OTP_PROVIDER", "none") or "none").lower()
    missing: List[str] = []
    configured = False

    if provider == "resend":
        if not _env("RESEND_API_KEY"):
            missing.append("RESEND_API_KEY")
        if not (_env("EMAIL_OTP_FROM") or _env("EMAIL_FROM")):
            missing.append("EMAIL_OTP_FROM")
        configured = not missing
    elif provider == "smtp":
        if not _env("SMTP_HOST"):
            missing.append("SMTP_HOST")
        if not (_env("EMAIL_OTP_FROM") or _env("EMAIL_FROM") or _env("SMTP_USERNAME")):
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

    return {
        "enabled": enabled,
        "provider": provider,
        "configured": bool(enabled and configured),
        "provider_configuration_present": configured,
        "missing_configuration": missing,
        "sender_configured": bool(_env("EMAIL_OTP_FROM") or _env("EMAIL_FROM") or _env("SMTP_USERNAME")),
        "login_url_configured": bool(_env("EMAIL_OTP_LOGIN_URL")),
    }


def _message_body(code: str, expires_minutes: int) -> str:
    app_name = _env("EMAIL_OTP_APP_NAME", "MoveReady")
    login_url = _env("EMAIL_OTP_LOGIN_URL")
    lines = [
        f"Your {app_name} sign-in code is {code}.",
        "",
        f"This code expires in {expires_minutes} minutes.",
        "",
        "MoveReady staff will never ask you to send this code by email, chat, or phone.",
        "If you did not request this code, you can safely ignore this email.",
    ]
    if login_url:
        lines.extend(["", f"Login page: {login_url}"])
    return "\n".join(lines)


def _message_html(code: str, expires_minutes: int) -> str:
    app_name = html.escape(_env("EMAIL_OTP_APP_NAME", "MoveReady"))
    login_url = _env("EMAIL_OTP_LOGIN_URL")
    safe_login_url = html.escape(login_url, quote=True)
    safe_code = html.escape(code)
    login_link = f'<p><a href="{safe_login_url}">Open {app_name} login</a></p>' if login_url else ""
    return f"""
    <div style="font-family:Arial,sans-serif;line-height:1.55;color:#111827;max-width:560px">
      <p>Your {app_name} sign-in code is:</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:4px">{safe_code}</p>
      <p>This code expires in {expires_minutes} minutes.</p>
      {login_link}
      <p style="color:#6b7280">MoveReady staff will never ask you to send this code by email, chat, or phone.</p>
      <p style="color:#6b7280">If you did not request this code, you can safely ignore this email.</p>
    </div>
    """.strip()


def _subject() -> str:
    app_name = _env("EMAIL_OTP_APP_NAME", "MoveReady")
    return f"Your {app_name} sign-in code"


def _send_resend(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    api_key = _env("RESEND_API_KEY")
    from_email = _env("EMAIL_OTP_FROM") or _env("EMAIL_FROM")
    if not api_key or not from_email:
        return _public_failure("resend_not_configured", "RESEND_API_KEY and EMAIL_OTP_FROM are required.", provider="resend")

    payload: Dict[str, Any] = {
        "from": from_email,
        "to": [to_email],
        "subject": _subject(),
        "text": _message_body(code, expires_minutes),
        "html": _message_html(code, expires_minutes),
    }
    reply_to = _env("EMAIL_OTP_REPLY_TO") or _env("EMAIL_REPLY_TO")
    if reply_to:
        payload["reply_to"] = reply_to

    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "MoveReady-OTP/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
            message_id = None
            try:
                message_id = (json.loads(body) or {}).get("id")
            except Exception:
                message_id = None
            return {"ok": True, "status": "sent", "provider": "resend", "message_id": message_id}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return _public_failure("resend_send_failed", body or str(exc), provider="resend")
    except Exception as exc:
        return _public_failure("resend_send_failed", str(exc), provider="resend")


def _send_smtp(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    host = _env("SMTP_HOST")
    try:
        port = int(_env("SMTP_PORT", "587") or "587")
    except Exception:
        return _public_failure("smtp_not_configured", "SMTP_PORT must be a valid integer.", provider="smtp")
    username = _env("SMTP_USERNAME")
    password = _env("SMTP_PASSWORD")
    from_email = _env("EMAIL_OTP_FROM") or _env("EMAIL_FROM") or username
    use_ssl = _env_bool("SMTP_USE_SSL", False)
    use_tls = _env_bool("SMTP_USE_TLS", not use_ssl)

    if not host or not from_email:
        return _public_failure("smtp_not_configured", "SMTP_HOST and EMAIL_OTP_FROM are required.", provider="smtp")
    if bool(username) != bool(password):
        return _public_failure("smtp_not_configured", "SMTP_USERNAME and SMTP_PASSWORD must be set together.", provider="smtp")

    message = EmailMessage()
    message["Subject"] = _subject()
    message["From"] = from_email
    message["To"] = to_email
    reply_to = _env("EMAIL_OTP_REPLY_TO") or _env("EMAIL_REPLY_TO")
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(_message_body(code, expires_minutes))
    message.add_alternative(_message_html(code, expires_minutes), subtype="html")

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context()) as server:
                if username and password:
                    server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                if username and password:
                    server.login(username, password)
                server.send_message(message)
        return {"ok": True, "status": "sent", "provider": "smtp"}
    except Exception as exc:
        return _public_failure("smtp_send_failed", str(exc), provider="smtp")


def deliver_login_code(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    """Send a login OTP only when production email delivery is explicitly enabled.

    Supported providers:
    - EMAIL_OTP_PROVIDER=resend with RESEND_API_KEY and EMAIL_OTP_FROM
    - EMAIL_OTP_PROVIDER=smtp with SMTP_HOST, SMTP_PORT, optional SMTP_USERNAME/SMTP_PASSWORD, and EMAIL_OTP_FROM
    """
    readiness = email_delivery_status()
    if not readiness["enabled"]:
        return {"ok": False, "status": "email_delivery_not_enabled", "provider": readiness["provider"]}
    if not readiness["configured"]:
        return _public_failure(
            "email_delivery_not_configured",
            ", ".join(readiness["missing_configuration"]),
            provider=readiness["provider"],
        )

    provider = readiness["provider"]
    if provider == "resend":
        return _send_resend(to_email, code, expires_minutes)
    if provider == "smtp":
        return _send_smtp(to_email, code, expires_minutes)
    return _public_failure("email_provider_not_configured", "Set EMAIL_OTP_PROVIDER to resend or smtp.", provider=provider)
