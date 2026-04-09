"""Group CRUD operations: list, get, create, update, delete."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.auth import require_user_token, resolve_auth_user
from app.dependencies.supabase import get_admin_client
from app.models import RoommateGroupCreate, RoommateGroupUpdate
from app.services.controlled_vocab import validate_city_name, validate_neighborhoods

from ._helpers import (
    maybe_trigger_legacy_stable_matching,
    normalize_group_preference_payload,
    normalize_group_record_for_response,
    resolve_auth_user_to_app_id,
    to_json_serializable_payload,
)

router = APIRouter()


@router.get("/", response_model=dict)
async def list_groups(
    token: str = Depends(require_user_token),
    status: Optional[str] = Query(None, description="Filter by status (active, inactive, matched)"),
    city: Optional[str] = Query(None, description="Filter by target city"),
    my_groups: bool = Query(False, description="Only show groups I'm a member of"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List roommate groups with optional filters."""
    supabase = get_admin_client()

    query = supabase.table("roommate_groups").select("*")
    if status:
        query = query.eq("status", status)
    if city:
        query = query.ilike("target_city", f"%{city}%")
    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)

    response = query.execute()
    groups = response.data

    if my_groups and token:
        auth_user = resolve_auth_user(supabase, token)
        if auth_user:
            auth_user_id = auth_user.id
            user_record = (
                supabase.table("users")
                .select("id")
                .eq("auth_id", auth_user_id)
                .execute()
            )
            if user_record.data:
                user_id = user_record.data[0]["id"]
                member_response = (
                    supabase.table("group_members")
                    .select("group_id")
                    .eq("user_id", user_id)
                    .eq("status", "accepted")
                    .execute()
                )
                member_group_ids = [m["group_id"] for m in member_response.data]
                groups = [g for g in groups if g["id"] in member_group_ids]
            else:
                groups = []

    if groups:
        group_ids = [g["id"] for g in groups]
        members_response = (
            supabase.table("group_members")
            .select("group_id")
            .in_("group_id", group_ids)
            .eq("status", "accepted")
            .execute()
        )
        member_counts: dict = {}
        for member in members_response.data:
            gid = member["group_id"]
            member_counts[gid] = member_counts.get(gid, 0) + 1
        for group in groups:
            group["current_member_count"] = member_counts.get(group["id"], 0)
            normalized = normalize_group_record_for_response(group)
            group.clear()
            group.update(normalized)

    return {"status": "success", "count": len(groups), "data": groups}


@router.get("/{group_id}", response_model=dict)
async def get_group(
    group_id: str,
    token: str = Depends(require_user_token),
    include_members: bool = Query(True, description="Include member details"),
):
    """Get a single roommate group by ID."""
    supabase = get_admin_client()

    group_response = (
        supabase.table("roommate_groups")
        .select("*")
        .eq("id", group_id)
        .single()
        .execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")

    group = group_response.data

    if include_members:
        members_response = (
            supabase.table("group_members")
            .select("*, users(id, email, full_name)")
            .eq("group_id", group_id)
            .execute()
        )
        members = []
        for member in members_response.data:
            user_data = (
                member.get("users", {})
                if isinstance(member.get("users"), dict)
                else {}
            )
            members.append(
                {
                    "id": member.get("id"),
                    "group_id": member.get("group_id"),
                    "user_id": member.get("user_id"),
                    "is_creator": member.get("is_creator", False),
                    "status": member.get("status", "unknown"),
                    "joined_at": member.get("joined_at"),
                    "user_name": user_data.get("full_name"),
                }
            )
        group["members"] = members
        group["member_count"] = len(
            [m for m in members if m.get("status") == "accepted"]
        )

    return {"status": "success", "data": group}


@router.post("/", response_model=dict)
async def create_group(
    group_data: RoommateGroupCreate,
    token: str = Depends(require_user_token),
):
    """Create a new roommate group and add the creator as the first member."""
    supabase = get_admin_client()
    user_id = resolve_auth_user_to_app_id(supabase, token)

    group_dict = group_data.model_dump(exclude_none=True)
    group_dict = normalize_group_preference_payload(group_dict)
    group_dict["creator_user_id"] = user_id

    try:
        group_dict["target_city"] = validate_city_name(group_dict.get("target_city", ""))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if "preferred_neighborhoods" in group_dict:
        try:
            group_dict["preferred_neighborhoods"] = validate_neighborhoods(
                group_dict.get("target_city", ""),
                group_dict.get("preferred_neighborhoods"),
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    group_dict = to_json_serializable_payload(group_dict)

    group_response = supabase.table("roommate_groups").insert(group_dict).execute()
    if not group_response.data:
        raise HTTPException(status_code=500, detail="Failed to create group")

    created_group = normalize_group_record_for_response(group_response.data[0])
    group_id = created_group["id"]

    supabase.table("group_members").insert(
        {"group_id": group_id, "user_id": user_id, "is_creator": True, "status": "accepted"}
    ).execute()

    matching_result = await maybe_trigger_legacy_stable_matching(
        target_city=created_group.get("target_city"), reason="group_created"
    )

    return {
        "status": "success",
        "message": "Group created successfully",
        "data": created_group,
        "matching": matching_result,
    }


@router.put("/{group_id}", response_model=dict)
async def update_group(
    group_id: str,
    group_data: RoommateGroupUpdate,
    token: str = Depends(require_user_token),
):
    """Update a roommate group.  Only the creator can update."""
    supabase = get_admin_client()
    user_id = resolve_auth_user_to_app_id(supabase, token)

    member_response = (
        supabase.table("group_members")
        .select("is_creator")
        .eq("group_id", group_id)
        .eq("user_id", user_id)
        .eq("status", "accepted")
        .execute()
    )
    if not member_response.data:
        raise HTTPException(status_code=403, detail="You are not a member of this group")
    if not member_response.data[0].get("is_creator"):
        raise HTTPException(status_code=403, detail="Only the group creator can edit the group")

    group_response = (
        supabase.table("roommate_groups")
        .select("*")
        .eq("id", group_id)
        .single()
        .execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")

    group = normalize_group_record_for_response(group_response.data)

    update_dict = group_data.model_dump(exclude_none=True)
    update_dict = normalize_group_preference_payload(update_dict)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No data provided for update")

    if "target_city" in update_dict:
        try:
            update_dict["target_city"] = validate_city_name(update_dict.get("target_city", ""))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    if "preferred_neighborhoods" in update_dict:
        effective_city = update_dict.get("target_city") or group.get("target_city")
        try:
            update_dict["preferred_neighborhoods"] = validate_neighborhoods(
                effective_city or "", update_dict.get("preferred_neighborhoods")
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    update_dict = to_json_serializable_payload(update_dict)

    updated_response = (
        supabase.table("roommate_groups")
        .update(update_dict)
        .eq("id", group_id)
        .execute()
    )

    preference_fields = [
        "budget_per_person_min", "budget_per_person_max",
        "target_move_in_date", "target_city",
    ]
    matching_result = {"status": "skipped", "message": "No preference changes detected"}
    if any(field in update_dict for field in preference_fields):
        target_city = update_dict.get("target_city") or group.get("target_city")
        matching_result = await maybe_trigger_legacy_stable_matching(
            target_city=target_city, reason="group_updated"
        )

    return {
        "status": "success",
        "message": "Group updated successfully",
        "data": (
            normalize_group_record_for_response(updated_response.data[0])
            if updated_response.data
            else None
        ),
        "matching": matching_result,
    }


@router.delete("/{group_id}", response_model=dict)
async def delete_group(
    group_id: str,
    token: str = Depends(require_user_token),
):
    """Delete a roommate group.  Only the creator can delete."""
    supabase = get_admin_client()
    user_id = resolve_auth_user_to_app_id(supabase, token)

    group_response = (
        supabase.table("roommate_groups")
        .select("*")
        .eq("id", group_id)
        .single()
        .execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")

    group = group_response.data
    if group["creator_user_id"] != user_id:
        raise HTTPException(
            status_code=403, detail="Only the group creator can delete this group"
        )

    supabase.table("group_members").delete().eq("group_id", group_id).execute()
    supabase.table("roommate_groups").delete().eq("id", group_id).execute()

    return {"status": "success", "message": "Group deleted successfully"}
