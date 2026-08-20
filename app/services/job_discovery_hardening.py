from __future__ import annotations

"""Runtime hardening for official vacancy discovery."""
import re
from typing import Any, Dict, List, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import httpx
from app.services import job_discovery as _base

_ORIGINAL_FETCH_SOURCE = _base.fetch_source
_MAX_GENERIC_PAGES = 6
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

def _actionable_fetch_error(exc:Exception)->RuntimeError:
    if isinstance(exc,httpx.HTTPStatusError):
        status=exc.response.status_code
        if status in {401,403}: return RuntimeError(f"official_source_access_blocked_http_{status}")
        if status==404: return RuntimeError("official_source_not_found_http_404")
        if status==429: return RuntimeError("official_source_rate_limited_http_429")
        if 500<=status<=599: return RuntimeError(f"official_source_upstream_error_http_{status}")
    if isinstance(exc,httpx.TimeoutException): return RuntimeError("official_source_timeout")
    if isinstance(exc,httpx.TransportError): return RuntimeError("official_source_network_error")
    return RuntimeError(str(exc) or exc.__class__.__name__)

def fetch_source_hardened(source_url:str,requested_adapter:str,keywords:Sequence[str],*,_listing_hops:int=0)->Dict[str,Any]:
    try: first=_ORIGINAL_FETCH_SOURCE(source_url,requested_adapter,keywords,_listing_hops=_listing_hops)
    except Exception as exc: raise _actionable_fetch_error(exc) from exc
    adapter=str(first.get("adapter") or ""); first_jobs=list(first.get("jobs") or [])
    if adapter not in {"generic","jsonld"} or _listing_hops>0: return {**first,"jobs":_merge_jobs([first_jobs],keywords)}
    if not first_jobs: return {**first,"jobs":[]}
    groups=[first_jobs]; known={_job_identity(x) for x in _merge_jobs(groups,keywords)}; pages_checked=1
    for page in range(1,_MAX_GENERIC_PAGES):
        try: result=_ORIGINAL_FETCH_SOURCE(_page_url(str(first.get("fetched_url") or source_url),page),requested_adapter,keywords,_listing_hops=1)
        except Exception: break
        jobs=_merge_jobs([list(result.get("jobs") or [])],keywords); pages_checked+=1
        new=[x for x in jobs if _job_identity(x) not in known]
        if not new: break
        groups.append(new); known.update(_job_identity(x) for x in new)
        if len(known)>=_base.MAX_CANDIDATES: break
    return {**first,"jobs":_merge_jobs(groups,keywords),"pagination_pages_checked":pages_checked,"complete_listing":bool(first.get("complete_listing")) and pages_checked==1}

def install()->None:
    if getattr(_base.fetch_source,"__name__","")!="fetch_source_hardened": _base.fetch_source=fetch_source_hardened
