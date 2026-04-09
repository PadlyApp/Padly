"""Analytics / data-logging endpoints (swipe context, listing views, page views, search queries).

All four are best-effort: failures return 500 but callers should fire-and-forget.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dependencies.auth import get_user_token, require_user_token
from app.dependencies.supabase import get_admin_client
from app.services.auth_helpers import resolve_current_user_id
from app.services.behavior_features import (
    build_group_behavior_vector,
    build_user_behavior_vector,
    get_swipe_health_summary,
)
from app.services.auth_helpers import require_group_membership

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SwipeContextEventCreate(BaseModel):
    listing_id: str
    action: Literal["like", "pass", "super_like", "group_save"]
    session_id: str = Field(..., min_length=1, max_length=128)
    active_filters_snapshot: Optional[Dict[str, Any]] = None
    device_context: Optional[Dict[str, Any]] = None


class ListingViewEventCreate(BaseModel):
    listing_id: str
    surface: Literal["discover_card", "listing_detail", "matches_card"]
    session_id: str = Field(..., min_length=1, max_length=128)
    view_duration_ms: Optional[int] = Field(default=None, ge=0)
    expanded: bool = False
    photos_viewed_count: int = Field(default=0, ge=0)


class PageViewEventCreate(BaseModel):
    page: Literal[
        "discover", "matches", "listing_detail", "preferences",
        "account", "groups", "roommates", "onboarding",
    ]
    session_id: str = Field(..., min_length=1, max_length=128)
    duration_ms: Optional[int] = Field(default=None, ge=0)
    referrer_page: Optional[str] = Field(default=None, max_length=100)


class SearchQueryEventCreate(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    filter_snapshot: Dict[str, Any]
    results_returned: int = Field(default=0, ge=0)
    offset: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Behavior vectors
# ---------------------------------------------------------------------------

@router.get("/behavior/me")
async def get_my_behavior_vector(
    days: int = Query(180, ge=7, le=365),
    max_events: int = Query(2000, ge=100, le=10000),
    token: str = Depends(require_user_token),
):
    """Return Phase 2A behavior vector for the authenticated user."""
    user_id = resolve_current_user_id(token)
    try:
        vector = build_user_behavior_vector(user_id=user_id, days=days, max_events=max_events)
        return {"status": "success", "data": vector}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(status_code=503, detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to build user behavior vector: {e}")


@router.get("/behavior/groups/{group_id}")
async def get_group_behavior(
    group_id: str,
    days: int = Query(180, ge=7, le=365),
    max_events_per_user: int = Query(2000, ge=100, le=10000),
    token: str = Depends(require_user_token),
):
    """Return Phase 2A behavior vector for a group (members only)."""
    user_id = resolve_current_user_id(token)
    require_group_membership(group_id=group_id, user_id=user_id)
    try:
        vector = build_group_behavior_vector(group_id=group_id, days=days, max_events_per_user=max_events_per_user)
        return {"status": "success", "data": vector}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(status_code=503, detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to build group behavior vector: {e}")


@router.get("/behavior/health")
async def get_behavior_health(
    days: int = Query(7, ge=1, le=90),
    max_events: int = Query(10000, ge=500, le=100000),
    token: str = Depends(require_user_token),
):
    """Return event quality and freshness summary for swipe interactions."""
    _ = resolve_current_user_id(token)
    try:
        summary = get_swipe_health_summary(days=days, max_events=max_events)
        return {"status": "success", "data": summary}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(status_code=503, detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to build behavior health summary: {e}")


# ---------------------------------------------------------------------------
# Data-logging endpoints
# ---------------------------------------------------------------------------

def _try_resolve_user(token: Optional[str]):
    """Best-effort user resolution; returns None when no valid session."""
    if not token:
        return None
    try:
        return resolve_current_user_id(token)
    except Exception:
        return None


@router.post("/swipe-context")
async def create_swipe_context_event(
    payload: SwipeContextEventCreate,
    token: Optional[str] = Depends(get_user_token),
):
    """Persist filter + device context alongside a swipe (optional auth)."""
    user_id = _try_resolve_user(token)
    if user_id is None:
        return {"status": "skipped"}

    supabase = get_admin_client()
    try:
        insert_data = {
            "actor_user_id": user_id,
            "listing_id": payload.listing_id,
            "session_id": payload.session_id,
            "action": payload.action,
            "active_filters_snapshot": payload.active_filters_snapshot,
            "device_context": payload.device_context,
        }
        created = supabase.table("swipe_context_events").insert(insert_data).execute()
        if not created.data:
            raise HTTPException(status_code=500, detail="Swipe context event was not persisted")
        return {"status": "success", "event_id": created.data[0]["event_id"]}
    except HTTPException:
        raise
    except Exception as e:
        err = str(e).lower()
        if "swipe_context_events" in err and "does not exist" in err:
            raise HTTPException(status_code=503, detail="swipe_context_events table not found. Run migration 012.")
        raise HTTPException(status_code=500, detail=f"Failed to store swipe context: {e}")


@router.post("/listing-views")
async def create_listing_view_event(
    payload: ListingViewEventCreate,
    token: Optional[str] = Depends(get_user_token),
):
    """Persist a listing view duration event (optional auth)."""
    user_id = _try_resolve_user(token)
    if user_id is None:
        return {"status": "skipped"}

    supabase = get_admin_client()
    try:
        created = supabase.table("listing_view_events").insert({
            "user_id": user_id,
            "listing_id": payload.listing_id,
            "surface": payload.surface,
            "session_id": payload.session_id,
            "view_duration_ms": payload.view_duration_ms,
            "expanded": payload.expanded,
            "photos_viewed_count": payload.photos_viewed_count,
        }).execute()
        if not created.data:
            raise HTTPException(status_code=500, detail="Listing view event was not persisted")
        return {"status": "success", "event_id": created.data[0]["event_id"]}
    except HTTPException:
        raise
    except Exception as e:
        err = str(e).lower()
        if "listing_view_events" in err and "does not exist" in err:
            raise HTTPException(status_code=503, detail="listing_view_events table not found. Run migration 014.")
        raise HTTPException(status_code=500, detail=f"Failed to store listing view event: {e}")


@router.post("/page-views")
async def create_page_view_event(
    payload: PageViewEventCreate,
    token: Optional[str] = Depends(get_user_token),
):
    """Persist a page view event for funnel analytics (optional auth)."""
    user_id = _try_resolve_user(token)
    if user_id is None:
        return {"status": "skipped"}

    supabase = get_admin_client()
    try:
        created = supabase.table("page_view_events").insert({
            "user_id": user_id,
            "page": payload.page,
            "session_id": payload.session_id,
            "duration_ms": payload.duration_ms,
            "referrer_page": payload.referrer_page,
        }).execute()
        if not created.data:
            raise HTTPException(status_code=500, detail="Page view event was not persisted")
        return {"status": "success", "event_id": created.data[0]["event_id"]}
    except HTTPException:
        raise
    except Exception as e:
        err = str(e).lower()
        if "page_view_events" in err and "does not exist" in err:
            raise HTTPException(status_code=503, detail="page_view_events table not found. Run migration 016.")
        raise HTTPException(status_code=500, detail=f"Failed to store page view event: {e}")


@router.post("/search-queries")
async def create_search_query_event(
    payload: SearchQueryEventCreate,
    token: Optional[str] = Depends(get_user_token),
):
    """Persist a search/filter event for demand intelligence (optional auth)."""
    user_id = _try_resolve_user(token)
    if user_id is None:
        return {"status": "skipped"}

    supabase = get_admin_client()
    try:
        created = supabase.table("search_query_events").insert({
            "user_id": user_id,
            "session_id": payload.session_id,
            "filter_snapshot": payload.filter_snapshot,
            "results_returned": payload.results_returned,
            "offset": payload.offset,
        }).execute()
        if not created.data:
            raise HTTPException(status_code=500, detail="Search query event was not persisted")
        return {"status": "success", "event_id": created.data[0]["event_id"]}
    except HTTPException:
        raise
    except Exception as e:
        err = str(e).lower()
        if "search_query_events" in err and "does not exist" in err:
            raise HTTPException(status_code=503, detail="search_query_events table not found. Run migration 018.")
        raise HTTPException(status_code=500, detail=f"Failed to store search query event: {e}")
