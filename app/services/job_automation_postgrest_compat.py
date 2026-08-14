from __future__ import annotations

from typing import Any

_PATCH_FLAG = "_moveready_zero_row_compat"


def apply_postgrest_zero_row_compat() -> None:
    """Normalize PostgREST maybe_single() zero-row behavior without I/O.

    MoveReady uses ``maybe_single`` for optional/existence lookups where zero
    rows is a valid state. Patch the PostgREST request-builder class directly so
    Flask application creation remains side-effect free: importing/creating the
    app must not instantiate a Supabase client, validate live credentials, or
    issue a database request.
    """
    try:
        from postgrest._sync.request_builder import SyncMaybeSingleRequestBuilder
    except ImportError:
        # Compatibility with postgrest releases that expose the builder from
        # the public package namespace.
        try:
            from postgrest import SyncMaybeSingleRequestBuilder  # type: ignore
        except ImportError:
            return

    builder_cls = SyncMaybeSingleRequestBuilder
    if getattr(builder_cls, _PATCH_FLAG, False):
        return

    original_execute = builder_cls.execute

    def execute_without_singular_406(self: Any):
        headers = getattr(self, "headers", None)
        if headers is not None:
            try:
                headers["Accept"] = "application/json"
            except Exception:
                pass
        response = original_execute(self)
        data = getattr(response, "data", None)
        if isinstance(data, list):
            try:
                response.data = data[0] if data else None
            except Exception:
                pass
        return response

    builder_cls.execute = execute_without_singular_406
    setattr(builder_cls, _PATCH_FLAG, True)
