from __future__ import annotations

from typing import Any

from app.services.supabase_client import get_supabase

_PATCH_FLAG = "_moveready_zero_row_compat"


def apply_postgrest_zero_row_compat() -> None:
    """Normalize Supabase/PostgREST maybe_single() zero-row behavior.

    The deployed PostgREST client can return HTTP 406 and then None for
    ``maybe_single`` when no row exists. MoveReady uses ``maybe_single`` only
    for optional/existence lookups where zero rows is valid state. Preserve the
    existing dict-or-None contract by executing those requests with ordinary
    JSON list semantics and collapsing the result to the first row.
    """
    probe = (
        get_supabase()
        .table("relocation_jobs")
        .select("id")
        .limit(1)
        .maybe_single()
    )
    builder_cls = probe.__class__
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
