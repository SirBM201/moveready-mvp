from __future__ import annotations

import hashlib
import re
from typing import Any, Dict


def _norm(value: Any) -> str:
    text = str(value or "").casefold().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def canonical_candidate_fingerprint(candidate: Dict[str, Any], watch_id: str) -> str:
    """Return the canonical monitored-vacancy identity used by the database.

    One watch belongs to one employer/source, so watch id + normalized title + location
    is stable across listing/detail/tracking URL changes while still keeping genuinely
    different postings (including Contract wording) separate.  Migration 043 aligns
    existing monitored rows to this exact MD5 contract and copies the value into both
    canonical_identity and source_fingerprint, allowing the existing scan lookup to
    update the survivor instead of inserting another row on every scan.
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
    return hashlib.md5(material.encode("utf-8"), usedforsecurity=False).hexdigest()


def install() -> None:
    """Install before job_automation imports candidate_fingerprint by value."""
    from app.services import job_discovery

    job_discovery.candidate_fingerprint = canonical_candidate_fingerprint
