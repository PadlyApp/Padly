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
    data = search_cities(country_code, state_code, q, limit)
    return {"status": "success", "count": len(data), "data": data}


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
