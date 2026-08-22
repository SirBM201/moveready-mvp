from __future__ import annotations

"""Extensions for public ATS career pages that do not expose anonymous partner APIs.

Gupy documents authenticated employer APIs, but public employer career pages remain the
appropriate source for anonymous MoveReady discovery. This extension recognizes Gupy
hosts and parses their public HTML/JSON-LD without requiring or storing employer tokens.
"""
from typing import Any, Dict, List, Sequence
from urllib.parse import urlparse

from app.services import job_discovery as _base

GUPY_HOST = "gupy.io"


def is_gupy_url(value: str) -> bool:
    host = str(urlparse(str(value or "")).hostname or "").casefold().rstrip(".")
    return host == GUPY_HOST or host.endswith(f".{GUPY_HOST}")


def parse_gupy_public_page(body: str, source_url: str, keywords: Sequence[str]) -> List[Dict[str, Any]]:
    # Gupy public pages can expose JobPosting JSON-LD. Reuse the source-first generic
    # parser so MoveReady only ingests vacancies actually published on the public board.
    rows = _base._parse_jsonld(body, source_url, include_generic_links=True)
    output: List[Dict[str, Any]] = []
    for row in rows:
        if not _base.candidate_matches(row, keywords):
            continue
        row = dict(row)
        row["source_name"] = "Official Gupy employer career page"
        output.append(row)
        if len(output) >= _base.MAX_CANDIDATES:
            break
    return output


def install() -> None:
    _base.SUPPORTED_ATS_HOSTS.add(GUPY_HOST)

    original_detect = _base.detect_adapter
    original_parse = _base.parse_source

    if getattr(original_detect, "__name__", "") != "detect_adapter_with_gupy":
        def detect_adapter_with_gupy(source_url: str, requested: str = "auto") -> str:
            if requested and requested != "auto":
                return requested
            if is_gupy_url(source_url):
                return "gupy"
            return original_detect(source_url, requested)
        _base.detect_adapter = detect_adapter_with_gupy

    if getattr(original_parse, "__name__", "") != "parse_source_with_gupy":
        def parse_source_with_gupy(body: str, *, content_type: str, source_url: str, adapter: str, keywords: Sequence[str]) -> Dict[str, Any]:
            if adapter != "gupy":
                return original_parse(body, content_type=content_type, source_url=source_url, adapter=adapter, keywords=keywords)
            rows = parse_gupy_public_page(body, source_url, keywords)
            seen = set()
            jobs: List[Dict[str, Any]] = []
            for row in rows:
                key = (str(row.get("job_url") or "").casefold().rstrip("/"), str(row.get("job_title") or "").casefold())
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(row)
            return {"adapter": "gupy", "jobs": jobs, "complete_listing": bool(jobs)}
        _base.parse_source = parse_source_with_gupy
