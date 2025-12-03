"""
Matches routes

This module provides endpoints for users to discover:
1. Compatible roommate groups (User-to-Group matching)
2. Listings for their group (via stable matching)

Note: Individual user→listing matching is deprecated. 
Users should join/create a group first, then get group→listing matches.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.dependencies.auth import get_user_token, require_user_token
from app.dependencies.supabase import get_admin_client
from app.services.user_group_matching import find_compatible_groups, calculate_user_group_compatibility

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get("/groups")
async def discover_compatible_groups(
    city: str = Query(..., description="Target city to search in"),
    budget_min: Optional[float] = Query(None, description="Minimum budget per person"),
    budget_max: Optional[float] = Query(None, description="Maximum budget per person"),
    move_in_date: Optional[str] = Query(None, description="Target move-in date (ISO format)"),
    # NEW: Additional preference filters from personal_preferences
    target_lease_type: Optional[str] = Query(None, description="Preferred lease type (month-to-month, fixed, sublet)"),
    target_lease_duration_months: Optional[int] = Query(None, description="Preferred lease duration in months"),
    target_furnished: Optional[bool] = Query(None, description="Prefer furnished places"),
    target_utilities_included: Optional[bool] = Query(None, description="Prefer utilities included"),
    min_score: int = Query(50, ge=0, le=100, description="Minimum compatibility score"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    token: str = Depends(require_user_token)
):
    """
    Discover compatible roommate groups based on user preferences.
    
    This uses the User-to-Group matching algorithm which scores groups based on:
    - Hard Constraints: City match, budget overlap, date proximity (±60 days), open spots
    - Soft Preferences: Budget fit (20pts), Date fit (15pts), Lease preferences (15pts),
      Amenity preferences (10pts), Company/School (10pts), Verification (10pts), Lifestyle (20pts)
    
    Returns groups ranked by compatibility score with detailed reasons.
    """
    supabase = get_admin_client()
    
    # Get current user from token
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up user in users table
    user_record = supabase.table('users').select('*').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    user = user_record.data[0]
    user_id = user['id']
    
    # Build user preferences from query params or stored preferences
    prefs_response = supabase.table("personal_preferences").select("*").eq("user_id", user_id).execute()
    user_prefs = prefs_response.data[0] if prefs_response.data else {}
    
    # Override with query params if provided
    user_prefs['target_city'] = city
    if budget_min is not None:
        user_prefs['budget_min'] = budget_min
    if budget_max is not None:
        user_prefs['budget_max'] = budget_max
    if move_in_date is not None:
        user_prefs['move_in_date'] = move_in_date
    # NEW: Override with new preference query params
    if target_lease_type is not None:
        user_prefs['target_lease_type'] = target_lease_type
    if target_lease_duration_months is not None:
        user_prefs['target_lease_duration_months'] = target_lease_duration_months
    if target_furnished is not None:
        user_prefs['target_furnished'] = target_furnished
    if target_utilities_included is not None:
        user_prefs['target_utilities_included'] = target_utilities_included
    
    # Find compatible groups
    try:
        compatible_groups = await find_compatible_groups(
            user_id=user_id,
            user_prefs=user_prefs,
            min_score=min_score,
            limit=limit
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    return {
        "status": "success",
        "user_id": user_id,
        "search_criteria": {
            "city": city,
            "budget_min": user_prefs.get('budget_min'),
            "budget_max": user_prefs.get('budget_max'),
            "move_in_date": user_prefs.get('move_in_date'),
            "target_lease_type": user_prefs.get('target_lease_type'),
            "target_lease_duration_months": user_prefs.get('target_lease_duration_months'),
            "target_furnished": user_prefs.get('target_furnished'),
            "target_utilities_included": user_prefs.get('target_utilities_included'),
            "min_score": min_score
        },
        "count": len(compatible_groups),
        "groups": compatible_groups
    }


@router.get("/{user_id}")
async def get_user_group_status(
    user_id: str,
    token: Optional[str] = Depends(get_user_token)
):
    """
    Get the user's current group and their group's listing matches.
    
    This endpoint helps users understand:
    1. Which group(s) they belong to
    2. What stable matches their group has (from LNS algorithm)
    
    For individual user→listing matches, users should:
    1. Create or join a roommate group
    2. Use /api/roommate-groups/{group_id}/matches for stable matches
    3. Use /api/roommate-groups/{group_id}/eligible-listings for browsing
    """
    supabase = get_admin_client()
    
    # Get user's groups
    member_response = supabase.table('group_members')\
        .select('*, roommate_groups(*)')\
        .eq('user_id', user_id)\
        .eq('status', 'accepted')\
        .execute()
    
    if not member_response.data:
        return {
            "status": "success",
            "user_id": user_id,
            "message": "User is not a member of any group. Create or join a group to get listing matches.",
            "groups": [],
            "next_steps": [
                "POST /api/roommate-groups - Create a new group",
                "GET /api/matches/groups?city=Boston - Discover compatible groups to join",
                "POST /api/roommate-groups/{group_id}/request-join - Request to join a group"
            ]
        }
    
    # Get matches for each group
    groups_with_matches = []
    for membership in member_response.data:
        group = membership.get('roommate_groups', {})
        group_id = group.get('id')
        
        if not group_id:
            continue
        
        # Get stable matches for this group
        matches_response = supabase.table('stable_matches')\
            .select('*, listings(*)')\
            .eq('group_id', group_id)\
            .eq('status', 'active')\
            .order('group_rank')\
            .limit(10)\
            .execute()
        
        groups_with_matches.append({
            "group_id": group_id,
            "group_name": group.get('group_name'),
            "target_city": group.get('target_city'),
            "is_creator": membership.get('is_creator', False),
            "match_count": len(matches_response.data) if matches_response.data else 0,
            "top_matches": matches_response.data[:5] if matches_response.data else []
        })
    
    return {
        "status": "success",
        "user_id": user_id,
        "groups": groups_with_matches,
        "endpoints": {
            "group_matches": "/api/roommate-groups/{group_id}/matches",
            "eligible_listings": "/api/roommate-groups/{group_id}/eligible-listings",
            "discover_groups": "/api/matches/groups?city={city}"
        }
    }

