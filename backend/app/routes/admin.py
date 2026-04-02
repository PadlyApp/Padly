"""
Admin routes
Admin-only operations using service role (bypasses RLS).

All routes here require the X-Admin-Secret header to match the ADMIN_SECRET
environment variable. Never expose these endpoints to the frontend.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from app.services.supabase_client import SupabaseHTTPClient
from app.dependencies.auth import require_admin_key

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_key)],
)


@router.get("/users")
async def admin_list_users(
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
):
    """
    Admin: List ALL users (bypasses RLS).
    
    ⚠️ Uses service role key - never expose to frontend
    """
    client = SupabaseHTTPClient(is_admin=True)
    
    users = await client.select(
        table="users",
        limit=limit,
        offset=offset,
        order="created_at.desc"
    )
    
    return {
        "status": "success",
        "count": len(users),
        "data": users
    }


@router.get("/users/{user_id}")
async def admin_get_user(user_id: str):
    """Admin: Get any user by ID (bypasses RLS)"""
    client = SupabaseHTTPClient(is_admin=True)
    
    user = await client.select_one(
        table="users",
        id_value=user_id
    )
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "status": "success",
        "data": user
    }


@router.delete("/users/{user_id}")
async def admin_delete_user(user_id: str):
    """Admin: Force delete any user (bypasses RLS)"""
    client = SupabaseHTTPClient(is_admin=True)
    
    await client.delete(
        table="users",
        id_value=user_id
    )
    
    return {
        "status": "success",
        "message": "User deleted successfully"
    }


@router.get("/listings")
async def admin_list_listings(
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
):
    """Admin: List ALL listings (bypasses RLS)"""
    client = SupabaseHTTPClient(is_admin=True)
    
    listings = await client.select(
        table="listings",
        limit=limit,
        offset=offset,
        order="created_at.desc"
    )
    
    return {
        "status": "success",
        "count": len(listings),
        "data": listings
    }


@router.delete("/listings/{listing_id}")
async def admin_delete_listing(listing_id: str):
    """Admin: Force delete any listing (bypasses RLS)"""
    client = SupabaseHTTPClient(is_admin=True)
    
    await client.delete(
        table="listings",
        id_value=listing_id
    )
    
    return {
        "status": "success",
        "message": "Listing deleted successfully"
    }


@router.get("/stats")
async def admin_stats():
    """Admin: Get platform statistics"""
    client = SupabaseHTTPClient(is_admin=True)
    
    # Count users
    users_count = await client.count("users")
    
    # Count listings
    listings_count = await client.count("listings")
    
    # Count active listings
    active_listings_count = await client.count(
        "listings",
        filters={"status": "eq.active"}
    )
    
    return {
        "status": "success",
        "data": {
            "total_users": users_count,
            "total_listings": listings_count,
            "active_listings": active_listings_count
        }
    }
