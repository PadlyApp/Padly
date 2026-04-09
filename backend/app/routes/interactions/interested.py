"""User interested-listings: mark, unmark, list."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth import require_user_token
from app.dependencies.supabase import get_admin_client
from app.services.auth_helpers import resolve_current_user_id
from app.services.listing_payloads import hydrate_listing_images

from ._helpers import interested_storage_missing

router = APIRouter()


class InterestedListingCreate(BaseModel):
    source: Optional[str] = Field(default=None, max_length=100)


@router.get("/interested-listings")
async def get_my_interested_listings(token: str = Depends(require_user_token)):
    """Return the current user's interested listings with listing payloads."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)

    try:
        rows_resp = (
            supabase.table("user_interested_listings")
            .select("listing_id, source, created_at")
            .eq("actor_user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = rows_resp.data or []
        if not rows:
            return {"status": "success", "data": []}

        listing_ids: list[str] = []
        seen: set[str] = set()
        for row in rows:
            listing_id = str(row.get("listing_id") or "").strip()
            if listing_id and listing_id not in seen:
                seen.add(listing_id)
                listing_ids.append(listing_id)

        listings_resp = (
            supabase.table("listings")
            .select("*,listing_photos(photo_url,sort_order)")
            .in_("id", listing_ids)
            .execute()
        )
        listing_map = {
            str(item["id"]): hydrate_listing_images(item)
            for item in (listings_resp.data or [])
        }

        data = []
        for row in rows:
            listing_id = str(row.get("listing_id") or "")
            listing = listing_map.get(listing_id)
            if listing:
                data.append({"interested_at": row.get("created_at"), "interest_source": row.get("source"), **listing})

        return {"status": "success", "data": data}
    except Exception as e:
        if interested_storage_missing(e):
            raise HTTPException(status_code=503, detail="Interested listing storage not configured. Run migration 20260406030000_user_interested_listings.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to fetch interested listings: {e}")


@router.get("/interested-listings/ids")
async def get_my_interested_listing_ids(token: str = Depends(require_user_token)):
    """Return listing IDs the current user marked as interested."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)

    try:
        rows_resp = (
            supabase.table("user_interested_listings")
            .select("listing_id")
            .eq("actor_user_id", user_id)
            .execute()
        )
        ids = [row["listing_id"] for row in (rows_resp.data or []) if row.get("listing_id")]
        return {"status": "success", "interested_listing_ids": ids}
    except Exception as e:
        if interested_storage_missing(e):
            raise HTTPException(status_code=503, detail="Interested listing storage not configured. Run migration 20260406030000_user_interested_listings.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to fetch interested listing ids: {e}")


@router.post("/interested-listings/{listing_id}")
async def mark_listing_interested(
    listing_id: str,
    payload: InterestedListingCreate,
    token: str = Depends(require_user_token),
):
    """Mark a listing as personally interesting for the current user."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)

    try:
        existing_listing = (
            supabase.table("listings").select("id").eq("id", listing_id).limit(1).execute()
        )
        if not existing_listing.data:
            raise HTTPException(status_code=404, detail="Listing not found")

        existing_interested = (
            supabase.table("user_interested_listings")
            .select("id")
            .eq("actor_user_id", user_id)
            .eq("listing_id", listing_id)
            .limit(1)
            .execute()
        )
        if existing_interested.data:
            return {"status": "success", "listing_id": listing_id, "already_interested": True}

        supabase.table("user_interested_listings").insert({
            "actor_user_id": user_id, "listing_id": listing_id, "source": payload.source
        }).execute()

        return {"status": "success", "listing_id": listing_id, "already_interested": False}
    except HTTPException:
        raise
    except Exception as e:
        if interested_storage_missing(e):
            raise HTTPException(status_code=503, detail="Interested listing storage not configured. Run migration 20260406030000_user_interested_listings.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to mark listing interested: {e}")


@router.delete("/interested-listings/{listing_id}")
async def unmark_listing_interested(listing_id: str, token: str = Depends(require_user_token)):
    """Remove a listing from the current user's interested list."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)

    try:
        supabase.table("user_interested_listings").delete().eq(
            "actor_user_id", user_id
        ).eq("listing_id", listing_id).execute()
        return {"status": "success", "listing_id": listing_id}
    except Exception as e:
        if interested_storage_missing(e):
            raise HTTPException(status_code=503, detail="Interested listing storage not configured. Run migration 20260406030000_user_interested_listings.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to unmark listing interested: {e}")
