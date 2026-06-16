from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
