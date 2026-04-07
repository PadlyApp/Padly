"""
Controlled vocabulary service.

Provides canonical options and validators for:
- Countries / states / cities (US + CA)
- Companies / schools / roles (predefined catalogs)
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import geonamescache
from app.services.location_matching import (
    get_metro_options,
    metro_option,
    metro_for_city,
    normalize_city_name,
    normalize_country,
    normalize_state,
)


COUNTRIES = [
    {"code": "US", "name": "United States"},
    {"code": "CA", "name": "Canada"},
]

# Geonames admin1 code -> Canadian province/territory abbreviations.
CA_ADMIN1_TO_ABBR = {
    "01": "AB",
    "02": "BC",
    "03": "MB",
    "04": "NB",
    "05": "NL",
    "07": "NS",
    "08": "ON",
    "09": "PE",
    "10": "QC",
    "11": "SK",
    "12": "YT",
    "13": "NT",
    "14": "NU",
}

CA_PROVINCES = {
    "AB": "Alberta",
    "BC": "British Columbia",
    "MB": "Manitoba",
    "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia",
    "NT": "Northwest Territories",
    "NU": "Nunavut",
    "ON": "Ontario",
    "PE": "Prince Edward Island",
    "QC": "Quebec",
    "SK": "Saskatchewan",
    "YT": "Yukon",
}

COMPANY_OPTIONS = sorted({
    "Amazon",
    "Apple",
    "Bloomberg",
    "Capital One",
    "Cisco",
    "Coinbase",
    "Databricks",
    "DoorDash",
    "Google",
    "IBM",
    "Intel",
    "Meta",
    "Microsoft",
    "NVIDIA",
    "Oracle",
    "Palantir",
    "Robinhood",
    "Salesforce",
    "Shopify",
    "Snap",
    "Spotify",
    "Stripe",
    "Tesla",
    "TikTok",
    "Uber",
    "Wayfair",
    "Workday",
})

SCHOOL_OPTIONS = sorted({
    "Carnegie Mellon University",
    "Columbia University",
    "Cornell University",
    "Georgia Institute of Technology",
    "McGill University",
    "New York University",
    "Purdue University",
    "Stanford University",
    "The University of British Columbia",
    "University of California, Berkeley",
    "University of California, Los Angeles",
    "University of Michigan",
    "University of Toronto",
    "University of Waterloo",
    "University of Washington",
    "University of Wisconsin-Madison",
})

ROLE_OPTIONS = [
    "Software Engineer",
    "Software Engineer Intern",
    "Machine Learning Engineer",
    "Data Scientist",
    "Data Analyst",
    "Product Manager",
    "Product Designer",
    "Frontend Engineer",
    "Backend Engineer",
    "Full Stack Engineer",
    "Student",
]

# Curated neighborhood lists with generic fallback for uncovered cities.
CURATED_NEIGHBORHOODS = {
    "toronto": [
        "Downtown", "North York", "Scarborough", "Etobicoke", "York",
        "The Annex", "Kensington Market", "Liberty Village", "Distillery District",
        "Harbourfront", "Leslieville", "Roncesvalles", "Queen West", "Corktown",
    ],
    "montreal": [
        "Downtown", "Old Montreal", "Plateau-Mont-Royal", "Mile End",
        "Griffintown", "Westmount", "Verdun", "NDG", "Hochelaga-Maisonneuve",
    ],
    "vancouver": [
        "Downtown", "Kitsilano", "Mount Pleasant", "Yaletown", "West End",
        "Commercial Drive", "Gastown", "Fairview", "South Granville",
    ],
    "new york": [
        "Midtown", "Financial District", "Upper East Side", "Upper West Side",
        "Chelsea", "SoHo", "East Village", "Harlem", "Williamsburg", "Astoria",
    ],
    "san francisco": [
        "Mission District", "SoMa", "Nob Hill", "Pacific Heights", "Sunset",
        "Richmond", "Castro", "Noe Valley", "Hayes Valley", "Marina",
    ],
    "seattle": [
        "Capitol Hill", "Belltown", "Queen Anne", "Fremont", "Ballard",
        "South Lake Union", "University District", "Beacon Hill", "Greenwood",
    ],
}

GENERIC_NEIGHBORHOODS = [
    "Downtown",
    "Midtown",
    "Uptown",
    "North Side",
    "South Side",
    "East Side",
    "West Side",
    "City Center",
]

_METRO_TO_NEIGHBORHOOD_CITY = {
    "gta": "toronto",
    "nyc": "new york",
    "bay_area": "san francisco",
}


def _norm(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


@dataclass(frozen=True)
class CityEntry:
    name: str
    country_code: str
    state_code: str


@lru_cache(maxsize=1)
def _build_vocab_cache() -> Dict[str, object]:
    gc = geonamescache.GeonamesCache()

    us_states_raw = gc.get_us_states()
    us_states: Dict[str, str] = {code: data["name"] for code, data in us_states_raw.items()}

    states_by_country: Dict[str, Dict[str, str]] = {
        "US": dict(sorted(us_states.items())),
        "CA": dict(sorted(CA_PROVINCES.items())),
    }

    cities_raw = gc.get_cities()
    city_entries: List[CityEntry] = []
    by_country_state: Dict[Tuple[str, str], Dict[str, str]] = {}

    for city in cities_raw.values():
        country = city.get("countrycode")
        if country not in {"US", "CA"}:
            continue

        admin1 = (city.get("admin1code") or "").strip().upper()
        if not admin1:
            continue

        if country == "CA":
            state_code = CA_ADMIN1_TO_ABBR.get(admin1)
        else:
            state_code = admin1

        if not state_code:
            continue
        if state_code not in states_by_country.get(country, {}):
            continue

        city_name = (city.get("name") or "").strip()
        if not city_name:
            continue

        city_entries.append(CityEntry(name=city_name, country_code=country, state_code=state_code))
        by_country_state.setdefault((country, state_code), {})[_norm(city_name)] = city_name

    city_global_map: Dict[str, str] = {}
    for item in sorted(city_entries, key=lambda e: e.name):
        city_global_map.setdefault(_norm(item.name), item.name)

    return {
        "states_by_country": states_by_country,
        "city_entries": city_entries,
        "city_name_index": by_country_state,
        "city_global_map": city_global_map,
        "company_map": {_norm(v): v for v in COMPANY_OPTIONS},
        "school_map": {_norm(v): v for v in SCHOOL_OPTIONS},
        "role_map": {_norm(v): v for v in ROLE_OPTIONS},
    }


def list_countries() -> List[Dict[str, str]]:
    return [{"value": c["code"], "label": c["name"]} for c in COUNTRIES]


def list_states(country_code: str) -> List[Dict[str, str]]:
    cache = _build_vocab_cache()
    states = cache["states_by_country"].get((country_code or "").upper(), {})
    return [{"value": code, "label": name} for code, name in states.items()]


def search_cities(
    country_code: str,
    state_code: str,
    query: str = "",
    limit: int = 100,
) -> List[Dict[str, str]]:
    cache = _build_vocab_cache()
    cc = (country_code or "").upper()
    sc = (state_code or "").upper()
    q = _norm(query)

    entries = [
        c for c in cache["city_entries"]
        if c.country_code == cc and c.state_code == sc and (not q or q in _norm(c.name))
    ]
    # De-dup by city name and keep deterministic order.
    seen = set()
    out = []
    for item in sorted(entries, key=lambda e: e.name):
        if item.name in seen:
            continue
        seen.add(item.name)
        out.append({"value": item.name, "label": item.name})
        if len(out) >= limit:
            break
    return out


def search_cities_global(query: str = "", limit: int = 100) -> List[Dict[str, str]]:
    cache = _build_vocab_cache()
    q = _norm(query)
    names = sorted(cache["city_global_map"].values())
    filtered = [name for name in names if not q or q in _norm(name)]
    metros = get_metro_options(query=query)

    out: List[Dict[str, str]] = []
    seen = set()

    for option in metros + [{"value": name, "label": name} for name in filtered]:
        value = str(option.get("value") or "").strip()
        if not value:
            continue
        key = _norm(value)
        if key in seen:
            continue
        seen.add(key)
        out.append({"value": value, "label": str(option.get("label") or value)})
        if len(out) >= limit:
            break

    return out


def _neighborhood_city_key(city_name: str) -> str:
    metro = metro_option(city_name)
    if metro:
        return _METRO_TO_NEIGHBORHOOD_CITY.get(metro["id"], _norm(metro["value"]))
    return _norm(normalize_city_name(city_name))


def _city_from_active_listings(country_code: str, state_code: str, city_name: str) -> Optional[str]:
    """Resolve a city from active listings when controlled vocab misses it."""
    from app.dependencies.supabase import get_admin_client

    city_norm = normalize_city_name(city_name)
    if not city_norm:
        return None

    target_country = normalize_country(country_code)
    target_state = normalize_state(state_code)
    supabase = get_admin_client()

    rows = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            supabase.table("listings")
            .select("city, state_province, country")
            .eq("status", "active")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        page = resp.data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    for row in rows:
        if normalize_country(row.get("country", "")) != target_country:
            continue
        if normalize_state(row.get("state_province", "")) != target_state:
            continue
        raw_city = (row.get("city") or "").strip()
        if not raw_city:
            continue
        # Keep label consistent with dropdown options.
        db_city = raw_city.split(" (")[0].strip() if " (" in raw_city else raw_city
        if normalize_city_name(db_city) == city_norm:
            return db_city

    return None


def search_neighborhoods(city_name: str, query: str = "", limit: int = 200) -> List[Dict[str, str]]:
    city_key = _neighborhood_city_key(city_name)
    q = _norm(query)

    neighborhoods = CURATED_NEIGHBORHOODS.get(city_key, GENERIC_NEIGHBORHOODS)
    filtered = [name for name in neighborhoods if not q or q in _norm(name)]
    return [{"value": v, "label": v} for v in filtered[:limit]]


def validate_neighborhoods(city_name: str, neighborhoods: Optional[List[str]]) -> Optional[List[str]]:
    """
    Validate and canonicalize selected neighborhoods for a city.
    """
    if neighborhoods is None:
        return None
    if not isinstance(neighborhoods, list):
        raise ValueError("preferred_neighborhoods must be an array of options")
    if len(neighborhoods) == 0:
        return []
    if not city_name:
        raise ValueError("target_city is required when preferred_neighborhoods are provided")

    allowed_options = search_neighborhoods(city_name, query="", limit=500)
    allowed_map = {_norm(opt["value"]): opt["value"] for opt in allowed_options}

    canonical: List[str] = []
    seen = set()
    for value in neighborhoods:
        text = str(value or "").strip()
        if not text:
            continue
        mapped = allowed_map.get(_norm(text))
        if not mapped:
            raise ValueError(
                f"Neighborhood '{text}' is not valid for city '{city_name}'. Choose from predefined options."
            )
        if mapped in seen:
            continue
        seen.add(mapped)
        canonical.append(mapped)

    return canonical


def validate_location(country_code: str, state_code: str, city_name: str) -> Tuple[str, str, str]:
    cache = _build_vocab_cache()
    cc = (country_code or "").upper().strip()
    state_input = (state_code or "").strip()
    sc = state_input.upper()

    if cc not in {"US", "CA"}:
        raise ValueError("country_code must be one of: US, CA")

    states = cache["states_by_country"].get(cc, {})
    if sc not in states:
        state_input_norm = _norm(state_input)
        matched_code = next(
            (
                code
                for code, label in states.items()
                if _norm(code) == state_input_norm or _norm(label) == state_input_norm
            ),
            None,
        )
        if not matched_code:
            raise ValueError(f"state_code '{sc}' is not valid for country '{cc}'")
        sc = matched_code

    selected_metro = metro_option(city_name)
    if selected_metro:
        state_name = states.get(sc, "")
        cc_norm = normalize_country(cc)
        sc_norm = normalize_state(state_name)
        if cc_norm != selected_metro["country"] or sc_norm not in selected_metro["states"]:
            raise ValueError(
                f"city '{city_name}' is not valid for state '{sc}', country '{cc}'"
            )
        submitted_city = city_name.strip()
        return cc, sc, submitted_city or selected_metro["value"]

    city_map = cache["city_name_index"].get((cc, sc), {})
    canonical_city = city_map.get(_norm(city_name))
    if not canonical_city:
        metro_id = metro_for_city(city_name)
        if metro_id:
            allowed_metros = {
                metro_option_data["value"]
                for metro_option_data in get_metro_options(country_code=cc, state_code=sc)
            }
            metro_display = {
                "gta": "GTA",
                "nyc": "NYC",
                "bay_area": "Bay Area",
            }.get(metro_id)
            if metro_display in allowed_metros:
                return cc, sc, city_name.strip()

        try:
            listing_city = _city_from_active_listings(cc, sc, city_name)
            if listing_city:
                return cc, sc, listing_city
        except Exception:
            pass

        raise ValueError(f"city '{city_name}' is not valid for state '{sc}', country '{cc}'")

    return cc, sc, canonical_city


def validate_city_name(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError("target_city is required")
    selected_metro = metro_option(text)
    if selected_metro:
        return text
    mapped = _build_vocab_cache()["city_global_map"].get(_norm(text))
    if not mapped:
        raise ValueError("target_city must be selected from predefined city options")
    return mapped


def _search_catalog(options: List[str], query: str, limit: int) -> List[Dict[str, str]]:
    q = _norm(query)
    filtered = [opt for opt in options if not q or q in _norm(opt)]
    return [{"value": v, "label": v} for v in filtered[:limit]]


def search_companies(query: str = "", limit: int = 100) -> List[Dict[str, str]]:
    return _search_catalog(COMPANY_OPTIONS, query, limit)


def search_schools(query: str = "", limit: int = 100) -> List[Dict[str, str]]:
    return _search_catalog(SCHOOL_OPTIONS, query, limit)


def list_roles() -> List[Dict[str, str]]:
    return [{"value": v, "label": v} for v in ROLE_OPTIONS]


def validate_company(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    mapped = _build_vocab_cache()["company_map"].get(_norm(text))
    if not mapped:
        raise ValueError("company_name must be selected from predefined options")
    return mapped


def validate_school(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    mapped = _build_vocab_cache()["school_map"].get(_norm(text))
    if not mapped:
        raise ValueError("school_name must be selected from predefined options")
    return mapped


def validate_role_title(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    mapped = _build_vocab_cache()["role_map"].get(_norm(text))
    if not mapped:
        raise ValueError("role_title must be selected from predefined options")
    return mapped
