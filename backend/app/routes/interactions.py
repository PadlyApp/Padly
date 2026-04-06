"""
Interactions routes

Phase 1 endpoint(s) for swipe event capture from Discover.
"""

from __future__ import annotations

from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dependencies.auth import require_user_token
from app.dependencies.supabase import get_admin_client
from app.services.behavior_features import (
    build_group_behavior_vector,
    build_user_behavior_vector,
    get_swipe_health_summary,
)

router = APIRouter(prefix="/api/interactions", tags=["interactions"])


class SwipeEventCreate(BaseModel):
    listing_id: str
    action: Literal["like", "pass", "super_like"]
    group_id_at_time: Optional[str] = None
    surface: str = Field(default="discover", min_length=1, max_length=100)
    session_id: str = Field(..., min_length=1, max_length=128)
    position_in_feed: int = Field(default=0, ge=0)
    algorithm_version: str = Field(..., min_length=1, max_length=100)
    model_version: Optional[str] = Field(default=None, max_length=100)
    city_filter: Optional[str] = Field(default=None, max_length=100)
    preference_snapshot_hash: Optional[str] = Field(default=None, max_length=128)
    latency_ms: Optional[int] = Field(default=None, ge=0)


def _resolve_current_user_id(token: str) -> str:
    """
    Resolve authenticated user to internal users.id UUID.
    """
    supabase = get_admin_client()

    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    auth_user_id = user_response.user.id

    # Preferred mapping: users.auth_id == auth user id.
    user_record = supabase.table("users").select("id").eq("auth_id", auth_user_id).limit(1).execute()
    if user_record.data:
        return user_record.data[0]["id"]

    # Fallback for legacy rows where users.id may equal auth user id.
    fallback_record = supabase.table("users").select("id").eq("id", auth_user_id).limit(1).execute()
    if fallback_record.data:
        return fallback_record.data[0]["id"]

    raise HTTPException(status_code=404, detail="User profile not found")


def _require_group_membership(group_id: str, user_id: str) -> None:
    """
    Require that user is an accepted member of the target group.
    """
    supabase = get_admin_client()
    membership = (
        supabase.table("group_members")
        .select("group_id")
        .eq("group_id", group_id)
        .eq("user_id", user_id)
        .eq("status", "accepted")
        .limit(1)
        .execute()
    )
    if not membership.data:
        raise HTTPException(status_code=403, detail="You are not a member of this group")


@router.post("/swipes")
async def create_swipe_event(
    payload: SwipeEventCreate,
    token: str = Depends(require_user_token),
):
    """
    Persist a single swipe event from Discover.

    This endpoint is idempotent per:
    actor_user_id + listing_id + session_id + position_in_feed
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        existing = (
            supabase.table("swipe_interactions")
            .select("event_id")
            .eq("actor_user_id", user_id)
            .eq("listing_id", payload.listing_id)
            .eq("session_id", payload.session_id)
            .eq("position_in_feed", payload.position_in_feed)
            .limit(1)
            .execute()
        )
        if existing.data:
            return {
                "status": "success",
                "duplicate_ignored": True,
                "event_id": existing.data[0]["event_id"],
            }

        insert_data = {
            "actor_type": "user",
            "actor_user_id": user_id,
            "group_id_at_time": payload.group_id_at_time,
            "listing_id": payload.listing_id,
            "action": payload.action,
            "surface": payload.surface,
            "session_id": payload.session_id,
            "position_in_feed": payload.position_in_feed,
            "algorithm_version": payload.algorithm_version,
            "model_version": payload.model_version,
            "city_filter": payload.city_filter,
            "preference_snapshot_hash": payload.preference_snapshot_hash,
            "latency_ms": payload.latency_ms,
        }

        created = supabase.table("swipe_interactions").insert(insert_data).execute()
        if not created.data:
            raise HTTPException(status_code=500, detail="Swipe event was not persisted")

        return {
            "status": "success",
            "duplicate_ignored": False,
            "event_id": created.data[0]["event_id"],
        }
    except HTTPException:
        raise
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        if "duplicate key value violates unique constraint" in err:
            # Edge race between duplicate check and insert.
            existing = (
                supabase.table("swipe_interactions")
                .select("event_id")
                .eq("actor_user_id", user_id)
                .eq("listing_id", payload.listing_id)
                .eq("session_id", payload.session_id)
                .eq("position_in_feed", payload.position_in_feed)
                .limit(1)
                .execute()
            )
            return {
                "status": "success",
                "duplicate_ignored": True,
                "event_id": existing.data[0]["event_id"] if existing.data else None,
            }
        raise HTTPException(status_code=500, detail=f"Failed to store swipe event: {e}")


@router.get("/swipes/me")
async def get_my_swipe_events(
    limit: int = Query(50, ge=1, le=500),
    token: str = Depends(require_user_token),
):
    """
    Return recent swipe events for the current user (debug/inspection endpoint).
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        response = (
            supabase.table("swipe_interactions")
            .select("*")
            .eq("actor_user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        events = response.data or []
        return {"status": "success", "count": len(events), "data": events}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to fetch swipe events: {e}")


@router.get("/behavior/me")
async def get_my_behavior_vector(
    days: int = Query(180, ge=7, le=365),
    max_events: int = Query(2000, ge=100, le=10000),
    token: str = Depends(require_user_token),
):
    """
    Return Phase 2A behavior vector for the authenticated user.
    """
    user_id = _resolve_current_user_id(token)
    try:
        vector = build_user_behavior_vector(user_id=user_id, days=days, max_events=max_events)
        return {"status": "success", "data": vector}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to build user behavior vector: {e}")


@router.get("/behavior/groups/{group_id}")
async def get_group_behavior(
    group_id: str,
    days: int = Query(180, ge=7, le=365),
    max_events_per_user: int = Query(2000, ge=100, le=10000),
    token: str = Depends(require_user_token),
):
    """
    Return Phase 2A behavior vector for a group.
    Access is limited to accepted group members.
    """
    user_id = _resolve_current_user_id(token)
    _require_group_membership(group_id=group_id, user_id=user_id)
    try:
        vector = build_group_behavior_vector(
            group_id=group_id,
            days=days,
            max_events_per_user=max_events_per_user,
        )
        return {"status": "success", "data": vector}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to build group behavior vector: {e}")


@router.get("/swipes/groups/{group_id}/liked")
async def get_group_liked_listings(
    group_id: str,
    limit: int = Query(100, ge=1, le=500),
    action: Optional[str] = Query(None, description="Filter by action: 'like', 'group_save', or omit for both"),
    token: str = Depends(require_user_token),
):
    """
    Return listings interacted with by any accepted member of the group.
    Pass ?action=group_save to see only group-saved listings.
    Pass ?action=like to see only individually liked listings.
    Omit action to see both.
    Each item includes listing data plus a list of member names who saved/liked it.
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    _require_group_membership(group_id=group_id, user_id=user_id)

    try:
        # Get all accepted member user IDs
        members_resp = (
            supabase.table("group_members")
            .select("user_id")
            .eq("group_id", group_id)
            .eq("status", "accepted")
            .execute()
        )
        members = members_resp.data or []
        if not members:
            return {"status": "success", "data": []}

        member_ids = [m["user_id"] for m in members]

        # Fetch user details separately
        users_resp = (
            supabase.table("users")
            .select("id, full_name, email")
            .in_("id", member_ids)
            .execute()
        )
        member_map = {
            u["id"]: u.get("full_name") or u.get("email", "Member")
            for u in (users_resp.data or [])
        }

        # Determine which actions to fetch based on the optional filter param.
        if action == "group_save":
            actions_to_fetch = ["group_save"]
        elif action == "like":
            actions_to_fetch = ["like"]
        else:
            actions_to_fetch = ["like", "group_save"]

        swipes_resp = (
            supabase.table("swipe_interactions")
            .select("listing_id, actor_user_id, action, group_id_at_time")
            .in_("actor_user_id", member_ids)
            .in_("action", actions_to_fetch)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        raw_swipes = swipes_resp.data or []
        # group_save rows must belong to this specific group; likes are group-agnostic.
        swipes = []
        for s in raw_swipes:
            if s.get("action") == "like":
                swipes.append(s)
            elif s.get("action") == "group_save" and s.get("group_id_at_time") == group_id:
                swipes.append(s)
        if not swipes:
            return {"status": "success", "data": []}

        # Build mapping: listing_id -> list of member names who liked it
        liked_by: dict = {}
        for s in swipes:
            lid = s["listing_id"]
            name = member_map.get(s["actor_user_id"], "Member")
            liked_by.setdefault(lid, [])
            if name not in liked_by[lid]:
                liked_by[lid].append(name)

        unique_listing_ids = list(liked_by.keys())

        # Fetch listing details
        listings_resp = (
            supabase.table("listings")
            .select("*")
            .in_("id", unique_listing_ids)
            .execute()
        )
        listings = listings_resp.data or []
        listing_map = {str(l["id"]): l for l in listings}

        result = []
        for lid in unique_listing_ids:
            listing = listing_map.get(str(lid))
            if listing:
                result.append({**listing, "liked_by": liked_by[lid]})

        return {"status": "success", "data": result}

    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to fetch group liked listings: {e}")


@router.post("/swipes/groups/{group_id}/save/{listing_id}")
async def save_listing_to_group(
    group_id: str,
    listing_id: str,
    token: str = Depends(require_user_token),
):
    """Save a listing to the group (star/bookmark action from Discover)."""
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    _require_group_membership(group_id=group_id, user_id=user_id)

    try:
        # Delete any existing group_save for this user+listing+group, then insert fresh
        supabase.table("swipe_interactions").delete().eq(
            "actor_user_id", user_id
        ).eq("listing_id", listing_id).eq("action", "group_save").eq(
            "group_id_at_time", group_id
        ).execute()

        supabase.table("swipe_interactions").insert({
            "actor_user_id": user_id,
            "listing_id": listing_id,
            "action": "group_save",
            "group_id_at_time": group_id,
            "surface": "matches",
            "session_id": f"group-save-{user_id}-{group_id}-{listing_id}",
            "algorithm_version": "group-save-v1",
            "position_in_feed": 0,
        }).execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save listing: {e}")


@router.delete("/swipes/groups/{group_id}/save/{listing_id}")
async def unsave_listing_from_group(
    group_id: str,
    listing_id: str,
    token: str = Depends(require_user_token),
):
    """Remove a group-saved listing."""
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    _require_group_membership(group_id=group_id, user_id=user_id)

    try:
        supabase.table("swipe_interactions").delete().eq(
            "actor_user_id", user_id
        ).eq("listing_id", listing_id).eq("action", "group_save").execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unsave listing: {e}")


@router.get("/swipes/groups/{group_id}/saved")
async def get_my_saved_listings_for_group(
    group_id: str,
    token: str = Depends(require_user_token),
):
    """Return listing IDs the current user has starred for this group."""
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    _require_group_membership(group_id=group_id, user_id=user_id)

    try:
        resp = (
            supabase.table("swipe_interactions")
            .select("listing_id")
            .eq("actor_user_id", user_id)
            .eq("group_id_at_time", group_id)
            .eq("action", "group_save")
            .execute()
        )
        ids = [r["listing_id"] for r in (resp.data or [])]
        return {"status": "success", "saved_listing_ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch saved listings: {e}")


@router.get("/behavior/health")
async def get_behavior_health(
    days: int = Query(7, ge=1, le=90),
    max_events: int = Query(10000, ge=500, le=100000),
    token: str = Depends(require_user_token),
):
    """
    Return event quality and freshness summary for swipe interactions.
    """
    _ = _resolve_current_user_id(token)
    try:
        summary = get_swipe_health_summary(days=days, max_events=max_events)
        return {"status": "success", "data": summary}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to build behavior health summary: {e}")
