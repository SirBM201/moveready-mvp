from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from flask import jsonify, request

from app.core.config import ADMIN_API_KEY

F = TypeVar("F", bound=Callable)


def require_admin_access(fn: F) -> F:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not ADMIN_API_KEY:
            return jsonify({"ok": False, "error": "admin_key_not_configured"}), 500

        supplied = (
            request.headers.get("X-MoveReady-Admin-Key")
            or request.headers.get("X-Relocation-Admin-Key")
            or request.headers.get("X-Admin-Key")
            or ""
        ).strip()

        if supplied != ADMIN_API_KEY:
            return jsonify({"ok": False, "error": "unauthorized"}), 401

        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
