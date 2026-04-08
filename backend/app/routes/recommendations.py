"""
Recommendations route

POST /api/recommendations
Returns a ranked list of listings with match scores for a given user.
Frontend just sends user preferences, gets back sorted listings with scores.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.ai.recommender import score_listings
from app.services.listing_payloads import hydrate_listing_image_collection
from app.services.location_matching import filter_listings_for_location
from app.dependencies.auth import get_user_token
from app.dependencies.rate_limit import guest_rate_limit

router = APIRouter(prefix="/api", tags=["recommendations"])


# ── request / response models ──────────────────────────────────────────────

class UserPreferences(BaseModel):
    """
    User preferences for recommendation scoring.
    All fields are optional — send whatever you have.
    The more fields provided, the better the recommendations.
    """
    # Budget
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    target_country: Optional[str] = None
    target_state_province: Optional[str] = None
    target_city: Optional[str] = None

    # Housing preferences
    desired_beds: Optional[float] = None
    desired_baths: Optional[float] = None
    desired_sqft_min: Optional[float] = None
    required_bedrooms: Optional[float] = None
    target_bathrooms: Optional[float] = None
    target_deposit_amount: Optional[float] = None
    furnished_preference: Optional[str] = None  # required | preferred | no_preference
    allow_larger_layouts: Optional[bool] = None
    lifestyle_preferences: Optional[Dict[str, Any]] = None
    gender_policy: Optional[str] = None         # same_gender_only | mixed_ok
    target_lease_type: Optional[str] = None     # fixed | month_to_month | sublet | any
    target_lease_duration_months: Optional[int] = None
    move_in_date: Optional[str] = None
    target_furnished: Optional[bool] = None
    wants_furnished: Optional[int] = None  # 1 = yes, 0 = no

    # Location
    pref_lat: Optional[float] = None
    pref_lon: Optional[float] = None
    max_distance_km: Optional[float] = None

    # Hard constraints
    has_cats: Optional[int] = None         # 1 = has cats
    has_dogs: Optional[int] = None         # 1 = has dogs
    is_smoker: Optional[int] = None        # 1 = smoker
    needs_wheelchair: Optional[int] = None # 1 = needs access

    # Demographics (improves accuracy but not required)
    age: Optional[float] = None
    household_size: Optional[float] = None
    income: Optional[float] = None
    has_ev: Optional[int] = None           # 1 = has EV

    # Liked listing averages (from user's interaction history)
    # If not provided, model falls back to profile features only
    liked_mean_price: Optional[float] = None
    liked_mean_beds: Optional[float] = None
    liked_mean_sqfeet: Optional[float] = None
    behavior_sample_size: Optional[int] = None

    # How many results to return (default 20, max 100)
    top_n: Optional[int] = 20
    offset: Optional[int] = 0


class RecommendedListing(BaseModel):
    """A single recommended listing with its match score."""
    listing_id: str
    match_score: float          # 0.0 to 1.0 — show as "X% match" in UI
    match_percent: str          # e.g. "94%" — ready to display directly
    rule_score: Optional[float] = None
    behavior_score: Optional[float] = None
    ml_score: Optional[float] = None
    algorithm_version: Optional[str] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    explainability: Optional[Dict[str, Any]] = None
    title: Optional[str] = None
    price_per_month: Optional[float] = None
    number_of_bedrooms: Optional[int] = None
    number_of_bathrooms: Optional[float] = None
    area_sqft: Optional[int] = None
    furnished: Optional[bool] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    property_type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    available_from: Optional[str] = None
    amenities: Optional[Dict[str, Any]] = None
    images: Optional[List[str]] = None


class RecommendationRankingContext(BaseModel):
    algorithm_version: Optional[str] = None
    model_version: Optional[str] = None
    experiment_name: Optional[str] = None
    experiment_variant: Optional[str] = None


class RecommendationsResponse(BaseModel):
    status: str
    count: int
    offset: int
    total_available: int
    has_more: bool
    ranking_context: Optional[RecommendationRankingContext] = None
    recommendations: List[RecommendedListing]


# ── endpoint ───────────────────────────────────────────────────────────────

GUEST_MAX_RESULTS = 20  # guests see a meaningful sample before hitting a signup prompt


@router.post("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    preferences: UserPreferences,
    _: None = Depends(guest_rate_limit),
    token: Optional[str] = Depends(get_user_token),
):
    """
    Get ranked listing recommendations for a user.

    Send the user's preferences and get back a list of listings sorted
    by compatibility score (highest first).

    The match_score is a number from 0 to 1.
    The match_percent field is ready to display directly (e.g. "94%").

    Example request:
    {
        "budget_max": 1500,
        "desired_beds": 2,
        "has_cats": 1,
        "pref_lat": 43.65,
        "pref_lon": -79.38,
        "top_n": 20
    }
    """
    is_guest = token is None
    if is_guest:
        preferences.top_n = min(preferences.top_n or GUEST_MAX_RESULTS, GUEST_MAX_RESULTS)

    try:
        from app.dependencies.supabase import get_admin_client
        supabase = get_admin_client()
        # Paginate to fetch all listings (Supabase default page size is 1000)
        all_listings = []
        page_size = 1000
        offset = 0
        while True:
            resp = (
                supabase.table("listings")
                .select("*,listing_photos(photo_url,sort_order)")
                .eq("status", "active")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            page = resp.data or []
            all_listings.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        listings = hydrate_listing_image_collection(all_listings)
    except Exception as e:
        print(f"[recommendations] listings fetch error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch listings. Please try again.")

    if not listings:
        return RecommendationsResponse(
            status="success",
            count=0,
            offset=0,
            total_available=0,
            has_more=False,
            recommendations=[],
        )

    user = preferences.model_dump(exclude={"top_n", "offset"})
    top_n = min(preferences.top_n or 20, 100)
    offset = max(preferences.offset or 0, 0)

    if user.get("target_city") or user.get("target_state_province") or user.get("target_country"):
        listings = filter_listings_for_location(
            listings,
            target_city=user.get("target_city"),
            target_state=user.get("target_state_province"),
            target_country=user.get("target_country"),
        )

    try:
        scored = score_listings(user, listings, top_n=len(listings))
    except Exception as e:
        print(f"[recommendations] scoring error: {e}")
        raise HTTPException(status_code=500, detail="Recommendation scoring failed. Please try again.")

    paged = scored[offset:offset + top_n]

    recommendations = []
    for item in paged:
        recommendations.append(RecommendedListing(
            listing_id=str(item.get("id", "")),
            match_score=item["match_score"],
            match_percent=f"{round(item['match_score'] * 100)}%",
            rule_score=item.get("rule_score"),
            behavior_score=item.get("behavior_score"),
            ml_score=item.get("ml_score"),
            algorithm_version=item.get("algorithm_version"),
            score_breakdown=item.get("score_breakdown"),
            explainability=item.get("explainability"),
            title=item.get("title"),
            price_per_month=float(item["price_per_month"]) if item.get("price_per_month") else None,
            number_of_bedrooms=item.get("number_of_bedrooms"),
            number_of_bathrooms=float(item["number_of_bathrooms"]) if item.get("number_of_bathrooms") else None,
            area_sqft=item.get("area_sqft"),
            furnished=item.get("furnished"),
            city=item.get("city"),
            state_province=item.get("state_province"),
            property_type=item.get("property_type"),
            latitude=float(item["latitude"]) if item.get("latitude") else None,
            longitude=float(item["longitude"]) if item.get("longitude") else None,
            available_from=str(item["available_from"]) if item.get("available_from") else None,
            amenities=item.get("amenities"),
            images=item.get("images"),
        ))

    has_ml_scores = any(item.get("ml_score") is not None for item in paged)
    ranking_context = RecommendationRankingContext(
        algorithm_version=paged[0].get("algorithm_version") if paged else None,
        model_version="recommender-v1" if has_ml_scores else None,
        experiment_name="matches_ranker_v1" if paged else None,
        experiment_variant="two_tower" if has_ml_scores else "baseline" if paged else None,
    )

    return RecommendationsResponse(
        status="success",
        count=len(recommendations),
        offset=offset,
        total_available=len(scored),
        has_more=(offset + len(recommendations)) < len(scored),
        ranking_context=ranking_context,
        recommendations=recommendations,
    )
