from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import requests

from app.core.config import (
    SECRET_KEY,
    SPARKGROWTH_API_BASE,
    SPARKGROWTH_INGESTION_KEY,
    SPARKGROWTH_TELEMETRY_ENABLED,
    SPARKGROWTH_TELEMETRY_TIMEOUT_SECONDS,
    SPARKGROWTH_WORKSPACE_ID,
)

logger = logging.getLogger(__name__)

_ALLOWED_EVENTS = {"session", "registration", "activation"}
_ATTRIBUTION_KEYS = (
    "campaign_id",
    "content_id",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
)


def telemetry_configured() -> bool:
    return bool(
        SPARKGROWTH_TELEMETRY_ENABLED
        and SPARKGROWTH_API_BASE
        and SPARKGROWTH_INGESTION_KEY
        and SPARKGROWTH_WORKSPACE_ID
        and SECRET_KEY
    )


def _hmac_identifier(namespace: str, value: str) -> str:
    digest = hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"{namespace}:{value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"mr_{namespace}_{digest[:48]}"


def subject_id_for_login_code(login_code_id: str) -> str:
    return _hmac_identifier("subject", str(login_code_id))


def session_id_for_login_code(login_code_id: str) -> str:
    return _hmac_identifier("session", str(login_code_id))


def event_id(subject_id: str, event_name: str) -> str:
    return _hmac_identifier("event", f"{subject_id}:{event_name}")


def _clean_value(value: Any, limit: int = 240) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned[:limit] or None


def _query_attribution(value: Optional[str]) -> Dict[str, str]:
    if not value:
        return {}
    try:
        query = parse_qs(urlparse(value).query, keep_blank_values=False)
    except Exception:
        return {}
    result: Dict[str, str] = {}
    for key in _ATTRIBUTION_KEYS:
        values = query.get(key)
        if values:
            cleaned = _clean_value(values[0])
            if cleaned:
                result[key] = cleaned
    return result


def capture_attribution_context(
    payload: Optional[Dict[str, Any]] = None,
    source_page: Optional[str] = None,
    referrer: Optional[str] = None,
) -> Dict[str, str]:
    """Keep only genuine campaign parameters that were actually supplied.

    Explicit payload fields take precedence over query-string values. No defaults
    are invented when campaign context is absent.
    """
    payload = payload or {}
    result: Dict[str, str] = {}
    for candidate in (referrer, source_page):
        result.update(_query_attribution(_clean_value(candidate, 2000)))
    for key in _ATTRIBUTION_KEYS:
        cleaned = _clean_value(payload.get(key))
        if cleaned:
            result[key] = cleaned
    return result


def referrer_origin(referrer: Optional[str]) -> Optional[str]:
    if not referrer:
        return None
    try:
        parsed = urlparse(referrer)
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"[:240]


def telemetry_session_metadata(
    login_code_id: str,
    attribution: Dict[str, str],
) -> Dict[str, Any]:
    return {
        "growth_subject_id": subject_id_for_login_code(login_code_id),
        "growth_session_id": session_id_for_login_code(login_code_id),
        "growth_attribution": dict(attribution),
    }


def _endpoint(path: str) -> str:
    return f"{SPARKGROWTH_API_BASE.rstrip('/')}{path}"


def track_event(
    event_name: str,
    subject_id: str,
    session_id: str,
    attribution: Optional[Dict[str, str]] = None,
    *,
    attribution_model: Optional[str] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Best-effort SG49 telemetry. Failure never blocks MoveReady product flows."""
    if event_name not in _ALLOWED_EVENTS:
        return {"sent": False, "reason": "unsupported_event"}
    if not telemetry_configured():
        return {"sent": False, "reason": "not_configured"}

    context: Dict[str, str] = {}
    for key, value in (attribution or {}).items():
        if key not in _ATTRIBUTION_KEYS:
            continue
        cleaned = _clean_value(value)
        if cleaned:
            context[key] = cleaned
    body: Dict[str, Any] = {
        "workspace_id": SPARKGROWTH_WORKSPACE_ID,
        "idempotency_key": event_id(subject_id, event_name),
        "anonymous_id": subject_id,
        "session_id": session_id,
        "event_name": event_name,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "evidence": {
            "source": "moveready_backend",
            **(evidence or {}),
        },
        **context,
    }
    if attribution_model:
        body["attribution_model"] = attribution_model

    try:
        response = requests.post(
            _endpoint("/v1/growth/attribution/ingest/touchpoint"),
            json=body,
            headers={"X-Ingestion-Key": SPARKGROWTH_INGESTION_KEY},
            timeout=SPARKGROWTH_TELEMETRY_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            logger.warning(
                "sparkgrowth.telemetry_rejected event=%s status=%s",
                event_name,
                response.status_code,
            )
            return {"sent": False, "reason": f"http_{response.status_code}"}
        data = response.json() if response.content else {}
        return {
            "sent": True,
            "accepted": bool(data.get("accepted")),
            "deduplicated": bool(data.get("deduplicated")),
            "attribution_status": data.get("attribution_status"),
        }
    except Exception as exc:
        logger.warning(
            "sparkgrowth.telemetry_unavailable event=%s error_type=%s",
            event_name,
            type(exc).__name__,
        )
        return {"sent": False, "reason": "unavailable"}


def probe_contract() -> Dict[str, Any]:
    """Read-only connectivity probe; it never inserts an SG49 event."""
    if not telemetry_configured():
        return {"ok": False, "reason": "not_configured"}
    try:
        response = requests.get(
            _endpoint(
                f"/v1/growth/attribution/ingest/contract/{SPARKGROWTH_WORKSPACE_ID}"
            ),
            headers={"X-Ingestion-Key": SPARKGROWTH_INGESTION_KEY},
            timeout=SPARKGROWTH_TELEMETRY_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            return {"ok": False, "reason": f"http_{response.status_code}"}
        data = response.json()
        return {
            "ok": True,
            "workspace_id": data.get("workspace_id"),
            "idempotency_required": bool(data.get("idempotency_required")),
            "allowed_events": data.get("allowed_events") or [],
        }
    except Exception:
        return {"ok": False, "reason": "unavailable"}
