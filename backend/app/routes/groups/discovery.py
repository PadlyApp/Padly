"""Group discovery: discover compatible groups, pending requests, compatible users."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.auth import require_user_token, resolve_auth_user
from app.dependencies.supabase import get_admin_client
from app.services.location_matching import cities_match

from ._helpers import (
    normalize_group_record_for_response,
    resolve_auth_user_to_app_id,
)

router = APIRouter()


@router.get("/discover", response_model=dict)
async def discover_groups(
    city: str = Query(..., description="Target city"),
    budget_min: Optional[float] = Query(None, description="Minimum budget per person"),
    budget_max: Optional[float] = Query(None, description="Maximum budget per person"),
    move_in_date: Optional[str] = Query(None, description="Target move-in date (ISO format)"),
    min_compatibility_score: int = Query(50, ge=0, le=100, description="Minimum compatibility score"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    token: str = Depends(require_user_token),
):
    """Discover compatible roommate groups based on user preferences."""
    from app.services.user_group_matching import find_compatible_groups

    supabase = get_admin_client()
    auth_user = resolve_auth_user(supabase, token)
    user_id = auth_user.id

    user_db_response = (
        supabase.table("users").select("*").eq("id", user_id).single().execute()
    )
    if not user_db_response.data:
        raise HTTPException(status_code=404, detail="User profile not found")

    prefs_response = (
        supabase.table("personal_preferences").select("*").eq("user_id", user_id).execute()
    )
    if prefs_response.data:
        user_prefs = prefs_response.data[0]
    else:
        user_prefs = {
            "target_city": city,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "move_in_date": move_in_date,
        }

    if budget_min is not None:
        user_prefs["budget_min"] = budget_min
    if budget_max is not None:
        user_prefs["budget_max"] = budget_max
    if move_in_date is not None:
        user_prefs["move_in_date"] = move_in_date
    if not user_prefs.get("target_city"):
        user_prefs["target_city"] = city

    compatible_groups = await find_compatible_groups(
        user_id=user_id,
        user_prefs=user_prefs,
        min_score=min_compatibility_score,
        limit=limit,
    )

    formatted_groups = []
    for group in compatible_groups:
        members_response = (
            supabase.table("group_members")
            .select("*, users(id, full_name, company_name, school_name, verification_status)")
            .eq("group_id", group["id"])
            .eq("status", "accepted")
            .execute()
        )
        members = []
        for md in members_response.data:
            ud = md.get("users", {}) if isinstance(md.get("users"), dict) else {}
            members.append({
                "id": ud.get("id"),
                "full_name": ud.get("full_name"),
                "company_name": ud.get("company_name"),
                "school_name": ud.get("school_name"),
                "verification_status": ud.get("verification_status"),
                "is_creator": md.get("is_creator", False),
            })

        current_count = group.get("current_member_count", len(members))
        target_size = group.get("target_group_size")
        open_spots = (target_size - current_count) if target_size else None

        formatted_groups.append({
            "id": group["id"],
            "group_name": group["group_name"],
            "description": group.get("description"),
            "target_city": group["target_city"],
            "budget_per_person_min": group.get("budget_per_person_min"),
            "budget_per_person_max": group.get("budget_per_person_max"),
            "target_move_in_date": str(group["target_move_in_date"]) if group.get("target_move_in_date") else None,
            "target_group_size": target_size,
            "current_member_count": current_count,
            "open_spots": open_spots,
            "members": members,
            "compatibility": group["compatibility"],
            "created_at": str(group["created_at"]) if group.get("created_at") else None,
        })

    return {"status": "success", "count": len(formatted_groups), "groups": formatted_groups}


@router.get("/{group_id}/pending-requests", response_model=dict)
async def get_pending_requests(group_id: str, token: str = Depends(require_user_token)):
    """Get pending join requests for a group (creator only)."""
    from app.services.user_group_matching import calculate_user_group_compatibility

    supabase = get_admin_client()
    current_user_id = resolve_auth_user_to_app_id(supabase, token)

    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = normalize_group_record_for_response(group_response.data)
    if group["creator_user_id"] != current_user_id:
        raise HTTPException(status_code=403, detail="Only group creator can view pending requests")

    pending_response = (
        supabase.table("group_members")
        .select("*, users(id, email, full_name, company_name, school_name, verification_status, profile_picture_url)")
        .eq("group_id", group_id)
        .eq("status", "pending")
        .execute()
    )

    requests = []
    for md in pending_response.data:
        ud = md.get("users", {}) if isinstance(md.get("users"), dict) else {}
        uid = ud.get("id")
        if not uid:
            continue

        prefs_response = (
            supabase.table("personal_preferences").select("*").eq("user_id", uid).execute()
        )
        user_prefs = prefs_response.data[0] if prefs_response.data else {}
        compatibility = calculate_user_group_compatibility(ud, user_prefs, group)

        requests.append({
            "user_id": uid,
            "full_name": ud.get("full_name"),
            "company_name": ud.get("company_name"),
            "school_name": ud.get("school_name"),
            "verification_status": ud.get("verification_status"),
            "profile_picture_url": ud.get("profile_picture_url"),
            "requested_at": str(md.get("joined_at")) if md.get("joined_at") else None,
            "user_preferences": {
                "budget_min": user_prefs.get("budget_min"),
                "budget_max": user_prefs.get("budget_max"),
                "target_city": user_prefs.get("target_city"),
                "move_in_date": str(user_prefs.get("move_in_date")) if user_prefs.get("move_in_date") else None,
                "lifestyle_preferences": user_prefs.get("lifestyle_preferences", {}),
            },
            "compatibility": compatibility,
        })

    requests.sort(key=lambda r: r["compatibility"]["score"], reverse=True)
    return {"status": "success", "count": len(requests), "requests": requests}


@router.get("/{group_id}/compatible-users", response_model=dict)
async def get_compatible_users(group_id: str, token: str = Depends(require_user_token)):
    """Get users who are compatible with the group's hard constraints."""
    supabase = get_admin_client()
    current_user_id = resolve_auth_user_to_app_id(supabase, token)

    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = group_response.data

    member_check = (
        supabase.table("group_members")
        .select("user_id")
        .eq("group_id", group_id)
        .eq("user_id", current_user_id)
        .eq("status", "accepted")
        .execute()
    )
    if not member_check.data:
        raise HTTPException(status_code=403, detail="Only group members can view compatible users")

    existing_members = (
        supabase.table("group_members").select("user_id").eq("group_id", group_id).execute()
    )
    excluded_user_ids = [m["user_id"] for m in existing_members.data]

    users_response = (
        supabase.table("users")
        .select("id, email, full_name, profile_picture_url, company_name, school_name, verification_status, bio")
        .execute()
    )
    prefs_response = supabase.table("personal_preferences").select("*").execute()
    prefs_map = {p["user_id"]: p for p in prefs_response.data}

    compatible_users = []
    group_city = group.get("target_city", "").strip()
    group_budget_min = group.get("budget_per_person_min") or 0
    group_budget_max = group.get("budget_per_person_max") or float("inf")
    group_move_in = group.get("target_move_in_date")

    for user_data in users_response.data:
        uid = user_data["id"]
        if uid in excluded_user_ids:
            continue

        prefs = prefs_map.get(uid, {})

        user_city = (prefs.get("target_city") or "").strip()
        if group_city and user_city and not cities_match(group_city, user_city):
            continue

        user_budget_min = prefs.get("budget_min") or 0
        user_budget_max = prefs.get("budget_max") or float("inf")
        if user_budget_max < group_budget_min or user_budget_min > group_budget_max:
            continue

        if group_move_in and prefs.get("move_in_date"):
            from datetime import datetime
            try:
                group_date = (
                    datetime.fromisoformat(str(group_move_in).replace("Z", "+00:00")).date()
                    if isinstance(group_move_in, str) else group_move_in
                )
                user_date = (
                    datetime.fromisoformat(str(prefs["move_in_date"]).replace("Z", "+00:00")).date()
                    if isinstance(prefs["move_in_date"], str) else prefs["move_in_date"]
                )
                if abs((group_date - user_date).days) > 30:
                    continue
            except (ValueError, TypeError):
                pass

        user_lifestyle = prefs.get("lifestyle_preferences", {}) or {}

        compatible_users.append({
            "id": uid,
            "full_name": user_data.get("full_name"),
            "profile_picture_url": user_data.get("profile_picture_url"),
            "company_name": user_data.get("company_name"),
            "school_name": user_data.get("school_name"),
            "verification_status": user_data.get("verification_status"),
            "bio": user_data.get("bio"),
            "preferences": {
                "target_city": prefs.get("target_city"),
                "budget_min": prefs.get("budget_min"),
                "budget_max": prefs.get("budget_max"),
                "move_in_date": str(prefs.get("move_in_date")) if prefs.get("move_in_date") else None,
                "lifestyle_preferences": user_lifestyle,
                "preferred_neighborhoods": prefs.get("preferred_neighborhoods", []),
            },
            "compatibility_score": 100,
        })

    compatible_users.sort(key=lambda u: u["compatibility_score"], reverse=True)

    return {
        "status": "success",
        "group_id": group_id,
        "group_constraints": {
            "target_city": group.get("target_city"),
            "budget_min": group.get("budget_per_person_min"),
            "budget_max": group.get("budget_per_person_max"),
            "move_in_date": str(group.get("target_move_in_date")) if group.get("target_move_in_date") else None,
        },
        "count": len(compatible_users),
        "users": compatible_users,
    }
