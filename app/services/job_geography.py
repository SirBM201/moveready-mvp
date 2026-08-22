from __future__ import annotations

import re
from typing import Any, Optional, Sequence, Tuple

# Canonical country names plus common ATS/user aliases. This registry is intentionally
# geography-wide rather than tied to one destination market. Unknown country names are
# preserved instead of being coerced to a supported country.
COUNTRY_ALIASES = {
    # North America
    "ca": "Canada", "can": "Canada", "canada": "Canada",
    "us": "United States", "usa": "United States", "u.s.": "United States", "u.s.a.": "United States",
    "united states": "United States", "united states of america": "United States",
    "mx": "Mexico", "mex": "Mexico", "mexico": "Mexico",
    # Europe
    "uk": "United Kingdom", "gb": "United Kingdom", "gbr": "United Kingdom", "great britain": "United Kingdom",
    "united kingdom": "United Kingdom", "england": "United Kingdom", "scotland": "United Kingdom",
    "wales": "United Kingdom", "northern ireland": "United Kingdom",
    "ie": "Ireland", "irl": "Ireland", "ireland": "Ireland",
    "de": "Germany", "deu": "Germany", "ger": "Germany", "germany": "Germany", "deutschland": "Germany",
    "fr": "France", "fra": "France", "france": "France",
    "nl": "Netherlands", "nld": "Netherlands", "netherlands": "Netherlands", "the netherlands": "Netherlands",
    "be": "Belgium", "bel": "Belgium", "belgium": "Belgium",
    "es": "Spain", "esp": "Spain", "spain": "Spain", "españa": "Spain",
    "pt": "Portugal", "prt": "Portugal", "portugal": "Portugal",
    "it": "Italy", "ita": "Italy", "italy": "Italy", "ch": "Switzerland", "che": "Switzerland", "switzerland": "Switzerland",
    "at": "Austria", "aut": "Austria", "austria": "Austria", "fi": "Finland", "fin": "Finland", "finland": "Finland",
    "se": "Sweden", "swe": "Sweden", "sweden": "Sweden", "no": "Norway", "nor": "Norway", "norway": "Norway",
    "dk": "Denmark", "dnk": "Denmark", "denmark": "Denmark", "pl": "Poland", "pol": "Poland", "poland": "Poland",
    "cz": "Czechia", "cze": "Czechia", "czech republic": "Czechia", "czechia": "Czechia",
    "gr": "Greece", "grc": "Greece", "greece": "Greece", "ro": "Romania", "rou": "Romania", "romania": "Romania",
    "hu": "Hungary", "hun": "Hungary", "hungary": "Hungary",
    # Middle East
    "ae": "United Arab Emirates", "are": "United Arab Emirates", "uae": "United Arab Emirates", "united arab emirates": "United Arab Emirates",
    "sa": "Saudi Arabia", "sau": "Saudi Arabia", "saudi arabia": "Saudi Arabia",
    "kw": "Kuwait", "kwt": "Kuwait", "kuwait": "Kuwait", "qa": "Qatar", "qat": "Qatar", "qatar": "Qatar",
    "bh": "Bahrain", "bhr": "Bahrain", "bahrain": "Bahrain", "om": "Oman", "omn": "Oman", "oman": "Oman",
    "il": "Israel", "isr": "Israel", "israel": "Israel", "jo": "Jordan", "jor": "Jordan", "jordan": "Jordan",
    # Africa
    "ng": "Nigeria", "nga": "Nigeria", "nigeria": "Nigeria", "gh": "Ghana", "gha": "Ghana", "ghana": "Ghana",
    "za": "South Africa", "zaf": "South Africa", "south africa": "South Africa", "ke": "Kenya", "ken": "Kenya", "kenya": "Kenya",
    "eg": "Egypt", "egy": "Egypt", "egypt": "Egypt", "ma": "Morocco", "mar": "Morocco", "morocco": "Morocco",
    "tz": "Tanzania", "tza": "Tanzania", "tanzania": "Tanzania", "ug": "Uganda", "uga": "Uganda", "uganda": "Uganda",
    "rw": "Rwanda", "rwa": "Rwanda", "rwanda": "Rwanda",
    # Asia-Pacific
    "au": "Australia", "aus": "Australia", "australia": "Australia", "nz": "New Zealand", "nzl": "New Zealand", "new zealand": "New Zealand",
    "sg": "Singapore", "sgp": "Singapore", "singapore": "Singapore", "in": "India", "ind": "India", "india": "India",
    "jp": "Japan", "jpn": "Japan", "japan": "Japan", "kr": "South Korea", "kor": "South Korea", "south korea": "South Korea", "republic of korea": "South Korea",
    "cn": "China", "chn": "China", "china": "China", "hk": "Hong Kong", "hkg": "Hong Kong", "hong kong": "Hong Kong",
    "my": "Malaysia", "mys": "Malaysia", "malaysia": "Malaysia", "id": "Indonesia", "idn": "Indonesia", "indonesia": "Indonesia",
    "ph": "Philippines", "phl": "Philippines", "philippines": "Philippines", "th": "Thailand", "tha": "Thailand", "thailand": "Thailand",
    "vn": "Vietnam", "vnm": "Vietnam", "vietnam": "Vietnam",
    # Latin America
    "br": "Brazil", "bra": "Brazil", "brazil": "Brazil", "brasil": "Brazil",
    "ar": "Argentina", "arg": "Argentina", "argentina": "Argentina", "cl": "Chile", "chl": "Chile", "chile": "Chile",
    "co": "Colombia", "col": "Colombia", "colombia": "Colombia", "pe": "Peru", "per": "Peru", "peru": "Peru", "perú": "Peru",
}

CANADA_SUBDIVISIONS = {
    "ab":"Alberta", "alberta":"Alberta", "bc":"British Columbia", "british columbia":"British Columbia",
    "mb":"Manitoba", "manitoba":"Manitoba", "nb":"New Brunswick", "new brunswick":"New Brunswick",
    "nl":"Newfoundland and Labrador", "newfoundland and labrador":"Newfoundland and Labrador",
    "ns":"Nova Scotia", "nova scotia":"Nova Scotia", "nt":"Northwest Territories", "northwest territories":"Northwest Territories",
    "nu":"Nunavut", "nunavut":"Nunavut", "on":"Ontario", "ontario":"Ontario", "pe":"Prince Edward Island",
    "prince edward island":"Prince Edward Island", "qc":"Quebec", "quebec":"Quebec", "québec":"Quebec",
    "sk":"Saskatchewan", "saskatchewan":"Saskatchewan", "yt":"Yukon", "yukon":"Yukon",
}

CANONICAL_COUNTRIES = frozenset(COUNTRY_ALIASES.values())


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_country(value: Any) -> str:
    original = _clean(value)
    key = original.casefold().rstrip(".")
    return COUNTRY_ALIASES.get(key, original)


def infer_location(values: Sequence[Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    cells = [_clean(v) for v in values if _clean(v)]
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None

    for cell in cells:
        parts = [_clean(p) for p in re.split(r"[,|]", cell) if _clean(p)]
        for idx, part in enumerate(parts):
            normalized = normalize_country(part)
            if normalized in CANONICAL_COUNTRIES:
                country = normalized
                if idx and not city:
                    previous = parts[idx - 1]
                    if normalize_country(previous) not in CANONICAL_COUNTRIES and previous.casefold() not in CANADA_SUBDIVISIONS:
                        city = previous
            subdivision = CANADA_SUBDIVISIONS.get(part.casefold())
            if subdivision and (not country or country == "Canada"):
                country = "Canada"
                region = subdivision
                if idx and not city:
                    previous = parts[idx - 1]
                    if previous.casefold() not in CANADA_SUBDIVISIONS:
                        city = previous

    # Some ATS payloads provide country and city in separate cells.
    if country:
        for cell in cells:
            if normalize_country(cell) in CANONICAL_COUNTRIES or cell.casefold() in CANADA_SUBDIVISIONS:
                continue
            if len(cell) <= 100 and not city:
                city = cell
                break
    return country, region, city
