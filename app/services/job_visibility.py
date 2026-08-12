from __future__ import annotations

from typing import Any, Mapping, Optional


def job_is_visible_to_account(row: Optional[Mapping[str, Any]], email: str) -> bool:
    if not row:
        return False
    if row.get("is_curated"):
        return True
    return str(row.get("owner_email") or "").casefold() == str(email or "").casefold()
