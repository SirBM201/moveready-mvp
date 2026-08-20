from __future__ import annotations

"""Runtime hardening for official vacancy discovery.

This module deliberately wraps the stable discovery service instead of changing
its public contract.  It adds conservative pagination for employer-hosted job
boards, removes obvious navigation false positives, preserves official-source
provenance, and turns common HTTP failures into actionable monitor errors.
"""

from typing import Any, Dict, List, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.services import job_discovery as _base


_ORIGINAL_FETCH_SOURCE = _base.fetch_source
_MAX_GENERIC_PAGES = 6
_GENERIC_NAVIGATION_TITLES = {
    "apply",
    "apply now",
    "apply to job",
    "career",
    "careers",
    "current opportunities",
    "find jobs",
    "job listings",
    "job search",
    "jobs",
    "open positions",
    "opportunities",
    "search jobs",
    "search open jobs",
    "search opportunities",
    "view job postings",
}


def _job_identity(row: Dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("job_url") or "").strip().casefold().rstrip("/"),
        str(row.get("job_title") or "").strip().casefold(),
        str(row.get("country") or "").strip().casefold(),
        str(row.get("city") or row.get("province") or "").strip().casefold(),
    )


def _looks_like_real_vacancy(row: Dict[str, Any]) -> bool:
    title = _base.clean_text(row.get("job_title"), 220)
    if not title or title.casefold() in _GENERIC_NAVIGATION_TITLES:
        return False
    url = str(row.get("job_url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    # Generic employer pages often expose menu links containing the word
    # "jobs".  Require either location evidence, vacancy text, or a URL/title
    # that is more specific than a navigation label.
    has_location = bool(row.get("country") or row.get("province") or row.get("city"))
    has_description = len(_base.clean_text(row.get("description_summary"), 500)) >= 20
    specific_title = len(title.split()) >= 2 and title.casefold() not in _GENERIC_NAVIGATION_TITLES
    return has_location or has_description or specific_title


def _page_url(source_url: str, page: int) -> str:
    parsed = urlparse(source_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["page"] = str(page)
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        urlencode(query),
        "",
    ))


def _merge_jobs(groups: Sequence[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    seen = set()
    for group in groups:
        for row in group:
            if not _looks_like_real_vacancy(row):
                continue
            key = _job_identity(row)
            if key in seen:
                continue
            seen.add(key)
            output.append(row)
            if len(output) >= _base.MAX_CANDIDATES:
                return output
    return output


def _actionable_fetch_error(exc: Exception) -> RuntimeError:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in {401, 403}:
            return RuntimeError(f"official_source_access_blocked_http_{status}")
        if status == 404:
            return RuntimeError("official_source_not_found_http_404")
        if status == 429:
            return RuntimeError("official_source_rate_limited_http_429")
        if 500 <= status <= 599:
            return RuntimeError(f"official_source_upstream_error_http_{status}")
    if isinstance(exc, httpx.TimeoutException):
        return RuntimeError("official_source_timeout")
    if isinstance(exc, httpx.TransportError):
        return RuntimeError("official_source_network_error")
    return RuntimeError(str(exc) or exc.__class__.__name__)


def fetch_source_hardened(
    source_url: str,
    requested_adapter: str,
    keywords: Sequence[str],
    *,
    _listing_hops: int = 0,
) -> Dict[str, Any]:
    """Fetch an official source with conservative employer-board pagination.

    ATS feeds remain handled by their dedicated adapters.  Pagination is used
    only for generic/jsonld employer-hosted pages after the first successful
    fetch, and stops as soon as a page contributes no new vacancy identities.
    """
    try:
        first = _ORIGINAL_FETCH_SOURCE(
            source_url,
            requested_adapter,
            keywords,
            _listing_hops=_listing_hops,
        )
    except Exception as exc:  # preserve scanner failure isolation
        raise _actionable_fetch_error(exc) from exc

    adapter = str(first.get("adapter") or "")
    first_jobs = list(first.get("jobs") or [])
    if adapter not in {"generic", "jsonld"} or _listing_hops > 0:
        return {**first, "jobs": _merge_jobs([first_jobs])}

    # Only paginate when the first employer page already behaved like a job
    # listing.  This avoids probing arbitrary corporate pages.
    if not first_jobs:
        return {**first, "jobs": []}

    groups: List[Sequence[Dict[str, Any]]] = [first_jobs]
    known = {_job_identity(row) for row in _merge_jobs(groups)}
    pages_checked = 1

    for page in range(1, _MAX_GENERIC_PAGES):
        candidate_url = _page_url(str(first.get("fetched_url") or source_url), page)
        try:
            page_result = _ORIGINAL_FETCH_SOURCE(
                candidate_url,
                requested_adapter,
                keywords,
                _listing_hops=1,
            )
        except Exception:
            # A working first page must not be converted into a failed monitor
            # merely because an optional pagination URL is unsupported.
            break
        page_jobs = _merge_jobs([list(page_result.get("jobs") or [])])
        pages_checked += 1
        new_jobs = [row for row in page_jobs if _job_identity(row) not in known]
        if not new_jobs:
            break
        groups.append(new_jobs)
        known.update(_job_identity(row) for row in new_jobs)
        if len(known) >= _base.MAX_CANDIDATES:
            break

    merged = _merge_jobs(groups)
    return {
        **first,
        "jobs": merged,
        "pagination_pages_checked": pages_checked,
        "complete_listing": bool(first.get("complete_listing")) and pages_checked == 1,
    }


def install() -> None:
    """Install the hardened fetcher while retaining the existing API surface."""
    if getattr(_base.fetch_source, "__name__", "") != "fetch_source_hardened":
        _base.fetch_source = fetch_source_hardened
