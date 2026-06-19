from __future__ import annotations

import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any, Dict, Optional


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name, "1" if default else "0").lower()
    return value in {"1", "true", "yes", "y", "on"}


def _public_failure(status: str, detail: Optional[str] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {"ok": False, "status": status}
    if detail:
        result["detail"] = detail[:240]
    return result


def _message_body(code: str, expires_minutes: int) -> str:
    app_name = _env("EMAIL_OTP_APP_NAME", "MoveReady")
    login_url = _env("EMAIL_OTP_LOGIN_URL")
    lines = [
        f"Your {app_name} sign-in code is {code}.",
        "",
        f"This code expires in {expires_minutes} minutes.",
        "",
        "If you did not request this code, you can safely ignore this email.",
    ]
    if login_url:
        lines.extend(["", f"Login page: {login_url}"])
    return "\n".join(lines)


def _message_html(code: str, expires_minutes: int) -> str:
    app_name = _env("EMAIL_OTP_APP_NAME", "MoveReady")
    login_url = _env("EMAIL_OTP_LOGIN_URL")
    login_link = f'<p><a href="{login_url}">Open {app_name} login</a></p>' if login_url else ""
    return f"""
    <div style="font-family:Arial,sans-serif;line-height:1.55;color:#111827">
      <p>Your {app_name} sign-in code is:</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:4px">{code}</p>
      <p>This code expires in {expires_minutes} minutes.</p>
      {login_link}
      <p style="color:#6b7280">If you did not request this code, you can safely ignore this email.</p>
    </div>
    """.strip()


def _send_resend(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    api_key = _env("RESEND_API_KEY")
    from_email = _env("EMAIL_OTP_FROM") or _env("EMAIL_FROM")
    if not api_key or not from_email:
        return _public_failure("resend_not_configured", "RESEND_API_KEY and EMAIL_OTP_FROM are required.")

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": "Your MoveReady sign-in code",
        "text": _message_body(code, expires_minutes),
        "html": _message_html(code, expires_minutes),
    }

    import json

    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": "sent", "provider": "resend", "provider_response": body[:500]}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return _public_failure("resend_send_failed", body or str(exc))
    except Exception as exc:
        return _public_failure("resend_send_failed", str(exc))


def _send_smtp(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    host = _env("SMTP_HOST")
    port = int(_env("SMTP_PORT", "587") or "587")
    username = _env("SMTP_USERNAME")
    password = _env("SMTP_PASSWORD")
    from_email = _env("EMAIL_OTP_FROM") or _env("EMAIL_FROM") or username
    use_tls = _env_bool("SMTP_USE_TLS", True)

    if not host or not from_email:
        return _public_failure("smtp_not_configured", "SMTP_HOST and EMAIL_OTP_FROM are required.")

    message = EmailMessage()
    message["Subject"] = "Your MoveReady sign-in code"
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(_message_body(code, expires_minutes))
    message.add_alternative(_message_html(code, expires_minutes), subtype="html")

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if use_tls:
                server.starttls(context=ssl.create_default_context())
            if username or password:
                server.login(username, password)
            server.send_message(message)
        return {"ok": True, "status": "sent", "provider": "smtp"}
    except Exception as exc:
        return _public_failure("smtp_send_failed", str(exc))


def deliver_login_code(to_email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
    """Send a login OTP if production email delivery is explicitly enabled.

    Supported providers:
    - EMAIL_OTP_PROVIDER=resend with RESEND_API_KEY and EMAIL_OTP_FROM
    - EMAIL_OTP_PROVIDER=smtp with SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_OTP_FROM
    """
    if not _env_bool("EMAIL_OTP_DELIVERY_ENABLED", False):
        return {"ok": False, "status": "email_delivery_not_configured", "provider": "none"}

    provider = (_env("EMAIL_OTP_PROVIDER", "none") or "none").lower()
    if provider == "resend":
        return _send_resend(to_email, code, expires_minutes)
    if provider == "smtp":
        return _send_smtp(to_email, code, expires_minutes)
    return _public_failure("email_provider_not_configured", "Set EMAIL_OTP_PROVIDER to resend or smtp.")
