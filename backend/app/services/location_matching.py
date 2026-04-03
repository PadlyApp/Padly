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
    "sf bay area": "bay_area",
    "san francisco bay area": "bay_area",
}


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
    if " (" in city:
        city = city.split(" (", 1)[0].strip()
    city = _CITY_CANONICAL_ALIASES.get(city, city)
    return city


def metro_for_city(value: Any) -> Optional[str]:
    city = normalize_city_name(value)
    if not city:
        return None
    for metro, aliases in _METRO_ALIASES.items():
        if city in aliases:
            return metro
    return None


def cities_match(target_city: Any, listing_city: Any) -> bool:
    target = normalize_city_name(target_city)
    listing = normalize_city_name(listing_city)
    if not target or not listing:
        return True

    # If user picked a metro name (GTA, NYC, Bay Area), match all cities in that metro
    target_as_metro = _METRO_DISPLAY_NAMES.get(target)
    if target_as_metro:
        listing_metro = metro_for_city(listing)
        return listing_metro == target_as_metro

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
