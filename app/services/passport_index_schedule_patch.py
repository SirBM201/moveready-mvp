from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import (
    PASSPORT_INDEX_SYNC_HOUR_UTC,
    PASSPORT_INDEX_SYNC_MINUTE_UTC,
    PASSPORT_INDEX_SYNC_WEEKDAYS,
)
from app.services import passport_index_provider as provider


_PATCH_APPLIED = False


def _next_sync_due_iso(from_dt: Optional[datetime] = None) -> str:
    base = from_dt or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    else:
        base = base.astimezone(timezone.utc)

    configured = [
        item.strip().upper()
        for item in (PASSPORT_INDEX_SYNC_WEEKDAYS or "FRI").split(",")
        if item.strip()
    ]
    weekday_map = {
        "MON": 0,
        "TUE": 1,
        "WED": 2,
        "THU": 3,
        "FRI": 4,
        "SAT": 5,
        "SUN": 6,
    }
    target_days = sorted({weekday_map[item] for item in configured if item in weekday_map}) or [4]

    for offset in range(0, 8):
        candidate_date = (base + timedelta(days=offset)).date()
        candidate = datetime(
            candidate_date.year,
            candidate_date.month,
            candidate_date.day,
            PASSPORT_INDEX_SYNC_HOUR_UTC,
            PASSPORT_INDEX_SYNC_MINUTE_UTC,
            tzinfo=timezone.utc,
        )
        if candidate.weekday() in target_days and candidate > base:
            return candidate.isoformat()

    return (base + timedelta(days=7)).replace(
        hour=PASSPORT_INDEX_SYNC_HOUR_UTC,
        minute=PASSPORT_INDEX_SYNC_MINUTE_UTC,
        second=0,
        microsecond=0,
    ).isoformat()


def apply_schedule_patch() -> None:
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return
    provider.next_sync_due_iso = _next_sync_due_iso
    provider.PASSPORT_INDEX_SCHEDULE_PATCH_ACTIVE = True
    _PATCH_APPLIED = True
