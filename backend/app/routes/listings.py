"""
Listing routes
CRUD operations for listings table
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from app.dependencies.auth import get_user_token, require_user_token
from app.services.supabase_client import SupabaseHTTPClient
from app.services.listing_payloads import hydrate_listing_image_collection, hydrate_listing_images
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
    if min_price is not None and max_price is not None:
        # PostgREST `and` operator avoids the dict-key collision when both bounds are set.
        filters["and"] = f"(price_per_month.gte.{min_price},price_per_month.lte.{max_price})"
    elif min_price is not None:
        filters["price_per_month"] = f"gte.{min_price}"
    elif max_price is not None:
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


@router.get("/listings/price-histogram")
async def get_price_histogram(
    city: str,
    status: Optional[str] = "active",
    bins: Optional[int] = 30,
):
    """
    Return a price-distribution histogram for listings in a given city or metro area.

    Metro area values (GTA, NYC, Bay Area) are expanded to all constituent cities
    using the shared location_matching helpers, so the histogram covers the full metro.

    Fetches only price_per_month + city (no photos, no RLS token required — prices
    are public context used to inform budget selection during onboarding).

    Query params:
    - city:   City name or metro alias to filter on (required)
    - status: Listing status, default "active"
    - bins:   Number of histogram buckets, default 30
    """
    from app.services.location_matching import metro_id_for_city, filter_listings_for_location
    from app.dependencies.supabase import get_admin_client

    supabase = get_admin_client()
    effective_status = status or "active"

    is_metro = metro_id_for_city(city) is not None

    if is_metro:
        # Paginate through all active listings then filter in Python via metro-aware helper.
        # SupabaseHTTPClient.select is capped by PostgREST db-max-rows (~1000); Bay Area
        # listings start at physical row 1722, so they would never appear without pagination.
        rows = []
        page_size = 1000
        offset = 0
        while True:
            resp = (
                supabase.table("listings")
                .select("price_per_month,city,state_province,country")
                .eq("status", effective_status)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            page = resp.data or []
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        rows = filter_listings_for_location(rows, target_city=city)
    else:
        resp = (
            supabase.table("listings")
            .select("price_per_month")
            .ilike("city", f"*{city}*")
            .eq("status", effective_status)
            .execute()
        )
        rows = resp.data or []

    prices = [
        float(r["price_per_month"])
        for r in rows
        if r.get("price_per_month") is not None and float(r["price_per_month"]) > 0
    ]

    if not prices:
        return {
            "status": "success",
            "data": {
                "city": city,
                "total_count": 0,
                "global_min": 500,
                "global_max": 5000,
                "p10": 500,
                "p90": 5000,
                "bins": [],
            },
        }

    prices_sorted = sorted(prices)
    total = len(prices_sorted)

    def _percentile(sorted_list, p):
        idx = max(0, min(int((p / 100) * (len(sorted_list) - 1)), len(sorted_list) - 1))
        return sorted_list[idx]

    global_min = prices_sorted[0]
    global_max = prices_sorted[-1]
    p10 = _percentile(prices_sorted, 10)
    p90 = _percentile(prices_sorted, 90)

    # Cap the display range to avoid outliers skewing the histogram left.
    # Find the price below which ≥ 97% of listings fall; only cap if the
    # outlier gap is meaningful (top outliers are >10% higher than the cutoff).
    outlier_threshold = max(2, int(0.03 * total))
    cutoff_idx = total - outlier_threshold - 1
    candidate_max = prices_sorted[cutoff_idx] if cutoff_idx >= 0 else global_max
    if candidate_max < global_max * 0.9:
        display_max = candidate_max
        capped = True
    else:
        display_max = global_max
        capped = False

    bin_count = max(1, min(bins, 50))
    if global_min == display_max:
        histogram_bins = [{"range_min": global_min, "range_max": display_max, "count": total}]
    else:
        bin_width = (display_max - global_min) / bin_count
        histogram_bins = [
            {
                "range_min": round(global_min + i * bin_width, 2),
                "range_max": round(global_min + (i + 1) * bin_width, 2),
                "count": 0,
            }
            for i in range(bin_count)
        ]
        for price in prices:
            # Prices above display_max are merged into the last bin
            idx = min(int((price - global_min) / bin_width), bin_count - 1)
            histogram_bins[idx]["count"] += 1

    return {
        "status": "success",
        "data": {
            "city": city,
            "total_count": total,
            "global_min": global_min,
            "global_max": global_max,
            "display_max": display_max,
            "capped": capped,
            "p10": p10,
            "p90": p90,
            "bins": histogram_bins,
        },
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
    Legacy stable-match endpoint retained only as an explicit retirement marker.
    """
    raise HTTPException(
        status_code=410,
        detail="Stable matching has been retired. Listing owners should use direct recommendation analytics instead of stable-match endpoints.",
    )


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
    raise HTTPException(
        status_code=410,
        detail="Stable match confirmations have been retired.",
    )


@router.delete("/listings/{listing_id}/reject-match")
async def reject_match_as_listing(
    listing_id: str,
    token: str = Depends(require_user_token)
):
    """
    Reject the current stable match as the listing owner.
    
    This removes the match and optionally triggers re-matching.
    """
    raise HTTPException(
        status_code=410,
        detail="Stable match rejections have been retired.",
    )
