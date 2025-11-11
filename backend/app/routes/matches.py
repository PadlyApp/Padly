"""
Matches routes
Get personalized listing matches for users based on preferences
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.dependencies.auth import get_user_token, require_user_token
from app.services.supabase_client import SupabaseHTTPClient
from app.services.matching_algorithm import (
    get_user_matches,
    get_matches_for_user,
    get_group_matches_for_user,
    get_all_algorithm_data
)

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get("/{user_id}")
async def get_matches_for_user(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    token: Optional[str] = Depends(get_user_token)
):
    """
    Get personalized listing matches for a user.
    
    Currently uses random matching algorithm.
    Future: Will use preferences-based matching.
    
    Args:
        user_id: The user's database ID (not auth_id)
        limit: Maximum number of matches to return (1-100)
        token: JWT authentication token (optional)
    
    Returns:
        List of matched listings with match scores
    """
    client = SupabaseHTTPClient(token=token)
    
    try:
        # Get user's preferences (optional - for future use)
        try:
            preferences = await client.select_one(
                table="personal_preferences",
                id_value=user_id,
                id_column="user_id"
            )
        except:
            preferences = None  # User might not have set preferences yet
        
        # Get all active listings
        # Note: PostgREST filter format is "column=eq.value"
        try:
            listings_response = await client.select(
                table="listings",
                filters={"status": "eq.active"},
                limit=100  # Limit initial fetch
            )
            all_listings = listings_response if isinstance(listings_response, list) else []
        except:
            # If filtering fails, get all listings
            all_listings_response = await client.select(
                table="listings",
                limit=100
            )
            all_listings = all_listings_response if isinstance(all_listings_response, list) else []
        
        # If no listings in database, return empty matches
        if not all_listings:
            return {
                "status": "success",
                "data": {
                    "user_id": user_id,
                    "total_matches": 0,
                    "matches": [],
                    "message": "No listings available at this time"
                }
            }
        
        # Get matches using the algorithm
        matches_data = get_user_matches(
            user_id=user_id,
            all_listings=all_listings,
            user_preferences=preferences,
            limit=limit
        )
        
        return {
            "status": "success",
            "data": matches_data
        }
        
    except HTTPException:
        raise  # Re-raise HTTPExceptions as-is
    except Exception as e:
        # Return friendly error with details
        import traceback
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get matches: {str(e)}"
        )


@router.get("/me/recommendations")
async def get_my_matches(
    limit: int = Query(default=20, ge=1, le=100),
    token: str = Depends(require_user_token)
):
    """
    Get matches for the currently authenticated user.
    
    Requires authentication. Extracts user_id from JWT token.
    """
    # TODO: Extract user_id from JWT token
    # For now, this is a placeholder endpoint
    raise HTTPException(
        status_code=501,
        detail="This endpoint requires JWT parsing to extract user_id. Use GET /{user_id} for now."
    )


@router.get("/data/listings")
async def get_parsed_listings():
    """
    Get all parsed listings data for algorithms.
    Returns JSON-ready listing objects.
    
    This endpoint is useful for:
    - Testing the data parser
    - Debugging matching algorithms
    - Exporting data for analysis
    
    Returns:
        List of parsed active listings
    """
    try:
        data = await get_all_algorithm_data()
        return {
            "status": "success",
            "count": len(data['listings']),
            "data": data['listings']
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch listings: {str(e)}"
        )


@router.get("/data/groups")
async def get_parsed_groups():
    """
    Get all parsed roommate groups data for algorithms.
    Returns JSON-ready group objects with member information.
    
    This endpoint is useful for:
    - Testing the data parser
    - Debugging matching algorithms
    - Exporting data for analysis
    
    Returns:
        List of parsed active groups with members
    """
    try:
        data = await get_all_algorithm_data()
        return {
            "status": "success",
            "count": len(data['groups']),
            "data": data['groups']
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch groups: {str(e)}"
        )


@router.get("/data/all")
async def get_all_parsed_data():
    """
    Get all parsed data for algorithms (listings and groups).
    Returns complete JSON-ready dataset.
    
    This endpoint is useful for:
    - Testing the data parser
    - Debugging matching algorithms
    - Exporting data for analysis
    - Getting a complete snapshot of available data
    
    Returns:
        Dictionary with 'listings' and 'groups' arrays
    """
    try:
        data = await get_all_algorithm_data()
        return {
            "status": "success",
            "data": data,
            "summary": {
                "total_listings": len(data['listings']),
                "total_groups": len(data['groups'])
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch algorithm data: {str(e)}"
        )


@router.get("/{user_id}/v2")
async def get_matches_for_user_v2(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    token: Optional[str] = Depends(get_user_token)
):
    """
    Get personalized listing matches for a user (v2 - uses data parser).
    
    This version fetches fresh data from Supabase and uses the data parser
    to ensure proper formatting for algorithms.
    
    Args:
        user_id: The user's database ID (not auth_id)
        limit: Maximum number of matches to return (1-100)
        token: JWT authentication token (optional)
    
    Returns:
        List of matched listings with match scores
    """
    try:
        matches_data = await get_matches_for_user(user_id=user_id, limit=limit)
        
        return {
            "status": "success",
            "data": matches_data
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get matches: {str(e)}"
        )


@router.get("/{user_id}/groups")
async def get_group_matches(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    token: Optional[str] = Depends(get_user_token)
):
    """
    Get roommate group matches for a user.
    
    Finds groups that:
    - Are still accepting members (not at capacity)
    - Match the user's preferences (future)
    - Are active
    
    Args:
        user_id: The user's database ID (not auth_id)
        limit: Maximum number of group matches to return (1-100)
        token: JWT authentication token (optional)
    
    Returns:
        List of matched groups with match scores
    """
    try:
        matches_data = await get_group_matches_for_user(user_id=user_id, limit=limit)
        
        return {
            "status": "success",
            "data": matches_data
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get group matches: {str(e)}"
        )
