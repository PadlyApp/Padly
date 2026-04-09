"""Group save/unsave operations and group-liked-listings retrieval."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.auth import require_user_token
from app.dependencies.supabase import get_admin_client
from app.services.auth_helpers import resolve_current_user_id, require_group_membership

router = APIRouter()


@router.get("/swipes/groups/{group_id}/liked")
async def get_group_liked_listings(
    group_id: str,
    limit: int = Query(100, ge=1, le=500),
    action: Optional[str] = Query(None, description="Filter by action: 'like', 'group_save', or omit for both"),
    token: str = Depends(require_user_token),
):
    """Return listings interacted with by any accepted member of the group."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)
    require_group_membership(group_id=group_id, user_id=user_id)

    try:
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
        swipes = []
        for s in raw_swipes:
            if s.get("action") == "like":
                swipes.append(s)
            elif s.get("action") == "group_save" and s.get("group_id_at_time") == group_id:
                swipes.append(s)
        if not swipes:
            return {"status": "success", "data": []}

        liked_by: dict = {}
        for s in swipes:
            lid = s["listing_id"]
            name = member_map.get(s["actor_user_id"], "Member")
            liked_by.setdefault(lid, [])
            if name not in liked_by[lid]:
                liked_by[lid].append(name)

        unique_listing_ids = list(liked_by.keys())
        listings_resp = (
            supabase.table("listings").select("*").in_("id", unique_listing_ids).execute()
        )
        listing_map = {str(l["id"]): l for l in (listings_resp.data or [])}

        result = []
        for lid in unique_listing_ids:
            listing = listing_map.get(str(lid))
            if listing:
                result.append({**listing, "liked_by": liked_by[lid]})

        return {"status": "success", "data": result}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(status_code=503, detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to fetch group liked listings: {e}")


@router.post("/swipes/groups/{group_id}/save/{listing_id}")
async def save_listing_to_group(
    group_id: str, listing_id: str, token: str = Depends(require_user_token)
):
    """Save a listing to the group."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)
    require_group_membership(group_id=group_id, user_id=user_id)

    try:
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
    group_id: str, listing_id: str, token: str = Depends(require_user_token)
):
    """Remove a group-saved listing."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)
    require_group_membership(group_id=group_id, user_id=user_id)

    try:
        supabase.table("swipe_interactions").delete().eq(
            "actor_user_id", user_id
        ).eq("listing_id", listing_id).eq("action", "group_save").execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unsave listing: {e}")


@router.get("/swipes/groups/{group_id}/saved")
async def get_my_saved_listings_for_group(
    group_id: str, token: str = Depends(require_user_token)
):
    """Return listing IDs the current user has starred for this group."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)
    require_group_membership(group_id=group_id, user_id=user_id)

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
