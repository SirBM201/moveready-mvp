from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import httpx


MAX_SOURCE_BYTES = 3 * 1024 * 1024
MAX_CANDIDATES = 200
USER_AGENT = "MoveReady-Official-Job-Monitor/1.0 (+https://sir-bm-201-moveready-frontend.vercel.app/jobs)"
SUPPORTED_ATS_HOSTS = {
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "boards-api.greenhouse.io",
    "jobs.lever.co",
    "api.lever.co",
    "myworkdayjobs.com",
    "workdayjobs.com",
    "smartrecruiters.com",
    "jobs.smartrecruiters.com",
    "api.smartrecruiters.com",
    "icims.com",
    "careers-page.com",
    "oraclecloud.com",
    "successfactors.com",
    "successfactors.eu",
    "phenompeople.com",
    "dayforcehcm.com",
    "ultipro.com",
    "ukg.com",
    "adp.com",
    "bamboohr.com",
}
IGNORED_KEYWORD_TOKENS = {
    "a", "an", "and", "at", "for", "in", "job", "jobs", "of", "or", "role", "the", "to", "with",
}
JOB_LINK_HINTS = {
    "apply", "career", "careers", "employment", "job", "jobs", "opening", "opportunity", "position", "vacancy",
}


def clean_text(value: Any, limit: int = 4000) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def normalize_terms(values: Iterable[Any], *, limit: int = 40) -> List[str]:
    output: List[str] = []
    seen = set()
    for value in values:
        term = clean_text(value, 100)
        key = term.casefold()
        if term and key not in seen:
            output.append(term)
            seen.add(key)
        if len(output) >= limit:
            break
    return output


def _hostname(url: str) -> str:
    return str(urlparse(url).hostname or "").casefold().rstrip(".")


def _host_matches(host: str, allowed_host: str) -> bool:
    return host == allowed_host or host.endswith(f".{allowed_host}")


def _company_domain(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def source_host_is_allowed(source_url: str, company_urls: Sequence[str]) -> bool:
    host = _hostname(source_url)
    if not host:
        return False
    if any(_host_matches(host, allowed) for allowed in SUPPORTED_ATS_HOSTS):
        return True
    for value in company_urls:
        allowed = _company_domain(_hostname(str(value or "")))
        if allowed and (_host_matches(host, allowed) or _host_matches(allowed, host)):
            return True
    return False


def validate_public_https_url(value: Any, *, resolve_dns: bool = True) -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source_url_must_be_public_https")
    if parsed.port not in (None, 443):
        raise ValueError("source_url_port_not_allowed")
    host = parsed.hostname.casefold().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or "." not in host:
        raise ValueError("source_url_host_not_public")
    try:
        literal = ipaddress.ip_address(host)
        if not literal.is_global:
            raise ValueError("source_url_host_not_public")
    except ValueError as exc:
        if str(exc) == "source_url_host_not_public":
            raise
    if resolve_dns:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        except socket.gaierror as exc:
            raise ValueError("source_url_dns_lookup_failed") from exc
        if not addresses:
            raise ValueError("source_url_dns_lookup_failed")
        for address in addresses:
            try:
                if not ipaddress.ip_address(address).is_global:
                    raise ValueError("source_url_resolves_to_private_network")
            except ValueError as exc:
                if str(exc) == "source_url_resolves_to_private_network":
                    raise
    path = parsed.path or "/"
    return urlunparse(("https", parsed.netloc, path, parsed.params, parsed.query, ""))


def detect_adapter(source_url: str, requested: str = "auto") -> str:
    if requested and requested != "auto":
        return requested
    host = _hostname(source_url)
    if "greenhouse.io" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "myworkdayjobs.com" in host or "workdayjobs.com" in host:
        return "workday"
    if "smartrecruiters.com" in host:
        return "smartrecruiters"
    return "jsonld"


def _greenhouse_api_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        raise ValueError("greenhouse_board_token_missing")
    token = segments[0]
    if parsed.hostname == "boards-api.greenhouse.io" and len(segments) >= 3 and segments[0] == "v1" and segments[1] == "boards":
        token = segments[2]
    token = re.sub(r"[^A-Za-z0-9_-]", "", token)
    if not token:
        raise ValueError("greenhouse_board_token_missing")
    return f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def _lever_api_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        raise ValueError("lever_site_token_missing")
    token = re.sub(r"[^A-Za-z0-9_-]", "", segments[0])
    if not token:
        raise ValueError("lever_site_token_missing")
    return f"https://api.lever.co/v0/postings/{token}?mode=json"


def _workday_api_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    host = str(parsed.hostname or "")
    tenant = host.split(".")[0]
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not tenant or not segments:
        raise ValueError("workday_tenant_or_site_missing")
    site_index = 1 if len(segments) > 1 and re.fullmatch(r"[a-z]{2}(?:-[A-Za-z]{2})?", segments[0]) else 0
    site = segments[site_index]
    tenant = re.sub(r"[^A-Za-z0-9_-]", "", tenant)
    site = re.sub(r"[^A-Za-z0-9_-]", "", site)
    if not tenant or not site:
        raise ValueError("workday_tenant_or_site_missing")
    return f"https://{host}/wday/cxs/{tenant}/{site}/jobs"


def _smartrecruiters_api_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if parsed.hostname == "api.smartrecruiters.com" and len(segments) >= 3 and segments[0] == "v1" and segments[1] == "companies":
        token = segments[2]
    else:
        token = segments[0] if segments else ""
    token = re.sub(r"[^A-Za-z0-9_-]", "", token)
    if not token:
        raise ValueError("smartrecruiters_company_token_missing")
    return f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100"


def adapter_request_url(source_url: str, adapter: str) -> str:
    if adapter == "greenhouse":
        return _greenhouse_api_url(source_url)
    if adapter == "lever":
        return _lever_api_url(source_url)
    if adapter == "workday":
        return _workday_api_url(source_url)
    if adapter == "smartrecruiters":
        return _smartrecruiters_api_url(source_url)
    return source_url


class _JobHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.json_blocks: List[str] = []
        self.links: List[Tuple[str, str]] = []
        self._json_depth = 0
        self._json_parts: List[str] = []
        self._link_href = ""
        self._link_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attributes = {key.casefold(): value or "" for key, value in attrs}
        if tag.casefold() == "script" and "ld+json" in attributes.get("type", "").casefold():
            self._json_depth += 1
            self._json_parts = []
        if tag.casefold() == "a" and attributes.get("href"):
            self._link_href = attributes["href"]
            self._link_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._json_depth:
            self._json_depth -= 1
            block = "".join(self._json_parts).strip()
            if block:
                self.json_blocks.append(block)
            self._json_parts = []
        if tag.casefold() == "a" and self._link_href:
            self.links.append((self._link_href, clean_text(" ".join(self._link_parts), 220)))
            self._link_href = ""
            self._link_parts = []

    def handle_data(self, data: str) -> None:
        if self._json_depth:
            self._json_parts.append(data)
        if self._link_href:
            self._link_parts.append(data)


def _walk_json(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        kind = value.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if any(str(item or "").casefold() == "jobposting" for item in kinds):
            yield value
        for nested in value.values():
            yield from _walk_json(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_json(nested)


def _iso_datetime(value: Any) -> Optional[str]:
    raw = clean_text(value, 80)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def _job_location(value: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    locations = value if isinstance(value, list) else [value]
    for item in locations:
        if not isinstance(item, dict):
            continue
        address = item.get("address") if isinstance(item.get("address"), dict) else item
        country_value = address.get("addressCountry")
        if isinstance(country_value, dict):
            country_value = country_value.get("name")
        country = clean_text(country_value, 100) or None
        province = clean_text(address.get("addressRegion"), 100) or None
        city = clean_text(address.get("addressLocality"), 100) or None
        if country or province or city:
            return country, province, city
    return None, None, None


def _schema_candidate(item: Dict[str, Any], source_url: str) -> Optional[Dict[str, Any]]:
    title = clean_text(item.get("title") or item.get("name"), 220)
    url = str(item.get("url") or "").strip()
    if not title:
        return None
    job_url = urljoin(source_url, url) if url else source_url
    if urlparse(job_url).scheme not in {"http", "https"}:
        return None
    country, province, city = _job_location(item.get("jobLocation"))
    organization = item.get("hiringOrganization") if isinstance(item.get("hiringOrganization"), dict) else {}
    return {
        "job_title": title,
        "job_url": job_url,
        "source_url": source_url,
        "source_name": "Official employer career page",
        "description_summary": clean_text(item.get("description"), 4000),
        "employment_type": clean_text(item.get("employmentType"), 100) or None,
        "country": country,
        "province": province,
        "city": city,
        "company_name": clean_text(organization.get("name"), 180) or None,
        "posted_at": _iso_datetime(item.get("datePosted")),
        "expires_at": _iso_datetime(item.get("validThrough")),
        "skills": normalize_terms(item.get("skills") if isinstance(item.get("skills"), list) else []),
    }


def _parse_jsonld(body: str, source_url: str, *, include_generic_links: bool) -> List[Dict[str, Any]]:
    parser = _JobHtmlParser()
    parser.feed(body)
    jobs: List[Dict[str, Any]] = []
    for block in parser.json_blocks:
        try:
            decoded = json.loads(block)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        for item in _walk_json(decoded):
            candidate = _schema_candidate(item, source_url)
            if candidate:
                jobs.append(candidate)
    if jobs or not include_generic_links:
        return jobs
    for href, label in parser.links:
        combined = f"{href} {label}".casefold()
        if not label or len(label) < 4 or not any(hint in combined for hint in JOB_LINK_HINTS):
            continue
        job_url = urljoin(source_url, href)
        if urlparse(job_url).scheme not in {"http", "https"}:
            continue
        jobs.append({
            "job_title": label,
            "job_url": job_url,
            "source_url": source_url,
            "source_name": "Official employer career page",
            "description_summary": "",
            "country": None,
            "province": None,
            "city": None,
            "skills": [],
        })
    return jobs


def _discover_supported_ats_link(body: str, source_url: str) -> Optional[str]:
    parser = _JobHtmlParser()
    parser.feed(body)
    for href, _label in parser.links:
        candidate = urljoin(source_url, href)
        adapter = detect_adapter(candidate, "auto")
        if adapter in {"greenhouse", "lever", "workday", "smartrecruiters"} and source_host_is_allowed(candidate, []):
            try:
                return validate_public_https_url(candidate, resolve_dns=False)
            except ValueError:
                continue
    return None


def _parse_greenhouse(body: str, source_url: str) -> List[Dict[str, Any]]:
    payload = json.loads(body)
    rows = payload.get("jobs") if isinstance(payload, dict) else []
    output: List[Dict[str, Any]] = []
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        location = item.get("location") if isinstance(item.get("location"), dict) else {}
        title = clean_text(item.get("title"), 220)
        if not title:
            continue
        output.append({
            "job_title": title,
            "job_url": str(item.get("absolute_url") or source_url),
            "source_url": source_url,
            "source_name": "Official Greenhouse job board",
            "description_summary": clean_text(item.get("content"), 4000),
            "country": None,
            "province": None,
            "city": clean_text(location.get("name"), 100) or None,
            "employment_type": None,
            "posted_at": _iso_datetime(item.get("updated_at")),
            "expires_at": None,
            "skills": [],
        })
    return output


def _parse_lever(body: str, source_url: str) -> List[Dict[str, Any]]:
    payload = json.loads(body)
    rows = payload if isinstance(payload, list) else []
    output: List[Dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        categories = item.get("categories") if isinstance(item.get("categories"), dict) else {}
        title = clean_text(item.get("text"), 220)
        if not title:
            continue
        output.append({
            "job_title": title,
            "job_url": str(item.get("hostedUrl") or item.get("applyUrl") or source_url),
            "source_url": source_url,
            "source_name": "Official Lever job board",
            "description_summary": clean_text(item.get("descriptionPlain") or item.get("description"), 4000),
            "country": None,
            "province": None,
            "city": clean_text(categories.get("location"), 100) or None,
            "employment_type": clean_text(categories.get("commitment"), 100) or None,
            "posted_at": None,
            "expires_at": None,
            "skills": [],
        })
    return output


def _parse_workday(body: str, source_url: str) -> List[Dict[str, Any]]:
    payload = json.loads(body)
    rows = payload.get("jobPostings") if isinstance(payload, dict) else []
    parsed_source = urlparse(source_url)
    source_base = urlunparse((parsed_source.scheme, parsed_source.netloc, parsed_source.path.rstrip("/") + "/", "", "", ""))
    output: List[Dict[str, Any]] = []
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get("title"), 220)
        external_path = str(item.get("externalPath") or "")
        if not title or not external_path:
            continue
        output.append({
            "job_title": title,
            "job_url": urljoin(source_base, external_path.lstrip("/")),
            "source_url": source_url,
            "source_name": "Official Workday career site",
            "description_summary": clean_text(item.get("bulletFields") or item.get("subtitles"), 4000),
            "country": None,
            "province": None,
            "city": clean_text(item.get("locationsText"), 100) or None,
            "employment_type": None,
            "posted_at": None,
            "expires_at": None,
            "skills": [],
        })
    return output


def _parse_smartrecruiters(body: str, source_url: str) -> List[Dict[str, Any]]:
    payload = json.loads(body)
    rows = payload.get("content") if isinstance(payload, dict) else []
    parsed = urlparse(source_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    company_token = segments[0] if segments else ""
    output: List[Dict[str, Any]] = []
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get("name") or item.get("title"), 220)
        location = item.get("location") if isinstance(item.get("location"), dict) else {}
        job_id = clean_text(item.get("id") or item.get("ref"), 100)
        job_url = str(item.get("jobAdUrl") or item.get("applyUrl") or "")
        if not job_url and company_token and job_id:
            job_url = f"https://jobs.smartrecruiters.com/{company_token}/{job_id}"
        if not title or not job_url:
            continue
        employment = item.get("typeOfEmployment") if isinstance(item.get("typeOfEmployment"), dict) else {}
        output.append({
            "job_title": title,
            "job_url": job_url,
            "source_url": source_url,
            "source_name": "Official SmartRecruiters career site",
            "description_summary": clean_text(item.get("jobAd") or item.get("industry"), 4000),
            "country": clean_text(location.get("country"), 100) or None,
            "province": clean_text(location.get("region"), 100) or None,
            "city": clean_text(location.get("city"), 100) or None,
            "employment_type": clean_text(employment.get("label"), 100) or None,
            "posted_at": _iso_datetime(item.get("releasedDate")),
            "expires_at": None,
            "skills": [],
        })
    return output


def _keyword_tokens(terms: Sequence[str]) -> set[str]:
    output: set[str] = set()
    for term in terms:
        for token in re.findall(r"[a-z0-9]+", str(term or "").casefold().replace("mould", "mold")):
            if len(token) > 2 and token not in IGNORED_KEYWORD_TOKENS:
                output.add(token)
    return output


def candidate_matches(candidate: Dict[str, Any], keywords: Sequence[str]) -> bool:
    if not keywords:
        return True
    haystack = " ".join(str(candidate.get(key) or "") for key in ("job_title", "description_summary", "city", "province"))
    haystack = haystack.casefold().replace("mould", "mold")
    if any(str(term or "").casefold().replace("mould", "mold") in haystack for term in keywords if len(str(term or "").strip()) >= 4):
        return True
    tokens = _keyword_tokens(keywords)
    return bool(tokens & set(re.findall(r"[a-z0-9]+", haystack)))


def candidate_fingerprint(candidate: Dict[str, Any], watch_id: str) -> str:
    url = str(candidate.get("job_url") or "").strip().casefold().rstrip("/")
    identity = url or "|".join([
        watch_id,
        str(candidate.get("job_title") or "").casefold(),
        str(candidate.get("city") or "").casefold(),
        str(candidate.get("province") or "").casefold(),
    ])
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def candidate_content_hash(candidate: Dict[str, Any]) -> str:
    material = json.dumps({
        key: candidate.get(key)
        for key in ("job_title", "job_url", "description_summary", "employment_type", "country", "province", "city", "posted_at", "expires_at")
    }, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def parse_source(body: str, *, content_type: str, source_url: str, adapter: str, keywords: Sequence[str]) -> Dict[str, Any]:
    del content_type  # Parsers use the selected official-source adapter.
    if adapter == "greenhouse":
        rows = _parse_greenhouse(body, source_url)
        complete = True
    elif adapter == "lever":
        rows = _parse_lever(body, source_url)
        complete = True
    elif adapter == "workday":
        rows = _parse_workday(body, source_url)
        complete = True
    elif adapter == "smartrecruiters":
        rows = _parse_smartrecruiters(body, source_url)
        complete = True
    else:
        rows = _parse_jsonld(body, source_url, include_generic_links=adapter in {"generic", "jsonld"})
        complete = bool(rows) and all(row.get("description_summary") for row in rows)

    output: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        if not candidate_matches(row, keywords):
            continue
        key = (str(row.get("job_url") or "").casefold().rstrip("/"), str(row.get("job_title") or "").casefold())
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
        if len(output) >= MAX_CANDIDATES:
            break
    return {"adapter": adapter, "jobs": output, "complete_listing": complete}


def fetch_source(source_url: str, requested_adapter: str, keywords: Sequence[str]) -> Dict[str, Any]:
    validated = validate_public_https_url(source_url)
    adapter = detect_adapter(validated, requested_adapter)
    request_url = validate_public_https_url(adapter_request_url(validated, adapter))
    response: Optional[httpx.Response] = None
    with httpx.Client(timeout=httpx.Timeout(15.0, connect=8.0), follow_redirects=False) as client:
        for _redirect in range(4):
            if adapter == "workday":
                response = client.post(
                    request_url,
                    headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"},
                    json={"appliedFacets": {}, "limit": 100, "offset": 0, "searchText": ""},
                )
            else:
                response = client.get(request_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/html;q=0.9"})
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise RuntimeError("source_redirect_missing_location")
                request_url = validate_public_https_url(urljoin(request_url, location))
                continue
            break
    if response is None:
        raise RuntimeError("source_fetch_failed")
    response.raise_for_status()
    content = response.content
    if len(content) > MAX_SOURCE_BYTES:
        raise RuntimeError("source_response_too_large")
    body = content.decode(response.encoding or "utf-8", errors="replace")
    parsed = parse_source(
        body,
        content_type=response.headers.get("content-type", ""),
        source_url=validated,
        adapter=adapter,
        keywords=keywords,
    )
    if not parsed.get("jobs") and adapter in {"jsonld", "generic"}:
        linked_ats = _discover_supported_ats_link(body, validated)
        if linked_ats and linked_ats.casefold().rstrip("/") != validated.casefold().rstrip("/"):
            linked = fetch_source(linked_ats, "auto", keywords)
            return {**linked, "requested_url": validated, "discovered_via": linked_ats}
    return {
        **parsed,
        "requested_url": validated,
        "fetched_url": str(response.url),
        "http_status": response.status_code,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
