"""
Listing routes
CRUD operations for listings table
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from app.dependencies.auth import get_user_token, require_user_token
from app.services.supabase_client import SupabaseHTTPClient
from app.models import ListingCreate, ListingUpdate

router = APIRouter(prefix="/api", tags=["listings"])


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
        filters=filters,
        limit=limit,
        offset=offset,
        order="created_at.desc"
    )
    
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
        id_value=listing_id
    )
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    return {
        "status": "success",
        "data": listing
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
