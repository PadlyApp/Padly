"""
Listing routes
CRUD operations for listings table
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import os
from app.dependencies.auth import get_user_token, require_user_token
from app.services.supabase_client import SupabaseHTTPClient
from app.services.listing_payloads import hydrate_listing_image_collection, hydrate_listing_images
from app.models import ListingCreate, ListingUpdate

router = APIRouter(prefix="/api", tags=["listings"])


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _stable_group_listing_writes_enabled() -> bool:
    return _env_bool("PADLY_STABLE_GROUP_LISTING_WRITES_ENABLED", default=False)


@router.get("/listings")
async def list_listings(
    token: Optional[str] = Depends(get_user_token),
    status: Optional[str] = None,
    city: Optional[str] = None,
    property_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_bedrooms: Optional[int] = None,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
):
    """
    List all listings with optional filters.
    
    Query params:
    - status: Filter by listing status (active, inactive, draft)
    - city: Filter by city
    - property_type: Filter by property type (entire_place, private_room, shared_room)
    - min_price: Minimum price per month
    - max_price: Maximum price per month
    - min_bedrooms: Minimum number of bedrooms
    - limit: Max results (default: 100)
    - offset: Pagination offset
    """
    client = SupabaseHTTPClient(token=token)
    
    filters = {}
    if status:
        filters["status"] = f"eq.{status}"
    if city:
        filters["city"] = f"ilike.*{city}*"
    if property_type:
        filters["property_type"] = f"eq.{property_type}"
    if min_price is not None:
        filters["price_per_month"] = f"gte.{min_price}"
    if max_price is not None:
        filters["price_per_month"] = f"lte.{max_price}"
    if min_bedrooms is not None:
        filters["number_of_bedrooms"] = f"gte.{min_bedrooms}"
    
    listings = await client.select(
        table="listings",
        columns="*,listing_photos(photo_url,sort_order)",
        filters=filters,
        limit=limit,
        offset=offset,
        order="created_at.desc"
    )
    listings = hydrate_listing_image_collection(listings)
    
    return {
        "status": "success",
        "message": "Listings fetched successfully",
        "data": {
            "count": len(listings),
            "listings": listings
        }
    }


@router.get("/listings/{listing_id}")
async def get_listing(
    listing_id: str,
    token: Optional[str] = Depends(get_user_token)
):
    """Get a single listing by ID"""
    client = SupabaseHTTPClient(token=token)
    
    listing = await client.select_one(
        table="listings",
        id_value=listing_id,
        columns="*,listing_photos(photo_url,sort_order)",
    )
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    return {
        "status": "success",
        "data": hydrate_listing_images(listing)
    }


@router.post("/listings")
async def create_listing(
    listing_data: ListingCreate,
    token: str = Depends(require_user_token)
):
    """
    Create a new listing.
    Requires authentication.
    """
    client = SupabaseHTTPClient(token=token)
    
    data = listing_data.model_dump(exclude_none=True)
    
    listing = await client.insert(
        table="listings",
        data=data
    )
    
    return {
        "status": "success",
        "message": "Listing created successfully",
        "data": listing
    }


@router.put("/listings/{listing_id}")
async def update_listing(
    listing_id: str,
    listing_data: ListingUpdate,
    token: str = Depends(require_user_token)
):
    """
    Update a listing.
    Requires authentication.
    With RLS: User can only update their own listings
    """
    client = SupabaseHTTPClient(token=token)
    
    data = listing_data.model_dump(exclude_none=True)
    
    if not data:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    listing = await client.update(
        table="listings",
        id_value=listing_id,
        data=data
    )
    
    return {
        "status": "success",
        "message": "Listing updated successfully",
        "data": listing
    }


@router.delete("/listings/{listing_id}")
async def delete_listing(
    listing_id: str,
    token: str = Depends(require_user_token)
):
    """
    Delete a listing.
    Requires authentication.
    With RLS: User can only delete their own listings
    """
    client = SupabaseHTTPClient(token=token)
    
    await client.delete(
        table="listings",
        id_value=listing_id
    )
    
    return {
        "status": "success",
        "message": "Listing deleted successfully"
    }


# =============================================================================
# Match Confirmation Endpoints
# =============================================================================

@router.get("/listings/{listing_id}/matches")
async def get_listing_matches(
    listing_id: str,
    token: str = Depends(require_user_token)
):
    """
    Get all stable matches for a listing (listing owner only).
    
    Returns groups that have been matched to this listing.
    """
    from app.dependencies.supabase import get_admin_client
    
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    current_user_id = user_record.data[0]['id']
    
    # Check if user owns this listing
    listing_response = supabase.table('listings')\
        .select('*')\
        .eq('id', listing_id)\
        .single()\
        .execute()
    
    if not listing_response.data:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    listing = listing_response.data
    
    if listing.get('host_user_id') != current_user_id:
        raise HTTPException(status_code=403, detail="Only the listing owner can view matches")
    
    # Get matches for this listing
    matches_response = supabase.table('stable_matches')\
        .select('*, roommate_groups(id, group_name, target_city, current_member_count, target_group_size)')\
        .eq('listing_id', listing_id)\
        .eq('status', 'active')\
        .order('listing_rank')\
        .execute()
    
    matches = matches_response.data or []
    
    # Enrich with group member details
    for match in matches:
        group = match.get('roommate_groups', {})
        if group and group.get('id'):
            members_response = supabase.table('group_members')\
                .select('*, users(id, full_name, email, verification_status)')\
                .eq('group_id', group['id'])\
                .eq('status', 'accepted')\
                .execute()
            
            members = []
            for member in members_response.data or []:
                user_data = member.get('users', {}) if isinstance(member.get('users'), dict) else {}
                members.append({
                    'user_id': member.get('user_id'),
                    'full_name': user_data.get('full_name'),
                    'email': user_data.get('email'),
                    'verification_status': user_data.get('verification_status'),
                    'is_creator': member.get('is_creator', False)
                })
            
            match['group_members'] = members
    
    return {
        "status": "success",
        "listing_id": listing_id,
        "listing_title": listing.get('title'),
        "count": len(matches),
        "matches": matches
    }


@router.post("/listings/{listing_id}/confirm-match")
async def confirm_match_as_listing(
    listing_id: str,
    token: str = Depends(require_user_token)
):
    """
    Confirm the current stable match as the listing owner.
    
    This sets listing_confirmed_at timestamp on the match.
    A match is fully confirmed when BOTH group and listing owner confirm.
    
    Confirmed matches are preserved during re-matching - only unconfirmed
    matches are recalculated when new groups join or preferences change.
    """
    if not _stable_group_listing_writes_enabled():
        raise HTTPException(
            status_code=410,
            detail=(
                "Stable match confirmation writes are disabled in Phase 3B. "
                "Group->Listing serving now uses neural ranking."
            ),
        )

    from datetime import datetime, timezone
    from app.dependencies.supabase import get_admin_client
    
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    current_user_id = user_record.data[0]['id']
    
    # Check if user owns this listing
    listing_response = supabase.table('listings')\
        .select('*')\
        .eq('id', listing_id)\
        .single()\
        .execute()
    
    if not listing_response.data:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    listing = listing_response.data
    
    if listing.get('host_user_id') != current_user_id:
        raise HTTPException(status_code=403, detail="Only the listing owner can confirm matches")
    
    # Get the active match for this listing
    match_response = supabase.table('stable_matches')\
        .select('*, roommate_groups(id, group_name, current_member_count)')\
        .eq('listing_id', listing_id)\
        .eq('status', 'active')\
        .execute()
    
    if not match_response.data:
        raise HTTPException(status_code=404, detail="No active match found for this listing")
    
    match = match_response.data[0]
    
    # Check if already confirmed by listing owner
    if match.get('listing_confirmed_at'):
        return {
            "status": "already_confirmed",
            "message": "This match was already confirmed by you",
            "match_id": match['id'],
            "group_confirmed_at": match.get('group_confirmed_at'),
            "listing_confirmed_at": match['listing_confirmed_at'],
            "fully_confirmed": match.get('group_confirmed_at') is not None
        }
    
    # Confirm the match
    now = datetime.now(timezone.utc).isoformat()
    
    update_response = supabase.table('stable_matches')\
        .update({'listing_confirmed_at': now})\
        .eq('id', match['id'])\
        .execute()
    
    # Check if now fully confirmed
    group_confirmed = match.get('group_confirmed_at') is not None
    fully_confirmed = group_confirmed  # Listing just confirmed, so fully_confirmed depends on group
    
    group_info = match.get('roommate_groups', {})
    
    return {
        "status": "success",
        "message": "Match confirmed by listing owner" + (" - Waiting for group" if not fully_confirmed else " - Both parties confirmed!"),
        "match_id": match['id'],
        "group": {
            "id": group_info.get('id'),
            "name": group_info.get('group_name'),
            "member_count": group_info.get('current_member_count')
        },
        "group_confirmed_at": match.get('group_confirmed_at'),
        "listing_confirmed_at": now,
        "fully_confirmed": fully_confirmed
    }


@router.delete("/listings/{listing_id}/reject-match")
async def reject_match_as_listing(
    listing_id: str,
    token: str = Depends(require_user_token)
):
    """
    Reject the current stable match as the listing owner.
    
    This removes the match and optionally triggers re-matching.
    """
    if not _stable_group_listing_writes_enabled():
        raise HTTPException(
            status_code=410,
            detail=(
                "Stable match rejection writes are disabled in Phase 3B. "
                "Group->Listing serving now uses neural ranking."
            ),
        )

    from app.dependencies.supabase import get_admin_client
    
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    current_user_id = user_record.data[0]['id']
    
    # Check if user owns this listing
    listing_response = supabase.table('listings')\
        .select('*')\
        .eq('id', listing_id)\
        .single()\
        .execute()
    
    if not listing_response.data:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    listing = listing_response.data
    
    if listing.get('host_user_id') != current_user_id:
        raise HTTPException(status_code=403, detail="Only the listing owner can reject matches")
    
    # Get the active match for this listing
    match_response = supabase.table('stable_matches')\
        .select('*')\
        .eq('listing_id', listing_id)\
        .eq('status', 'active')\
        .execute()
    
    if not match_response.data:
        raise HTTPException(status_code=404, detail="No active match found for this listing")
    
    match = match_response.data[0]
    
    # Check if already confirmed by BOTH parties - can't reject a fully confirmed match
    if match.get('group_confirmed_at') and match.get('listing_confirmed_at'):
        raise HTTPException(
            status_code=400, 
            detail="Cannot reject a fully confirmed match. Contact support if needed."
        )
    
    # Mark the match as cancelled
    supabase.table('stable_matches')\
        .update({'status': 'cancelled'})\
        .eq('id', match['id'])\
        .execute()
    
    # Trigger re-matching for the city
    city = listing.get('city')
    matching_result = {'status': 'skipped', 'message': 'No city specified'}
    
    if city:
        from app.routes.stable_matching import run_matching, RunMatchingRequest
        
        try:
            matching_request = RunMatchingRequest(city=city, date_flexibility_days=30)
            matching_response = await run_matching(matching_request)
            matching_result = {
                "status": "success",
                "city": city,
                "total_matches": len(matching_response.matches),
                "message": "Re-matching completed"
            }
        except Exception as e:
            matching_result = {"status": "error", "message": str(e)}
    
    return {
        "status": "success",
        "message": "Match rejected. Re-matching triggered to find new options.",
        "rejected_match_id": match['id'],
        "matching": matching_result
    }
