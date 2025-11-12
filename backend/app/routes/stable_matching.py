"""
Stable Matching API Routes

This module provides REST API endpoints for the stable matching system.

Endpoints:
- POST /api/matches/run - Execute matching algorithm
- GET /api/matches/active - Get active matches (with filters)
- GET /api/matches/stats - Get matching statistics
- DELETE /api/matches/group/{group_id} - Delete matches for a group
- DELETE /api/matches/listing/{listing_id} - Delete matches for a listing
- POST /api/matches/expire - Expire old matches

Author: Padly Matching Team
Version: 0.6.0
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from app.dependencies.supabase import get_admin_client
from app.models import ListingResponse, RoommateGroupResponse
from app.services.stable_matching import (
    # Phase 1: Filters
    get_eligible_listings,
    get_eligible_groups,
    get_move_in_windows,
    # Phase 2: Feasible Pairs
    build_feasible_pairs,
    get_feasibility_statistics,
    # Phase 3: Scoring
    build_preference_lists,
    # Phase 4: Deferred Acceptance
    run_deferred_acceptance,
    # Phase 5: Persistence
    save_matching_results,
    get_active_matches_for_group,
    get_active_matches_for_listing,
    MatchPersistenceEngine
)

router = APIRouter(prefix="/api/stable-matches", tags=["Stable Matching"])
logger = logging.getLogger(__name__)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class RunMatchingRequest(BaseModel):
    """Request to run stable matching algorithm"""
    city: str = Field(..., description="City to run matching for")
    date_flexibility_days: int = Field(30, description="Date flexibility in days (default 30)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "city": "Boston",
                "date_flexibility_days": 30
            }
        }


class MatchResult(BaseModel):
    """Individual match result"""
    group_id: str
    listing_id: str
    group_score: float
    listing_score: float
    group_rank: int
    listing_rank: int
    matched_at: str
    is_stable: bool


class DiagnosticsResult(BaseModel):
    """Diagnostics for a matching round"""
    city: str
    date_window_start: str
    date_window_end: str
    total_groups: int
    total_listings: int
    feasible_pairs: int
    matched_groups: int
    matched_listings: int
    unmatched_groups: int
    unmatched_listings: int
    proposals_sent: int
    proposals_rejected: int
    iterations: int
    avg_group_rank: float
    avg_listing_rank: float
    match_quality_score: float
    is_stable: bool
    executed_at: str


class RunMatchingResponse(BaseModel):
    """Response from running matching algorithm"""
    status: str
    message: str
    diagnostics_id: Optional[str] = None
    matches: List[MatchResult]
    diagnostics: DiagnosticsResult
    execution_time_seconds: float


class ActiveMatchesResponse(BaseModel):
    """Response with active matches"""
    status: str
    count: int
    matches: List[Dict]


class StatsResponse(BaseModel):
    """Response with matching statistics"""
    status: str
    total_active_matches: int
    latest_run: Optional[Dict]


class DeleteResponse(BaseModel):
    """Response from delete operation"""
    status: str
    message: str
    deleted_count: int


class ExpireResponse(BaseModel):
    """Response from expire operation"""
    status: str
    message: str
    expired_count: int


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/run", response_model=RunMatchingResponse)
async def run_matching(request: RunMatchingRequest):
    """
    Execute the stable matching algorithm for a city
    
    This endpoint:
    1. Filters eligible groups and listings in the city
    2. Builds feasible pairs based on hard constraints
    3. Scores all pairs and builds preference lists
    4. Runs Deferred Acceptance algorithm
    5. Saves results to database
    
    Returns match results and diagnostics.
    """
    try:
        start_time = datetime.now()
        logger.info(f"Starting matching for city: {request.city}")
        
        supabase = get_admin_client()
        
        # Fetch all data from database
        logger.info("Fetching data from database...")
        listings_response = supabase.table('listings').select('*').eq('city', request.city).eq('status', 'active').execute()
        groups_response = supabase.table('roommate_groups').select('*').eq('target_city', request.city).eq('status', 'active').execute()
        
        # Parse data using Pydantic models for type safety and validation
        logger.info("Parsing data with Pydantic models...")
        
        from decimal import Decimal
        
        def convert_decimals_to_float(obj):
            """Recursively convert all Decimal fields to float"""
            if isinstance(obj, dict):
                return {k: convert_decimals_to_float(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimals_to_float(item) for item in obj]
            elif isinstance(obj, Decimal):
                return float(obj)
            else:
                return obj
        
        # Parse with Pydantic for validation, then convert Decimals to floats
        all_listings = [
            convert_decimals_to_float(ListingResponse(**listing).model_dump())
            for listing in listings_response.data
        ]
        all_groups = [
            convert_decimals_to_float(RoommateGroupResponse(**group).model_dump())
            for group in groups_response.data
        ]
        
        logger.info(f"✅ Validated and parsed {len(all_listings)} listings and {len(all_groups)} groups")
        
        # Phase 1: Get eligible entities
        logger.info("Phase 1: Filtering eligible groups and listings...")
        eligible_listings, listing_stats = get_eligible_listings(all_listings, request.city)
        eligible_groups, group_stats = get_eligible_groups(all_groups, request.city)
        
        if not eligible_listings:
            raise HTTPException(
                status_code=404,
                detail=f"No eligible listings found in {request.city}"
            )
        
        if not eligible_groups:
            raise HTTPException(
                status_code=404,
                detail=f"No eligible groups found in {request.city}"
            )
        
        logger.info(f"Found {len(eligible_listings)} eligible listings, {len(eligible_groups)} eligible groups")
        
        # Get date windows
        date_windows = get_move_in_windows(eligible_groups, window_days=request.date_flexibility_days)
        
        if not date_windows:
            raise HTTPException(
                status_code=404,
                detail="No overlapping date windows found"
            )
        
        # For now, process first date window (can be extended to handle multiple)
        date_window = date_windows[0]
        logger.info(f"Processing date window: {date_window.start_date} to {date_window.end_date}")
        
        # Phase 2: Build feasible pairs
        logger.info("Phase 2: Building feasible pairs...")
        feasible_pairs, _ = build_feasible_pairs(
            date_window.groups,
            eligible_listings,
            date_delta_days=request.date_flexibility_days
        )
        
        if not feasible_pairs:
            # Get statistics to understand why
            stats = get_feasibility_statistics(
                date_window.groups,
                eligible_listings,
                feasible_pairs
            )
            
            raise HTTPException(
                status_code=404,
                detail=f"No feasible pairs found. Stats: {stats}"
            )
        
        logger.info(f"Found {len(feasible_pairs)} feasible pairs")
        
        # Phase 3: Build preference lists
        logger.info("Phase 3: Building preference lists...")
        group_prefs, listing_prefs = build_preference_lists(
            feasible_pairs,
            date_window.groups,
            eligible_listings
        )
        
        # Create preference_lists structure
        preference_lists = {
            'group_preferences': group_prefs,
            'listing_preferences': listing_prefs
        }
        
        # Add metadata
        preference_lists['metadata'] = {
            'city': request.city,
            'date_window_start': date_window.start_date.isoformat(),
            'date_window_end': date_window.end_date.isoformat(),
            'groups': list(preference_lists['group_preferences'].keys()),
            'listings': list(preference_lists['listing_preferences'].keys()),
            'feasible_pairs': len(feasible_pairs)
        }
        
        # Phase 4: Run Deferred Acceptance
        logger.info("Phase 4: Running Deferred Acceptance algorithm...")
        matches, diagnostics = run_deferred_acceptance(preference_lists)
        
        logger.info(f"Matching complete: {len(matches)} stable matches created")
        
        # Phase 5: Save to database
        logger.info("Phase 5: Saving results to database...")
        save_result = await save_matching_results(supabase, matches, diagnostics)
        
        if save_result['status'] != 'success':
            logger.error(f"Failed to save results: {save_result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save results: {save_result.get('error')}"
            )
        
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Matching completed in {execution_time:.2f} seconds")
        
        # Format response
        return RunMatchingResponse(
            status="success",
            message=f"Successfully matched {len(matches)} groups in {request.city}",
            diagnostics_id=save_result.get('diagnostics_id'),
            matches=[
                MatchResult(
                    group_id=m.group_id,
                    listing_id=m.listing_id,
                    group_score=m.group_score,
                    listing_score=m.listing_score,
                    group_rank=m.group_rank,
                    listing_rank=m.listing_rank,
                    matched_at=m.matched_at.isoformat(),
                    is_stable=m.is_stable
                )
                for m in matches
            ],
            diagnostics=DiagnosticsResult(
                city=diagnostics.city,
                date_window_start=diagnostics.date_window_start,
                date_window_end=diagnostics.date_window_end,
                total_groups=diagnostics.total_groups,
                total_listings=diagnostics.total_listings,
                feasible_pairs=diagnostics.feasible_pairs,
                matched_groups=diagnostics.matched_groups,
                matched_listings=diagnostics.matched_listings,
                unmatched_groups=diagnostics.unmatched_groups,
                unmatched_listings=diagnostics.unmatched_listings,
                proposals_sent=diagnostics.proposals_sent,
                proposals_rejected=diagnostics.proposals_rejected,
                iterations=diagnostics.iterations,
                avg_group_rank=diagnostics.avg_group_rank,
                avg_listing_rank=diagnostics.avg_listing_rank,
                match_quality_score=diagnostics.match_quality_score,
                is_stable=diagnostics.is_stable,
                executed_at=diagnostics.executed_at.isoformat()
            ),
            execution_time_seconds=execution_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running matching: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/active", response_model=ActiveMatchesResponse)
async def get_active_matches(
    city: Optional[str] = Query(None, description="Filter by city"),
    group_id: Optional[str] = Query(None, description="Filter by group ID"),
    listing_id: Optional[str] = Query(None, description="Filter by listing ID")
):
    """
    Get active matches with optional filters
    
    Returns all active matches, optionally filtered by:
    - city: Get matches in a specific city
    - group_id: Get matches for a specific group
    - listing_id: Get matches for a specific listing
    """
    try:
        supabase = get_admin_client()
        engine = MatchPersistenceEngine(supabase)
        
        matches = await engine.get_active_matches(
            city=city,
            group_id=group_id,
            listing_id=listing_id
        )
        
        return ActiveMatchesResponse(
            status="success",
            count=len(matches),
            matches=matches
        )
        
    except Exception as e:
        logger.error(f"Error getting active matches: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/stats", response_model=StatsResponse)
async def get_matching_stats(
    city: Optional[str] = Query(None, description="Filter by city")
):
    """
    Get matching statistics
    
    Returns aggregate statistics about matches, including:
    - Total active matches
    - Latest matching run details (if any)
    """
    try:
        supabase = get_admin_client()
        engine = MatchPersistenceEngine(supabase)
        
        stats = await engine.get_match_statistics(city=city)
        
        return StatsResponse(
            status="success",
            total_active_matches=stats.get('total_active_matches', 0),
            latest_run=stats.get('latest_run')
        )
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.delete("/group/{group_id}", response_model=DeleteResponse)
async def delete_matches_for_group(group_id: str):
    """
    Delete all matches for a specific group
    
    Use cases:
    - Group is dissolved
    - Group preferences changed significantly
    - Group wants to opt out of matching
    """
    try:
        supabase = get_admin_client()
        engine = MatchPersistenceEngine(supabase)
        
        count = await engine.delete_matches_for_group(group_id)
        
        return DeleteResponse(
            status="success",
            message=f"Deleted {count} matches for group {group_id}",
            deleted_count=count
        )
        
    except Exception as e:
        logger.error(f"Error deleting matches for group: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.delete("/listing/{listing_id}", response_model=DeleteResponse)
async def delete_matches_for_listing(listing_id: str):
    """
    Delete all matches for a specific listing
    
    Use cases:
    - Listing is removed/archived
    - Listing becomes unavailable
    - Listing details changed significantly
    """
    try:
        supabase = get_admin_client()
        engine = MatchPersistenceEngine(supabase)
        
        count = await engine.delete_matches_for_listing(listing_id)
        
        return DeleteResponse(
            status="success",
            message=f"Deleted {count} matches for listing {listing_id}",
            deleted_count=count
        )
        
    except Exception as e:
        logger.error(f"Error deleting matches for listing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/expire", response_model=ExpireResponse)
async def expire_old_matches(
    days_threshold: int = Query(30, description="Expire matches older than this many days")
):
    """
    Expire old matches
    
    Marks matches older than the threshold as 'expired'.
    Default: 30 days
    """
    try:
        supabase = get_admin_client()
        
        # Call the database function
        response = supabase.rpc('expire_old_matches', {'days_threshold': days_threshold}).execute()
        
        count = response.data if response.data is not None else 0
        
        return ExpireResponse(
            status="success",
            message=f"Expired {count} matches older than {days_threshold} days",
            expired_count=count
        )
        
    except Exception as e:
        logger.error(f"Error expiring matches: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# Export router
__all__ = ['router']
