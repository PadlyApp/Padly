"""
Shared helpers for the groups sub-package.

Contains preference normalisation, payload serialisation, and common
Supabase query patterns that are used by multiple groups sub-routers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.dependencies.auth import resolve_auth_user
from app.dependencies.supabase import get_admin_client
from app.services.location_matching import filter_listings_for_location
from app.services.preferences_contract import (
    normalize_lease_type,
    resolve_furnished_preference,
    target_furnished_from_preference,
)
from app.services.auth_helpers import safe_float, safe_int


# ---------------------------------------------------------------------------
# Preference normalisation
# ---------------------------------------------------------------------------

def normalize_group_preference_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Keep personal-style and group-legacy field names in sync."""
    out = dict(payload)

    if out.get("budget_min") is not None and out.get("budget_per_person_min") is None:
        out["budget_per_person_min"] = out["budget_min"]
    if out.get("budget_per_person_min") is not None and out.get("budget_min") is None:
        out["budget_min"] = out["budget_per_person_min"]
    if out.get("budget_max") is not None and out.get("budget_per_person_max") is None:
        out["budget_per_person_max"] = out["budget_max"]
    if out.get("budget_per_person_max") is not None and out.get("budget_max") is None:
        out["budget_max"] = out["budget_per_person_max"]

    if out.get("move_in_date") is not None and out.get("target_move_in_date") is None:
        out["target_move_in_date"] = out["move_in_date"]
    if out.get("target_move_in_date") is not None and out.get("move_in_date") is None:
        out["move_in_date"] = out["target_move_in_date"]

    if out.get("required_bedrooms") is not None and out.get("target_bedrooms") is None:
        out["target_bedrooms"] = out["required_bedrooms"]
    if out.get("target_bedrooms") is not None and out.get("required_bedrooms") is None:
        out["required_bedrooms"] = out["target_bedrooms"]

    furnished_pref = resolve_furnished_preference(
        out.get("furnished_preference"),
        out.get("target_furnished"),
    )
    if furnished_pref is not None:
        out["furnished_preference"] = furnished_pref
        out["target_furnished"] = target_furnished_from_preference(furnished_pref)
        out["furnished_is_hard"] = furnished_pref == "required"

    if "target_lease_type" in out and out.get("target_lease_type") is not None:
        normalized_lease_type = normalize_lease_type(out.get("target_lease_type"))
        if normalized_lease_type is not None:
            out["target_lease_type"] = normalized_lease_type

    if out.get("preferred_neighborhoods") is not None:
        values = [
            str(v).strip()
            for v in (out.get("preferred_neighborhoods") or [])
            if str(v).strip()
        ]
        out["preferred_neighborhoods"] = list(dict.fromkeys(values))
    if out.get("lifestyle_preferences") is not None and not isinstance(
        out.get("lifestyle_preferences"), dict
    ):
        out["lifestyle_preferences"] = {}

    return out


def to_json_serializable_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Decimal/date-like values for Supabase JSON serialisation."""
    from decimal import Decimal
    from datetime import date as date_type, datetime as datetime_type

    out = dict(payload)
    for key, value in list(out.items()):
        if isinstance(value, Decimal):
            out[key] = float(value)
        elif isinstance(value, date_type) and not isinstance(value, datetime_type):
            out[key] = value.isoformat()
    return out


def normalize_group_record_for_response(group: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure response payloads expose both personal-style and legacy group aliases."""
    if not isinstance(group, dict):
        return group
    return normalize_group_preference_payload(group)


# ---------------------------------------------------------------------------
# Aggregate preferences
# ---------------------------------------------------------------------------

def build_group_update_from_aggregate_prefs(
    aggregate_prefs: Dict[str, Any],
) -> Dict[str, Any]:
    allowed_fields = [
        "target_country", "target_state_province", "target_city",
        "budget_min", "budget_max", "budget_per_person_min", "budget_per_person_max",
        "move_in_date", "target_move_in_date", "required_bedrooms", "target_bedrooms",
        "target_bathrooms", "target_furnished", "furnished_preference", "furnished_is_hard",
        "target_utilities_included", "target_deposit_amount", "gender_policy",
        "target_lease_type", "target_lease_duration_months", "target_house_rules",
        "preferred_neighborhoods", "lifestyle_preferences",
    ]

    nullable_passthrough_fields = {
        "target_furnished", "target_utilities_included", "target_deposit_amount",
        "target_house_rules", "target_lease_type", "target_lease_duration_months",
    }

    update_data: Dict[str, Any] = {}
    for key in allowed_fields:
        if key not in aggregate_prefs:
            continue
        if aggregate_prefs[key] is not None or key in nullable_passthrough_fields:
            update_data[key] = aggregate_prefs[key]

    update_data = normalize_group_preference_payload(update_data)
    return to_json_serializable_payload(update_data)


def aggregate_and_persist_group_preferences(group_id: str) -> Dict[str, Any]:
    """Recompute aggregate preferences for a group and persist them."""
    from app.services.group_preferences_aggregator import calculate_aggregate_group_preferences

    supabase = get_admin_client()
    aggregate_prefs = calculate_aggregate_group_preferences(group_id)
    update_data = build_group_update_from_aggregate_prefs(aggregate_prefs)

    if not update_data:
        return {"status": "skipped"}

    supabase.table("roommate_groups").update(update_data).eq("id", group_id).execute()
    return {
        "status": "success",
        "updated_fields": list(update_data.keys()),
        "aggregate_prefs": {
            "budget_min": update_data.get("budget_min"),
            "budget_max": update_data.get("budget_max"),
            "move_in_date": update_data.get("move_in_date"),
            "required_bedrooms": update_data.get("required_bedrooms"),
            "target_bathrooms": update_data.get("target_bathrooms"),
            "furnished_preference": update_data.get("furnished_preference"),
            "gender_policy": update_data.get("gender_policy"),
        },
    }


# ---------------------------------------------------------------------------
# Listing helpers
# ---------------------------------------------------------------------------

def fetch_active_listings_for_group_location(
    supabase: Any,
    group: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Load all active listings, then apply metro-aware location matching."""
    page_size = 1000
    page = 0
    listings: List[Dict[str, Any]] = []

    while True:
        batch = (
            supabase.table("listings")
            .select("*")
            .eq("status", "active")
            .range(page * page_size, page * page_size + page_size - 1)
            .execute()
            .data
            or []
        )
        if not batch:
            break
        listings.extend(batch)
        if len(batch) < page_size:
            break
        page += 1

    return filter_listings_for_location(
        listings,
        target_city=group.get("target_city"),
        target_state=group.get("target_state_province"),
        target_country=group.get("target_country"),
    )


# ---------------------------------------------------------------------------
# Legacy stable-matching stub
# ---------------------------------------------------------------------------

async def maybe_trigger_legacy_stable_matching(
    target_city: Optional[str],
    reason: str,
) -> Dict[str, Any]:
    """Stable matching has been retired.  Preserve response shape for legacy callers."""
    return {
        "status": "retired",
        "city": target_city,
        "message": f"Legacy stable matching has been removed (reason={reason}).",
    }


# ---------------------------------------------------------------------------
# User-payload builder for group ranking
# ---------------------------------------------------------------------------

def build_user_payload_from_group(
    group: Dict[str, Any],
    behavior: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Map group constraints + behavior context into recommender user payload."""
    group_size = safe_int(
        group.get("target_group_size") or group.get("current_member_count") or 2,
        default=2,
    )
    group_size = max(1, group_size)
    required_beds = safe_int(group.get("required_bedrooms"), default=0)
    desired_beds = max(group_size, required_beds) if required_beds else float(group_size)

    furnished_preference = str(group.get("furnished_preference") or "").strip().lower()
    wants_furnished = None
    if furnished_preference in {"required", "preferred"}:
        wants_furnished = 1
    elif group.get("target_furnished") is True:
        wants_furnished = 1
    elif group.get("target_furnished") is False:
        wants_furnished = 0

    vector = (behavior or {}).get("vector") or {}
    return {
        "budget_min": safe_float(group.get("budget_per_person_min"), default=0.0) or None,
        "budget_max": safe_float(group.get("budget_per_person_max"), default=0.0) or None,
        "desired_beds": desired_beds,
        "desired_baths": safe_float(group.get("target_bathrooms"), default=0.0) or None,
        "wants_furnished": wants_furnished,
        "liked_mean_price": vector.get("liked_mean_price"),
        "liked_mean_beds": vector.get("liked_mean_beds"),
        "liked_mean_sqfeet": vector.get("liked_mean_sqfeet"),
        "behavior_sample_size": safe_int((behavior or {}).get("sample_size"), default=0),
    }


# ---------------------------------------------------------------------------
# Auth resolve (resolve auth user → app user id)
# ---------------------------------------------------------------------------

def resolve_auth_user_to_app_id(supabase: Any, token: str) -> str:
    """Auth user → users table id, raising 404 if not found."""
    auth_user = resolve_auth_user(supabase, token)
    auth_user_id = auth_user.id

    user_record = (
        supabase.table("users").select("id").eq("auth_id", auth_user_id).execute()
    )
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    return user_record.data[0]["id"]
