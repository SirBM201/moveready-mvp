from __future__ import annotations

import hashlib
import re
from typing import Any, Dict


def _norm(value: Any) -> str:
    text = str(value or "").casefold().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def canonical_candidate_fingerprint(candidate: Dict[str, Any], watch_id: str) -> str:
    """Return a stable vacancy identity across URL/ATS representation changes.

    Official career systems frequently expose the same vacancy through multiple URLs
    (listing URL, detail URL, tracking URL, ATS URL).  URL-first fingerprints caused
    those representations to become separate MoveReady vacancies.  The database
    canonical-identity contract introduced in migration 040 already defines one
    genuine vacancy by employer/watch + normalized title + location; runtime scans
    now use the same semantic identity.
    """
    material = "|".join(
        [
            _norm(watch_id),
            _norm(candidate.get("job_title")),
            _norm(candidate.get("city")),
            _norm(candidate.get("province")),
            _norm(candidate.get("country")),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def install() -> None:
    """Install before job_automation imports candidate_fingerprint by value."""
    from app.services import job_discovery

    job_discovery.candidate_fingerprint = canonical_candidate_fingerprint
