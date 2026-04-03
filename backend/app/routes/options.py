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

router = APIRouter(prefix="/api/options", tags=["options"])


@router.get("/countries")
async def get_countries():
    return {"status": "success", "count": 2, "data": list_countries()}


@router.get("/states")
async def get_states(
    country_code: str = Query(..., min_length=2, max_length=2),
):
    data = list_states(country_code)
    if not data:
        raise HTTPException(status_code=400, detail="Unsupported country_code. Use US or CA.")
    return {"status": "success", "count": len(data), "data": data}


@router.get("/cities")
async def get_cities(
    country_code: str = Query(..., min_length=2, max_length=2),
    state_code: str = Query(..., min_length=2, max_length=3),
    q: str = Query("", max_length=100),
    limit: int = Query(100, ge=1, le=500),
):
    """Return cities that have actual listings in the DB, filtered by country/state."""
    from app.dependencies.supabase import get_admin_client
    from app.services.location_matching import normalize_state, normalize_country

    supabase = get_admin_client()

    # Map country_code to DB country values
    country_map = {"US": ["usa", "us", "united states"], "CA": ["canada", "ca", "can"]}
    db_countries = country_map.get(country_code.upper(), [country_code.lower()])

    # Map state_code to DB state values
    state_norm = normalize_state(state_code)
    try:
        resp = supabase.table("listings").select("city, state_province, country").eq("status", "active").execute()
        rows = resp.data or []
    except Exception:
        # Fallback to geonamescache if DB unavailable
        data = search_cities(country_code, state_code, q, limit)
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
