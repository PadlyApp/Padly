"""Group listing ranking: matches, eligible-listings, ranked-listings, neural-ranked."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import settings
from app.dependencies.auth import get_user_token, require_user_token
from app.dependencies.supabase import get_admin_client
from app.services import ml_client
from app.services.auth_helpers import resolve_current_user_id, require_group_membership, safe_float, safe_int
from app.services.behavior_features import build_group_behavior_vector

from ._helpers import (
    build_user_payload_from_group,
    fetch_active_listings_for_group_location,
    normalize_group_record_for_response,
)

router = APIRouter()


def _build_legacy_rule_rankings(
    group: Dict[str, Any],
    eligible_listings: List[Dict[str, Any]],
    limit: int,
) -> List[Dict[str, Any]]:
    """Phase 1 legacy ranking: soft rule score over hard-filtered candidates."""
    from app.services.stable_matching.scoring import calculate_group_score

    group_size = safe_int(group.get("target_group_size"), default=2)
    group_size = max(1, group_size)

    ranked = []
    for listing in eligible_listings:
        score = float(calculate_group_score(group, listing))
        listing_copy = dict(listing)
        listing_copy["match_score"] = round(score, 2)
        listing_copy["match_percent"] = f"{round(score)}%"
        listing_price = safe_float(listing.get("price_per_month"), default=0.0)
        listing_copy["price_per_person"] = round(listing_price / group_size, 2)
        ranked.append(listing_copy)

    ranked.sort(
        key=lambda x: (-x.get("match_score", 0.0), x.get("price_per_month", float("inf")))
    )
    return ranked[:limit]


@router.get("/{group_id}/matches", response_model=dict)
async def get_group_matches(
    group_id: str,
    token: Optional[str] = Depends(get_user_token),
):
    """Phase 3B compatibility endpoint.

    Primary: neural-ranked listings.  Fallback: deterministic rule-ranked.
    """

    def to_legacy_data(ranked_listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for idx, listing in enumerate(ranked_listings, start=1):
            listing_id = listing.get("id") or listing.get("listing_id")
            normalized_listing = dict(listing)
            normalized_listing["id"] = listing_id
            out.append({
                "id": listing_id,
                "listing_id": listing_id,
                "group_rank": idx,
                "listing_rank": None,
                "group_score": listing.get("match_score"),
                "listing_score": None,
                "is_stable": False,
                "algorithm_version": listing.get("algorithm_version"),
                "score_breakdown": listing.get("score_breakdown"),
                "explainability": listing.get("explainability"),
                "listing": normalized_listing,
            })
        return out

    if token:
        try:
            response = await get_neural_ranked_listings_for_group(
                group_id=group_id,
                limit=50,
                shadow_compare=False,
                force_enable=True,
                token=token,
            )
            data = to_legacy_data(response.get("ranked_listings", []))
            return {
                "status": "success",
                "mode": "neural_cutover",
                "group_id": group_id,
                "count": len(data),
                "data": data,
                "fallback_used": False,
            }
        except HTTPException as exc:
            if exc.status_code not in {403, 503, 500}:
                raise

    fallback = await get_ranked_listings_for_group(
        group_id=group_id, limit=50, token=token
    )
    data = to_legacy_data(fallback.get("ranked_listings", []))
    return {
        "status": "success",
        "mode": "legacy_rule_fallback",
        "group_id": group_id,
        "count": len(data),
        "data": data,
        "fallback_used": True,
    }


@router.get("/{group_id}/eligible-listings", response_model=dict)
async def get_eligible_listings_for_group(
    group_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max listings to return"),
    token: Optional[str] = Depends(get_user_token),
):
    """Get listings that match the group's HARD CONSTRAINTS only."""
    from app.services.stable_matching import build_feasible_pairs, get_feasibility_statistics

    supabase = get_admin_client()
    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = group_response.data
    target_city = group.get("target_city")
    if not target_city:
        raise HTTPException(status_code=400, detail="Group must have a target city to find eligible listings")

    all_listings = fetch_active_listings_for_group_location(supabase, group)
    if not all_listings:
        return {
            "status": "success",
            "group_id": group_id,
            "group_constraints": {
                "target_city": target_city,
                "budget_min": group.get("budget_per_person_min"),
                "budget_max": group.get("budget_per_person_max"),
                "target_move_in_date": str(group.get("target_move_in_date")) if group.get("target_move_in_date") else None,
            },
            "count": 0,
            "listings": [],
            "message": f"No active listings found in {target_city}",
        }

    feasible_pairs, _ = build_feasible_pairs(
        groups=[group], listings=all_listings, date_delta_days=30, include_rejection_reasons=True
    )
    eligible_listing_ids = {listing_id for _, listing_id in feasible_pairs}

    eligible_listings = []
    for listing in all_listings:
        if listing["id"] in eligible_listing_ids:
            price = float(listing.get("price_per_month", 0))
            listing["price_per_person"] = round(price / 2, 2)
            eligible_listings.append(listing)

    eligible_listings.sort(key=lambda x: x.get("price_per_month", float("inf")))
    eligible_listings = eligible_listings[:limit]

    stats = get_feasibility_statistics([group], all_listings, feasible_pairs)

    return {
        "status": "success",
        "group_id": group_id,
        "group_constraints": {
            "target_city": target_city,
            "budget_min": group.get("budget_per_person_min"),
            "budget_max": group.get("budget_per_person_max"),
            "target_move_in_date": str(group.get("target_move_in_date")) if group.get("target_move_in_date") else None,
            "target_furnished": group.get("target_furnished"),
            "target_utilities_included": group.get("target_utilities_included"),
        },
        "stats": {
            "total_listings_in_city": stats["total_listings"],
            "eligible_count": stats["total_feasible_pairs"],
            "rejected_count": stats["listings_with_no_options"],
        },
        "count": len(eligible_listings),
        "listings": eligible_listings,
    }


@router.get("/{group_id}/ranked-listings", response_model=dict)
async def get_ranked_listings_for_group(
    group_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max ranked listings to return"),
    token: Optional[str] = Depends(get_user_token),
):
    """Deterministic fallback: hard constraint filter + soft rule-based scoring."""
    from app.services.stable_matching import build_feasible_pairs, get_feasibility_statistics
    from app.services.stable_matching.scoring import calculate_group_score

    supabase = get_admin_client()
    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).limit(1).execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = group_response.data[0]
    target_city = group.get("target_city")
    if not target_city:
        raise HTTPException(status_code=400, detail="Group must have a target city")

    all_listings = fetch_active_listings_for_group_location(supabase, group)
    if not all_listings:
        return {
            "status": "success",
            "group_id": group_id,
            "count": 0,
            "ranked_listings": [],
            "message": f"No active listings found in {target_city}",
        }

    feasible_pairs, _ = build_feasible_pairs(
        groups=[group], listings=all_listings, date_delta_days=30, include_rejection_reasons=True
    )
    eligible_listing_ids = {listing_id for _, listing_id in feasible_pairs}

    group_size = max(int(group.get("target_group_size") or group.get("current_member_count") or 2), 1)

    ranked = []
    for listing in all_listings:
        if listing["id"] not in eligible_listing_ids:
            continue
        score = float(calculate_group_score(group, listing))
        listing_copy = dict(listing)
        listing_copy["match_score"] = round(score, 2)
        listing_copy["match_percent"] = f"{round(score)}%"
        listing_price = float(listing.get("price_per_month") or 0.0)
        listing_copy["price_per_person"] = round(listing_price / group_size, 2)
        ranked.append(listing_copy)

    ranked.sort(key=lambda x: (-x.get("match_score", 0.0), x.get("price_per_month", float("inf"))))
    ranked = ranked[:limit]

    stats = get_feasibility_statistics([group], all_listings, feasible_pairs)

    return {
        "status": "success",
        "group_id": group_id,
        "group_constraints": {
            "target_city": target_city,
            "budget_min": group.get("budget_per_person_min"),
            "budget_max": group.get("budget_per_person_max"),
            "target_move_in_date": str(group.get("target_move_in_date")) if group.get("target_move_in_date") else None,
            "target_lease_type": group.get("target_lease_type"),
            "target_lease_duration_months": group.get("target_lease_duration_months"),
            "target_bathrooms": group.get("target_bathrooms"),
            "target_furnished": group.get("target_furnished"),
            "target_utilities_included": group.get("target_utilities_included"),
            "target_deposit_amount": group.get("target_deposit_amount"),
            "target_house_rules": group.get("target_house_rules"),
        },
        "stats": {
            "total_listings_in_city": stats["total_listings"],
            "eligible_count": stats["total_feasible_pairs"],
            "returned_count": len(ranked),
        },
        "count": len(ranked),
        "ranked_listings": ranked,
    }


@router.get("/{group_id}/neural-ranked-listings", response_model=dict)
async def get_neural_ranked_listings_for_group(
    group_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max ranked listings to return"),
    shadow_compare: bool = Query(False),
    force_enable: bool = Query(False),
    token: str = Depends(require_user_token),
):
    """Phase 3A Group -> Listing neural-ranked feed."""
    from app.services.stable_matching import build_feasible_pairs, get_feasibility_statistics

    ranking_enabled = settings.padly_group_neural_ranking_enabled
    kill_switch = settings.padly_group_neural_kill_switch

    if kill_switch:
        raise HTTPException(status_code=503, detail="Group neural ranking is temporarily disabled by kill switch.")
    if not ranking_enabled and not force_enable:
        raise HTTPException(
            status_code=503,
            detail="Group neural ranking is not enabled yet. Set PADLY_GROUP_NEURAL_RANKING_ENABLED=true or use force_enable for testing.",
        )

    supabase = get_admin_client()
    current_user_id = resolve_current_user_id(token)
    require_group_membership(group_id=group_id, user_id=current_user_id)

    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).limit(1).execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = group_response.data[0]

    target_city = group.get("target_city")
    if not target_city:
        raise HTTPException(status_code=400, detail="Group must have a target city")

    all_listings = fetch_active_listings_for_group_location(supabase, group)
    if not all_listings:
        return {
            "status": "success",
            "mode": "group_neural_ranked",
            "group_id": group_id,
            "count": 0,
            "ranked_listings": [],
            "message": f"No active listings found in {target_city}",
        }

    feasible_pairs, _ = build_feasible_pairs(
        groups=[group], listings=all_listings, date_delta_days=30, include_rejection_reasons=True
    )
    eligible_listing_ids = {listing_id for _, listing_id in feasible_pairs}
    eligible_listings = [l for l in all_listings if l.get("id") in eligible_listing_ids]
    feasibility_stats = get_feasibility_statistics([group], all_listings, feasible_pairs)

    if not eligible_listings:
        return {
            "status": "success",
            "mode": "group_neural_ranked",
            "group_id": group_id,
            "stats": {
                "total_listings_in_city": feasibility_stats["total_listings"],
                "eligible_count": feasibility_stats["total_feasible_pairs"],
                "returned_count": 0,
            },
            "count": 0,
            "ranked_listings": [],
            "message": "No hard-eligible listings found for this group.",
        }

    warnings: List[str] = []
    behavior = None
    try:
        behavior = build_group_behavior_vector(group_id=group_id, days=180, max_events_per_user=2000)
    except Exception as e:
        warnings.append(f"Behavior vector unavailable, using neutral behavior prior: {e}")

    user_payload = build_user_payload_from_group(group=group, behavior=behavior)
    scored = await ml_client.score_listings(user_payload, eligible_listings, top_n=limit)

    invalid_ids = [str(item.get("id")) for item in scored if item.get("id") not in eligible_listing_ids]
    if invalid_ids:
        raise HTTPException(
            status_code=500,
            detail=f"Hard-filter guardrail violation. Ranked non-eligible listings: {invalid_ids[:5]}",
        )

    group_size = max(safe_int(group.get("target_group_size") or group.get("current_member_count") or 2, default=2), 1)

    ranked_listings = []
    for item in scored:
        listing = dict(item)
        listing["listing_id"] = str(item.get("id") or "")
        listing_price = safe_float(item.get("price_per_month"), default=0.0)
        listing["price_per_person"] = round(listing_price / group_size, 2)
        ranked_listings.append(listing)

    shadow_comparison = None
    if shadow_compare:
        legacy_ranked = _build_legacy_rule_rankings(group=group, eligible_listings=eligible_listings, limit=limit)
        neural_ids = [str(x.get("id")) for x in ranked_listings]
        legacy_ids = [str(x.get("id")) for x in legacy_ranked]
        neural_top = neural_ids[:limit]
        legacy_top = legacy_ids[:limit]
        overlap = len(set(neural_top).intersection(set(legacy_top)))
        denom = len(set(neural_top).union(set(legacy_top))) or 1
        shadow_comparison = {
            "enabled": True,
            "top_k": limit,
            "overlap_count": overlap,
            "overlap_rate": round(overlap / max(1, min(len(neural_top), len(legacy_top))), 4),
            "jaccard_top_k": round(overlap / denom, 4),
            "legacy_only_top_ids": [x for x in legacy_top if x not in set(neural_top)][:10],
            "neural_only_top_ids": [x for x in neural_top if x not in set(legacy_top)][:10],
        }

    return {
        "status": "success",
        "mode": "group_neural_ranked",
        "group_id": group_id,
        "feature_flags": {
            "group_neural_ranking_enabled": ranking_enabled,
            "group_neural_kill_switch": kill_switch,
            "force_enable": force_enable,
        },
        "group_constraints": {
            "target_city": target_city,
            "budget_min": group.get("budget_per_person_min"),
            "budget_max": group.get("budget_per_person_max"),
            "target_move_in_date": str(group.get("target_move_in_date")) if group.get("target_move_in_date") else None,
        },
        "stats": {
            "total_listings_in_city": feasibility_stats["total_listings"],
            "eligible_count": feasibility_stats["total_feasible_pairs"],
            "returned_count": len(ranked_listings),
        },
        "behavior_context": {
            "sample_size": user_payload.get("behavior_sample_size"),
            "has_behavior_signal": any(
                user_payload.get(key) is not None
                for key in ("liked_mean_price", "liked_mean_beds", "liked_mean_sqfeet")
            ),
        },
        "warnings": warnings,
        "count": len(ranked_listings),
        "ranked_listings": ranked_listings,
        "shadow_comparison": shadow_comparison,
    }


# ---------------------------------------------------------------------------
# Retired confirmation endpoints
# ---------------------------------------------------------------------------

@router.post("/{group_id}/confirm-match", response_model=dict)
async def confirm_match_as_group(group_id: str, token: str = Depends(require_user_token)):
    raise HTTPException(status_code=410, detail="Stable match confirmations have been retired.")


@router.delete("/{group_id}/reject-match", response_model=dict)
async def reject_match_as_group(group_id: str, token: str = Depends(require_user_token)):
    raise HTTPException(status_code=410, detail="Stable match rejections have been retired.")
