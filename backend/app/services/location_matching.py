"""
Shared location normalization and metro-aware matching helpers.

Padly inventory now spans broader metros like the GTA, NYC boroughs, and the Bay Area.
These helpers keep recommendation and group-matching logic aligned so nearby submarkets
are not excluded by exact string comparisons.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


_STATE_ALIASES = {
    "on": "ontario",
    "ontario": "ontario",
    "bc": "british columbia",
    "british columbia": "british columbia",
    "ny": "new york",
    "new york": "new york",
    "ca": "california",
    "california": "california",
}

_COUNTRY_ALIASES = {
    "us": "us",
    "usa": "us",
    "united states": "us",
    "united states of america": "us",
    "ca": "ca",
    "can": "ca",
    "canada": "ca",
}

_METRO_ALIASES = {
    "gta": {
        "gta",
        "greater toronto area",
        "greater toronto",
        "toronto",
        "downtown toronto",
        "north york",
        "scarborough",
        "etobicoke",
        "mississauga",
        "vaughan",
        "markham",
        "richmond hill",
        "brampton",
        "oakville",
        "milton",
        "ajax",
        "pickering",
        "whitby",
        "oshawa",
    },
    "nyc": {
        "nyc",
        "new york",
        "new york city",
        "manhattan",
        "brooklyn",
        "queens",
        "bronx",
        "staten island",
        "astoria",
        "long island city",
        "ridgewood",
        "flushing",
        "jamaica",
        "east elmhurst",
    },
    "bay_area": {
        "bay area",
        "san francisco bay area",
        "sf bay area",
        "sf",
        "san francisco",
        "oakland",
        "berkeley",
        "san jose",
        "fremont",
        "palo alto",
        "mountain view",
        "sunnyvale",
        "santa clara",
        "redwood city",
        "san mateo",
        "daly city",
        "south san francisco",
        "emeryville",
        "alameda",
        # East Bay
        "hayward",
        "richmond",
        "san leandro",
        "castro valley",
        "union city",
        "newark",
        "san lorenzo",
        "san pablo",
        "el cerrito",
        "albany",
        "pinole",
        "hercules",
        "rodeo",
        "concord",
        "walnut creek",
        "pleasant hill",
        "martinez",
        "antioch",
        "pittsburg",
        "brentwood",
        "oakley",
        "danville",
        "san ramon",
        "dublin",
        "pleasanton",
        "livermore",
        # Peninsula / South Bay
        "milpitas",
        "cupertino",
        "campbell",
        "los gatos",
        "saratoga",
        "los altos",
        "los altos hills",
        "monte sereno",
        "morgan hill",
        "gilroy",
        "menlo park",
        "atherton",
        "portola valley",
        "woodside",
        "foster city",
        "san carlos",
        "belmont",
        "burlingame",
        "millbrae",
        "san bruno",
        "pacifica",
        "half moon bay",
        # North Bay
        "marin",
        "san rafael",
        "novato",
        "san anselmo",
        "fairfax",
        "corte madera",
        "mill valley",
        "tiburon",
        "sausalito",
        "petaluma",
        "santa rosa",
        "rohnert park",
        "napa",
        "vallejo",
        "benicia",
        "fairfield",
        "vacaville",
    },
}

_CITY_CANONICAL_ALIASES = {
    "sf": "san francisco",
    "san fran": "san francisco",
    "nyc": "new york",
    "new york city": "new york",
}

# Metro display names that users can pick — treated as "show entire metro"
_METRO_DISPLAY_NAMES = {
    "gta": "gta",
    "greater toronto area": "gta",
    "nyc": "nyc",
    "new york city metro": "nyc",
    "bay area": "bay_area",
    "south bay": "bay_area",
    "south bay area": "bay_area",
    "silicon valley": "bay_area",
    "silicon valley metro": "bay_area",
    "sf bay area": "bay_area",
    "san francisco bay area": "bay_area",
}

_METRO_CATALOG = (
    {
        "id": "gta",
        "value": "GTA",
        "label": "GTA (Greater Toronto Area)",
        "country": "ca",
        "states": {"ontario"},
    },
    {
        "id": "nyc",
        "value": "NYC",
        "label": "NYC (New York City Metro)",
        "country": "us",
        "states": {"new york"},
    },
    {
        "id": "bay_area",
        "value": "Bay Area",
        "label": "Bay Area (San Francisco Metro)",
        "country": "us",
        "states": {"california"},
    },
)

_METRO_BY_ID = {m["id"]: m for m in _METRO_CATALOG}

for metro in _METRO_CATALOG:
    value_key = re.sub(r"\s+", " ", metro["value"].strip().lower())
    label_key = re.sub(r"\s+", " ", metro["label"].strip().lower())
    _METRO_DISPLAY_NAMES[value_key] = metro["id"]
    _METRO_DISPLAY_NAMES[label_key] = metro["id"]


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_country(value: Any) -> str:
    return _COUNTRY_ALIASES.get(normalize_text(value), normalize_text(value))


def normalize_state(value: Any) -> str:
    return _STATE_ALIASES.get(normalize_text(value), normalize_text(value))


def normalize_city_name(value: Any) -> str:
    city = normalize_text(value)
    if not city:
        return ""
    # Strip " (..." parenthetical suffix — e.g. "San Francisco (CA)" → "San Francisco"
    if " (" in city:
        city = city.split(" (", 1)[0].strip()
    # Strip everything after the first comma — handles ", CA", ", ON", ", California", etc.
    # e.g. "San Francisco, CA" → "San Francisco", "San Jose, California" → "San Jose"
    if "," in city:
        city = city.split(",", 1)[0].strip()
    city = _CITY_CANONICAL_ALIASES.get(city, city)
    return city


def metro_id_for_city(value: Any) -> Optional[str]:
    raw = normalize_text(value)
    if not raw:
        return None
    if " (" in raw:
        raw = raw.split(" (", 1)[0].strip()

    direct = _METRO_DISPLAY_NAMES.get(raw)
    if direct:
        return direct
    city = normalize_city_name(value)
    direct = _METRO_DISPLAY_NAMES.get(city)
    if direct:
        return direct
    return None


def is_metro_city(value: Any) -> bool:
    return metro_id_for_city(value) is not None


def metro_option(value: Any) -> Optional[Dict[str, Any]]:
    metro_id = metro_id_for_city(value)
    if not metro_id:
        return None
    metro = _METRO_BY_ID.get(metro_id)
    if not metro:
        return None
    return {
        "id": metro["id"],
        "value": metro["value"],
        "label": metro["label"],
        "country": metro["country"],
        "states": set(metro["states"]),
    }


def get_metro_options(
    *,
    country_code: Any = None,
    state_code: Any = None,
    query: str = "",
) -> List[Dict[str, str]]:
    cc = normalize_country(country_code) if country_code is not None else ""
    sc = normalize_state(state_code) if state_code is not None else ""
    q = normalize_text(query)

    out: List[Dict[str, str]] = []
    for metro in _METRO_CATALOG:
        if cc and metro["country"] != cc:
            continue
        if sc and sc not in metro["states"]:
            continue
        if q and q not in normalize_text(metro["value"]) and q not in normalize_text(metro["label"]):
            continue
        out.append({"value": metro["value"], "label": metro["label"]})
    return out


def metro_for_city(value: Any) -> Optional[str]:
    city = normalize_city_name(value)
    if not city:
        return None
    as_metro = _METRO_DISPLAY_NAMES.get(city)
    if as_metro:
        return as_metro
    for metro, aliases in _METRO_ALIASES.items():
        if city in aliases:
            return metro
    return None


def explicit_metro_id(value: Any) -> Optional[str]:
    raw = normalize_text(value)
    if not raw:
        return None
    if " (" in raw:
        raw = raw.split(" (", 1)[0].strip()
    if "," in raw:
        raw = raw.split(",", 1)[0].strip()
    return _METRO_DISPLAY_NAMES.get(raw)


def cities_match(target_city: Any, listing_city: Any) -> bool:
    target = normalize_city_name(target_city)
    listing = normalize_city_name(listing_city)
    if not target or not listing:
        return True

    target_as_explicit_metro = explicit_metro_id(target_city)
    if target_as_explicit_metro:
        listing_as_metro = metro_for_city(listing)
        return listing_as_metro == target_as_explicit_metro

    # Otherwise strict exact match only
    return target == listing


def locations_match(
    *,
    target_city: Any,
    listing_city: Any,
    target_state: Any = None,
    listing_state: Any = None,
    target_country: Any = None,
    listing_country: Any = None,
) -> bool:
    if not cities_match(target_city, listing_city):
        return False

    target_state_norm = normalize_state(target_state)
    listing_state_norm = normalize_state(listing_state)
    if target_state_norm and listing_state_norm and target_state_norm != listing_state_norm:
        return False

    target_country_norm = normalize_country(target_country)
    listing_country_norm = normalize_country(listing_country)
    if target_country_norm and listing_country_norm and target_country_norm != listing_country_norm:
        return False

    return True


def filter_listings_for_location(
    listings: Iterable[Dict[str, Any]],
    *,
    target_city: Any,
    target_state: Any = None,
    target_country: Any = None,
) -> List[Dict[str, Any]]:
    return [
        listing
        for listing in listings
        if locations_match(
            target_city=target_city,
            listing_city=listing.get("city"),
            target_state=target_state,
            listing_state=listing.get("state_province"),
            target_country=target_country,
            listing_country=listing.get("country"),
        )
    ]
