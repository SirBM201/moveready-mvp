from __future__ import annotations

import hmac
from functools import wraps
from typing import Callable, TypeVar

from flask import jsonify, request

from app.core import config

F = TypeVar("F", bound=Callable)


def require_admin_access(fn: F) -> F:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not config.ADMIN_API_KEY:
            return jsonify({"ok": False, "error": "admin_key_not_configured"}), 500

        supplied = (request.headers.get("X-MoveReady-Admin-Key") or "").strip()
        if not supplied and config.ENV_MODE.lower() == "development":
            supplied = (request.headers.get("X-Relocation-Admin-Key") or "").strip()

        if not supplied or not hmac.compare_digest(supplied, config.ADMIN_API_KEY):
            return jsonify({"ok": False, "error": "unauthorized"}), 401

        return fn(*args, **kwargs)

    setattr(wrapper, "_moveready_admin_protected", True)
    return wrapper  # type: ignore[return-value]
