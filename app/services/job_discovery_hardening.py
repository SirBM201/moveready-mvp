from __future__ import annotations

"""Runtime hardening for official vacancy discovery."""
import re
import time
from typing import Any, Dict, List, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import httpx
from app.services import job_discovery as _base
from app.services import job_geography as _geo

_ORIGINAL_FETCH_SOURCE = _base.fetch_source
_MAX_GENERIC_PAGES = 6
_MAX_TRANSIENT_ATTEMPTS = 3
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
_GENERIC_NAVIGATION_TITLES = {"apply","apply now","apply to job","career","careers","current opportunities","find jobs","job listings","job search","jobs","open positions","opportunities","search jobs","search open jobs","search opportunities","view job postings"}
_GENERIC_ROLE_WORDS = {"production","manufacturing","technician","supervisor","manager","engineer","engineering","team","leader","lead","operator","assembly","quality","maintenance","mechanical","shift"}

def _canonical_url(value: Any) -> str:
    parsed=urlparse(str(value or "").strip())
    if not parsed.scheme or not parsed.hostname: return str(value or "").strip().casefold().rstrip("/")
    path=re.sub(r"/+","/",parsed.path or "/").rstrip("/") or "/"
    return urlunparse((parsed.scheme.casefold(),parsed.netloc.casefold(),path,"","",""))

def _normalized_title(value: Any) -> str:
    title=_base.clean_text(value,220).casefold().replace("mould","mold")
    title=re.sub(r"\s*\([^)]*(?:contract|temporary|temp|full[- ]?time|part[- ]?time)[^)]*\)\s*"," ",title)
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9]+"," ",title)).strip()

def _job_identity(row: Dict[str,Any])->tuple[str,str,str,str]:
    return (_canonical_url(row.get("job_url")),_normalized_title(row.get("job_title")),str(row.get("country") or "").strip().casefold(),str(row.get("city") or row.get("province") or "").strip().casefold())

def _semantic_identity(row: Dict[str,Any])->tuple[str,str,str,str]:
    return (str(row.get("company_name") or "").strip().casefold(),_normalized_title(row.get("job_title")),str(row.get("country") or "").strip().casefold(),str(row.get("city") or row.get("province") or "").strip().casefold())

def _role_tokens(value: Any)->set[str]: return {x for x in _normalized_title(value).split() if len(x)>2}

def _candidate_is_relevant(row: Dict[str,Any],keywords: Sequence[str])->bool:
    if not keywords: return True
    title=_normalized_title(row.get("job_title"))
    terms=[_normalized_title(x) for x in keywords if _normalized_title(x)]
    if any(t in title for t in terms if len(t)>=4): return True
    title_tokens=_role_tokens(title); target=set(); distinctive=set()
    for term in terms:
        tokens=_role_tokens(term); target.update(tokens); distinctive.update(x for x in tokens if x not in _GENERIC_ROLE_WORDS)
    overlap=title_tokens & target
    return len(overlap)>=2 or bool(overlap & distinctive)

def _looks_like_real_vacancy(row: Dict[str,Any])->bool:
    title=_base.clean_text(row.get("job_title"),220)
    if not title or title.casefold() in _GENERIC_NAVIGATION_TITLES: return False
    parsed=urlparse(str(row.get("job_url") or "").strip())
    if parsed.scheme not in {"http","https"} or not parsed.hostname: return False
    return bool(row.get("country") or row.get("province") or row.get("city")) or len(_base.clean_text(row.get("description_summary"),500))>=20 or len(title.split())>=2

def _page_url(source_url:str,page:int)->str:
    p=urlparse(source_url); q=dict(parse_qsl(p.query,keep_blank_values=True)); q["page"]=str(page)
    return urlunparse((p.scheme,p.netloc,p.path,p.params,urlencode(q),""))

def _merge_jobs(groups:Sequence[Sequence[Dict[str,Any]]],keywords:Sequence[str]=())->List[Dict[str,Any]]:
    output=[]; seen_urls=set(); seen_semantic=set()
    for group in groups:
        for row in group:
            if not _looks_like_real_vacancy(row) or not _candidate_is_relevant(row,keywords): continue
            key=_job_identity(row); semantic=_semantic_identity(row)
            if key[0] in seen_urls or semantic in seen_semantic: continue
            seen_urls.add(key[0]); seen_semantic.add(semantic); output.append(row)
            if len(output)>=_base.MAX_CANDIDATES: return output
    return output

def _failure_code(exc:Exception)->str:
    if isinstance(exc,httpx.HTTPStatusError):
        status=exc.response.status_code
        if status in {401,403}: return f"official_source_access_blocked_http_{status}"
        if status==404: return "official_source_not_found_http_404"
        if status==429: return "official_source_rate_limited_http_429"
        if 500<=status<=599: return f"official_source_upstream_error_http_{status}"
        return f"official_source_http_{status}"
    if isinstance(exc,httpx.TimeoutException): return "official_source_timeout"
    if isinstance(exc,httpx.TransportError): return "official_source_network_error"
    value=str(exc) or exc.__class__.__name__
    return _base.clean_text(value,100)

def _is_transient(exc:Exception)->bool:
    if isinstance(exc,(httpx.TimeoutException,httpx.TransportError)): return True
    return isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code in _RETRYABLE_STATUS

def _fetch_with_retry(source_url:str,requested_adapter:str,keywords:Sequence[str],*,_listing_hops:int)->tuple[Dict[str,Any],int]:
    last:Exception|None=None
    for attempt in range(1,_MAX_TRANSIENT_ATTEMPTS+1):
        try:
            result=_ORIGINAL_FETCH_SOURCE(source_url,requested_adapter,keywords,_listing_hops=_listing_hops)
            return result,attempt
        except Exception as exc:
            last=exc
            if not _is_transient(exc) or attempt>=_MAX_TRANSIENT_ATTEMPTS: break
            time.sleep(0.15*(2**(attempt-1)))
    assert last is not None
    raise RuntimeError(_failure_code(last)) from last

def fetch_source_hardened(source_url:str,requested_adapter:str,keywords:Sequence[str],*,_listing_hops:int=0)->Dict[str,Any]:
    first,attempts=_fetch_with_retry(source_url,requested_adapter,keywords,_listing_hops=_listing_hops)
    adapter=str(first.get("adapter") or ""); first_jobs=list(first.get("jobs") or [])
    base={**first,"fetch_attempts":attempts,"recovered_after_retry":attempts>1}
    if adapter not in {"generic","jsonld"} or _listing_hops>0: return {**base,"jobs":_merge_jobs([first_jobs],keywords)}
    if not first_jobs: return {**base,"jobs":[]}
    groups=[first_jobs]; known={_job_identity(x) for x in _merge_jobs(groups,keywords)}; pages_checked=1
    for page in range(1,_MAX_GENERIC_PAGES):
        try: result,_attempts=_fetch_with_retry(_page_url(str(first.get("fetched_url") or source_url),page),requested_adapter,keywords,_listing_hops=1)
        except Exception: break
        jobs=_merge_jobs([list(result.get("jobs") or [])],keywords); pages_checked+=1
        new=[x for x in jobs if _job_identity(x) not in known]
        if not new: break
        groups.append(new); known.update(_job_identity(x) for x in new)
        if len(known)>=_base.MAX_CANDIDATES: break
    return {**base,"jobs":_merge_jobs(groups,keywords),"pagination_pages_checked":pages_checked,"complete_listing":bool(first.get("complete_listing")) and pages_checked==1}

def install()->None:
    # Geography normalization is deliberately global. Canada-specific subdivision recognition
    # remains available inside job_geography, but discovery itself is not destination-specific.
    _base.COUNTRY_ALIASES = dict(_geo.COUNTRY_ALIASES)
    _base._normalized_country = _geo.normalize_country
    _base._infer_location = _geo.infer_location
    if getattr(_base.fetch_source,"__name__","")!="fetch_source_hardened": _base.fetch_source=fetch_source_hardened
