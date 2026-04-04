"""
Controlled options routes.

Provides canonical dropdown/search values for location and profile fields.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.controlled_vocab import (
    list_countries,
    list_roles,
    list_states,
    search_cities,
    search_cities_global,
    search_neighborhoods,
    search_companies,
    search_schools,
)
from app.services.location_matching import get_metro_options

router = APIRouter(prefix="/api/options", tags=["options"])


def _norm(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _resolve_state_code(country_code: str, state_input: str) -> str:
    """Map incoming state/province value or label to canonical code when possible."""
    raw = (state_input or "").strip()
    if not raw:
        return raw

    states = list_states(country_code)
    raw_norm = _norm(raw)
    for state in states:
        value = (state.get("value") or "").strip()
        label = (state.get("label") or "").strip()
        if _norm(value) == raw_norm or _norm(label) == raw_norm:
            return value
    return raw


@router.get("/countries")
async def get_countries():
    return {"status": "success", "count": 2, "data": list_countries()}


@router.get("/states")
async def get_states(
    country_code: str = Query(..., min_length=2, max_length=2),
):
    """Return only states/provinces that have active listings in the DB."""
    from app.dependencies.supabase import get_admin_client
    from app.services.location_matching import normalize_country

    supabase = get_admin_client()
    target_country = normalize_country(country_code)

    try:
        # Paginate to get all listings
        rows = []
        page_size = 1000
        offset = 0
        while True:
            resp = supabase.table("listings").select("state_province, country").eq("status", "active").range(offset, offset + page_size - 1).execute()
            page = resp.data or []
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size

        # Get all states from controlled vocab for label lookup
        all_states = {s["value"]: s["label"] for s in list_states(country_code)}

        seen = set()
        states = []
        for row in rows:
            if normalize_country(row.get("country", "")) != target_country:
                continue
            code = (row.get("state_province") or "").strip()
            if not code or code.lower() in seen:
                continue
            seen.add(code.lower())
            label = all_states.get(code, code)
            states.append({"value": code, "label": label})

        states.sort(key=lambda x: x["label"])
        if not states:
            # Fallback to full list if DB query returns nothing
            states = list_states(country_code)
    except Exception:
        states = list_states(country_code)

    return {"status": "success", "count": len(states), "data": states}


@router.get("/cities")
async def get_cities(
    country_code: str = Query(..., min_length=2, max_length=2),
    state_code: str = Query(..., min_length=2, max_length=64),
    q: str = Query("", max_length=100),
    limit: int = Query(100, ge=1, le=500),
):
    """Return cities that have actual listings in the DB, filtered by country/state."""
    from app.dependencies.supabase import get_admin_client
    from app.services.location_matching import normalize_state, normalize_country

    supabase = get_admin_client()

    resolved_state_code = _resolve_state_code(country_code, state_code)

    # Map state_code to DB state values
    state_norm = normalize_state(state_code)
    try:
        # Paginate to get all listings (Supabase default page size is 1000)
        rows = []
        page_size = 1000
        offset = 0
        while True:
            resp = supabase.table("listings").select("city, state_province, country").eq("status", "active").range(offset, offset + page_size - 1).execute()
            page = resp.data or []
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
    except Exception:
        # Fallback to geonamescache if DB unavailable
        data = search_cities(country_code, resolved_state_code, q, limit)
        return {"status": "success", "count": len(data), "data": data}

    seen = set()
    cities = []
    for row in rows:
        db_country = normalize_country(row.get("country", ""))
        db_state = normalize_state(row.get("state_province", ""))
        target_country = normalize_country(country_code)

        if db_country != target_country:
            continue
        if db_state != state_norm:
            continue

        raw_city = row.get("city", "")
        # Strip sub-area suffixes like "Toronto (Malvern)" → "Toronto"
        city_label = raw_city.split(" (")[0].strip() if " (" in raw_city else raw_city
        if not city_label:
            continue
        key = city_label.lower()
        if key in seen:
            continue
        if q and q.lower() not in key:
            continue
        seen.add(key)
        cities.append({"value": city_label, "label": city_label})
        if len(cities) >= limit:
            break

    cities.sort(key=lambda x: x["label"])

    if not cities:
        # If no active listings match this location, keep the picker usable via controlled vocab.
        cities = search_cities(country_code, resolved_state_code, q, limit)

    # Prepend metro options at the top if they match this country/state
    metro_options = []
    if country_code.upper() == "CA" and normalize_state(state_code) == "ontario":
        metro_options.append({"value": "GTA", "label": "GTA (Greater Toronto Area)"})
    if country_code.upper() == "US" and normalize_state(state_code) == "new york":
        metro_options.append({"value": "NYC", "label": "NYC (New York City Metro)"})
    if country_code.upper() == "US" and normalize_state(state_code) == "california":
        metro_options.append({"value": "Bay Area", "label": "Bay Area (San Francisco Metro)"})

    if q:
        metro_options = [m for m in metro_options if q.lower() in m["label"].lower()]

    cities = metro_options + cities
    return {"status": "success", "count": len(cities), "data": cities}


@router.get("/cities-global")
async def get_cities_global(
    q: str = Query("", max_length=100),
    limit: int = Query(200, ge=1, le=500),
):
    data = search_cities_global(q, limit)
    return {"status": "success", "count": len(data), "data": data}


@router.get("/neighborhoods")
async def get_neighborhoods(
    city: str = Query(..., min_length=1, max_length=100),
    q: str = Query("", max_length=100),
    limit: int = Query(200, ge=1, le=500),
):
    data = search_neighborhoods(city, q, limit)
    return {"status": "success", "count": len(data), "data": data}


@router.get("/companies")
async def get_companies(
    q: str = Query("", max_length=100),
    limit: int = Query(100, ge=1, le=500),
):
    data = search_companies(q, limit)
    return {"status": "success", "count": len(data), "data": data}


@router.get("/schools")
async def get_schools(
    q: str = Query("", max_length=100),
    limit: int = Query(100, ge=1, le=500),
):
    data = search_schools(q, limit)
    return {"status": "success", "count": len(data), "data": data}


@router.get("/roles")
async def get_roles():
    data = list_roles()
    return {"status": "success", "count": len(data), "data": data}
