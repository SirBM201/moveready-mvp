from __future__ import annotations

from app.core.config import AUTH_OTP_DEV_MODE
from app.routes import auth as _auth


def _safe_dev_code_allowed() -> bool:
    return bool(AUTH_OTP_DEV_MODE)


# The original auth blueprint keeps the route implementation.
# This wrapper ensures dev OTP codes are exposed only when AUTH_OTP_DEV_MODE is explicitly true.
_auth._dev_code_allowed = _safe_dev_code_allowed

bp = _auth.bp
