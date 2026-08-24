from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

CONTRACT_VERSION = "b19.11.1-v1"

LEGAL_SUFFIXES = {
    "inc", "incorporated", "ltd", "limited", "llc", "plc", "corp", "corporation",
    "company", "co", "gmbh", "ag", "sa", "sarl", "bv", "nv", "oy", "ab", "pte",
}


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def normalize_domain(value: Any) -> str | None:
    raw = _text(value)
    if not raw:
        return None
    candidate = raw if "://" in raw else f"https://{raw}"
    host = (urlparse(candidate).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or None


def normalize_employer_name(value: Any) -> str:
    name = (_text(value) or "").casefold()
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()
    parts = [part for part in name.split() if part not in LEGAL_SUFFIXES]
    return " ".join(parts)


def canonical_employer_key(*, name: Any, domain: Any = None, country: Any = None) -> str:
    normalized_name = normalize_employer_name(name)
    normalized_domain = normalize_domain(domain)
    normalized_country = (_text(country) or "").casefold()
    identity = f"domain:{normalized_domain}" if normalized_domain else f"name:{normalized_name}|country:{normalized_country}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]


def employer_identity(payload: Mapping[str, Any]) -> dict[str, Any]:
    name = _text(payload.get("name") or payload.get("company") or payload.get("company_name") or payload.get("employer"))
    if not name:
        raise ValueError("employer_name_required")
    domain = normalize_domain(payload.get("domain") or payload.get("website") or payload.get("company_url"))
    country = _text(payload.get("country") or payload.get("location_country"))
    aliases = []
    for value in payload.get("aliases") or []:
        alias = _text(value)
        if alias and alias.casefold() != name.casefold() and alias not in aliases:
            aliases.append(alias)
    return {
        "contract_version": CONTRACT_VERSION,
        "canonical_key": canonical_employer_key(name=name, domain=domain, country=country),
        "canonical_name": name,
        "normalized_name": normalize_employer_name(name),
        "domain": domain,
        "country": country,
        "industry": _text(payload.get("industry")),
        "aliases": aliases,
        "identity_basis": "verified_domain" if domain else "normalized_name_and_country",
    }


def same_employer(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    a = employer_identity(left); b = employer_identity(right)
    domain_match = bool(a["domain"] and b["domain"] and a["domain"] == b["domain"])
    name_country_match = bool(a["normalized_name"] and a["normalized_name"] == b["normalized_name"] and (a["country"] or "").casefold() == (b["country"] or "").casefold())
    matched = domain_match or name_country_match
    return {"matched": matched, "basis": "domain" if domain_match else ("name_and_country" if name_country_match else "none"), "left": a, "right": b, "safety":{"fuzzy_name_only_merge_allowed":False,"cross_country_name_only_merge_allowed":False}}


def deduplicate_employers(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for item in items:
        identity = employer_identity(item)
        key = identity["canonical_key"]
        if key not in groups:
            groups[key] = {**identity, "source_records": 1}
        else:
            groups[key]["source_records"] += 1
            for alias in identity["aliases"] + [identity["canonical_name"]]:
                if alias.casefold() != groups[key]["canonical_name"].casefold() and alias not in groups[key]["aliases"]:
                    groups[key]["aliases"].append(alias)
    return list(groups.values())


def employer_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    identity = employer_identity(payload)
    return {**identity, "relationships":{"vacancies":True,"applications":True,"campaigns":True,"evidence":True,"outcomes":True},"safety":{"canonical_identity_is_not_employer_verification":True,"domain_must_be_evidenced_before_verified_status":True,"sponsorship_not_inferred":True,"relocation_support_not_inferred":True,"employer_intent_not_inferred":True}}
