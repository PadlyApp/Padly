"""Member management: invite, join, leave, accept/reject requests."""

from __future__ import annotations

import random
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies.auth import require_user_token, resolve_auth_user
from app.dependencies.supabase import get_admin_client

from ._helpers import (
    aggregate_and_persist_group_preferences,
    maybe_trigger_legacy_stable_matching,
    normalize_group_record_for_response,
    resolve_auth_user_to_app_id,
)

router = APIRouter()


class GroupMemberInvite(BaseModel):
    user_email: str
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Pending requests (user's own)
# ---------------------------------------------------------------------------

@router.get("/my-pending-requests", response_model=dict)
async def get_my_pending_requests(token: str = Depends(require_user_token)):
    """Get all pending join requests for the current user."""
    supabase = get_admin_client()
    user_id = resolve_auth_user_to_app_id(supabase, token)

    pending_response = (
        supabase.table("group_members")
        .select("group_id, joined_at, roommate_groups(id, group_name, target_city, status)")
        .eq("user_id", user_id)
        .eq("status", "pending")
        .execute()
    )

    pending_requests = []
    for membership in pending_response.data:
        group_data = membership.get("roommate_groups", {}) if membership.get("roommate_groups") else {}
        pending_requests.append({
            "group_id": membership["group_id"],
            "group_name": group_data.get("group_name"),
            "target_city": group_data.get("target_city"),
            "group_status": group_data.get("status"),
            "requested_at": membership.get("joined_at"),
        })

    return {"status": "success", "count": len(pending_requests), "data": pending_requests}


# ---------------------------------------------------------------------------
# List / get members
# ---------------------------------------------------------------------------

@router.get("/{group_id}/members", response_model=dict)
async def get_group_members(
    group_id: str,
    token: str = Depends(require_user_token),
    status_filter: Optional[str] = Query(None, description="Filter by member status"),
):
    """Get all members of a group."""
    supabase = get_admin_client()

    group_response = (
        supabase.table("roommate_groups").select("id").eq("id", group_id).single().execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")

    query = (
        supabase.table("group_members")
        .select("*, users(id, email, full_name, profile_picture_url)")
        .eq("group_id", group_id)
    )
    if status_filter:
        query = query.eq("status", status_filter)
    members_response = query.execute()

    members = []
    for member in members_response.data:
        user_data = member.get("users", {}) if isinstance(member.get("users"), dict) else {}
        members.append({
            "id": member.get("id"),
            "group_id": member.get("group_id"),
            "user_id": member.get("user_id"),
            "is_creator": member.get("is_creator", False),
            "status": member.get("status", "unknown"),
            "joined_at": member.get("joined_at"),
            "user_name": user_data.get("full_name"),
            "user_picture": user_data.get("profile_picture_url"),
        })

    return {"status": "success", "count": len(members), "data": members}


# ---------------------------------------------------------------------------
# Invite
# ---------------------------------------------------------------------------

@router.post("/{group_id}/invite", response_model=dict)
async def invite_to_group(
    group_id: str,
    invite_data: GroupMemberInvite,
    token: str = Depends(require_user_token),
):
    """Invite a user to join the group by email.  Only group members can invite."""
    supabase = get_admin_client()
    inviter_id = resolve_auth_user_to_app_id(supabase, token)

    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = group_response.data

    is_creator = group["creator_user_id"] == inviter_id
    if not is_creator:
        member_response = (
            supabase.table("group_members")
            .select("*")
            .eq("group_id", group_id)
            .eq("user_id", inviter_id)
            .eq("status", "accepted")
            .execute()
        )
        if not member_response.data:
            raise HTTPException(status_code=403, detail="Only group members can invite others")

    invited_user_response = (
        supabase.table("users")
        .select("id, email, full_name")
        .eq("email", invite_data.user_email)
        .execute()
    )
    if not invited_user_response.data:
        raise HTTPException(
            status_code=404, detail=f"User with email {invite_data.user_email} not found"
        )
    invited_user_id = invited_user_response.data[0]["id"]

    existing_member = (
        supabase.table("group_members")
        .select("*")
        .eq("group_id", group_id)
        .eq("user_id", invited_user_id)
        .execute()
    )
    if existing_member.data:
        st = existing_member.data[0]["status"]
        if st == "accepted":
            raise HTTPException(status_code=400, detail="User is already a member of this group")
        if st == "pending":
            raise HTTPException(status_code=400, detail="User already has a pending invitation")
        if st == "rejected":
            supabase.table("group_members").update({"status": "pending"}).eq(
                "id", existing_member.data[0]["id"]
            ).execute()
            return {
                "status": "success",
                "message": "Invitation re-sent successfully",
                "data": {
                    "group_id": group_id,
                    "invited_user_email": invite_data.user_email,
                    "status": "pending",
                },
            }

    supabase.table("group_members").insert(
        {"group_id": group_id, "user_id": invited_user_id, "is_creator": False, "status": "pending"}
    ).execute()

    return {
        "status": "success",
        "message": "Invitation sent successfully",
        "data": {
            "group_id": group_id,
            "invited_user_email": invite_data.user_email,
            "invited_user_name": invited_user_response.data[0].get("full_name"),
            "status": "pending",
        },
    }


# ---------------------------------------------------------------------------
# Request-join / join / reject
# ---------------------------------------------------------------------------

@router.post("/{group_id}/request-join", response_model=dict)
async def request_join_group(group_id: str, token: str = Depends(require_user_token)):
    """Request to join a group (self-invite, creates a pending invitation)."""
    supabase = get_admin_client()
    user_id = resolve_auth_user_to_app_id(supabase, token)

    existing_group_membership = (
        supabase.table("group_members")
        .select("group_id, roommate_groups(group_name, is_solo)")
        .eq("user_id", user_id)
        .eq("status", "accepted")
        .execute()
    )
    if existing_group_membership.data:
        existing = existing_group_membership.data[0]
        group_info = existing.get("roommate_groups", {})
        is_solo = group_info.get("is_solo", False)
        group_name = group_info.get("group_name", "a group")
        if is_solo:
            raise HTTPException(
                status_code=400,
                detail="You are currently in a solo group. Please leave your solo group first before requesting to join another group.",
            )
        raise HTTPException(
            status_code=400,
            detail=f"You are already a member of '{group_name}'. You can only be in one group at a time. Please leave your current group first.",
        )

    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = group_response.data

    existing_member = (
        supabase.table("group_members")
        .select("*")
        .eq("group_id", group_id)
        .eq("user_id", user_id)
        .execute()
    )
    if existing_member.data:
        st = existing_member.data[0]["status"]
        if st == "accepted":
            raise HTTPException(status_code=400, detail="You are already a member of this group")
        if st == "pending":
            raise HTTPException(status_code=400, detail="You already have a pending request to join")
        if st == "rejected":
            supabase.table("group_members").update({"status": "pending"}).eq(
                "id", existing_member.data[0]["id"]
            ).execute()
            return {
                "status": "success",
                "message": "Join request sent successfully",
                "data": {"group_id": group_id, "group_name": group["group_name"], "status": "pending"},
            }

    current_members = (
        supabase.table("group_members")
        .select("user_id")
        .eq("group_id", group_id)
        .eq("status", "accepted")
        .execute()
    )
    target_size = group.get("target_group_size")
    if target_size is not None and len(current_members.data) >= target_size:
        raise HTTPException(status_code=400, detail="Group is already full")

    supabase.table("group_members").insert(
        {"group_id": group_id, "user_id": user_id, "is_creator": False, "status": "pending"}
    ).execute()

    return {
        "status": "success",
        "message": "Join request sent successfully. You can accept it from the Invitations page.",
        "data": {"group_id": group_id, "group_name": group["group_name"], "status": "pending"},
    }


@router.post("/{group_id}/join", response_model=dict)
async def join_group(group_id: str, token: str = Depends(require_user_token)):
    """Accept invitation and join a group."""
    supabase = get_admin_client()
    auth_user = resolve_auth_user(supabase, token)
    user_id = auth_user.id

    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = group_response.data

    member_response = (
        supabase.table("group_members")
        .select("*")
        .eq("group_id", group_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not member_response.data:
        raise HTTPException(status_code=400, detail="You don't have an invitation to this group")
    member = member_response.data[0]
    if member["status"] == "accepted":
        raise HTTPException(status_code=400, detail="You are already a member of this group")
    if member["status"] == "rejected":
        raise HTTPException(status_code=400, detail="You previously rejected this invitation")

    target_size = group.get("target_group_size")
    if target_size is not None:
        current_members = (
            supabase.table("group_members")
            .select("user_id")
            .eq("group_id", group_id)
            .eq("status", "accepted")
            .execute()
        )
        if len(current_members.data) >= target_size:
            raise HTTPException(status_code=400, detail="Group is already full")

    supabase.table("group_members").update({"status": "accepted"}).eq(
        "group_id", group_id
    ).eq("user_id", user_id).execute()

    aggregation_result: dict = {"status": "skipped"}
    try:
        aggregation_result = aggregate_and_persist_group_preferences(group_id)
    except Exception as e:
        aggregation_result = {"status": "error", "message": str(e)}

    matching_result = await maybe_trigger_legacy_stable_matching(
        target_city=group.get("target_city"), reason="group_joined"
    )

    updated_group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    )
    updated_group = updated_group_response.data if updated_group_response.data else group

    return {
        "status": "success",
        "message": "Successfully joined the group",
        "data": {
            "group_id": group_id,
            "group_name": group["group_name"],
            "current_member_count": updated_group.get("current_member_count", 1),
        },
        "preference_aggregation": aggregation_result,
        "matching": matching_result,
    }


@router.post("/{group_id}/reject", response_model=dict)
async def reject_invitation(group_id: str, token: str = Depends(require_user_token)):
    """Reject a group invitation."""
    supabase = get_admin_client()
    user_id = resolve_auth_user_to_app_id(supabase, token)

    member_response = (
        supabase.table("group_members")
        .select("*")
        .eq("group_id", group_id)
        .eq("user_id", user_id)
        .eq("status", "pending")
        .execute()
    )
    if not member_response.data:
        raise HTTPException(status_code=400, detail="No pending invitation found")

    supabase.table("group_members").update({"status": "rejected"}).eq(
        "group_id", group_id
    ).eq("user_id", user_id).execute()

    return {"status": "success", "message": "Invitation rejected"}


# ---------------------------------------------------------------------------
# Creator accept/reject join requests
# ---------------------------------------------------------------------------

@router.post("/{group_id}/accept-request/{user_id}", response_model=dict)
async def accept_join_request(
    group_id: str, user_id: str, token: str = Depends(require_user_token)
):
    """Accept a user's request to join the group (creator only)."""
    supabase = get_admin_client()
    current_user_id = resolve_auth_user_to_app_id(supabase, token)

    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = group_response.data
    if group["creator_user_id"] != current_user_id:
        raise HTTPException(status_code=403, detail="Only the group creator can accept join requests")

    member_response = (
        supabase.table("group_members")
        .select("*")
        .eq("group_id", group_id)
        .eq("user_id", user_id)
        .eq("status", "pending")
        .execute()
    )
    if not member_response.data:
        raise HTTPException(status_code=400, detail="No pending join request found for this user")

    target_size = group.get("target_group_size")
    if target_size is not None:
        current_members = (
            supabase.table("group_members")
            .select("user_id")
            .eq("group_id", group_id)
            .eq("status", "accepted")
            .execute()
        )
        if len(current_members.data) >= target_size:
            raise HTTPException(status_code=400, detail="Group is already full")

    supabase.table("group_members").update({"status": "accepted"}).eq(
        "group_id", group_id
    ).eq("user_id", user_id).execute()

    supabase.table("group_members").delete().eq("user_id", user_id).eq(
        "status", "pending"
    ).neq("group_id", group_id).execute()

    user_info_response = (
        supabase.table("users").select("email, full_name").eq("id", user_id).single().execute()
    )
    user_info = user_info_response.data if user_info_response.data else {}

    matching_result = await maybe_trigger_legacy_stable_matching(
        target_city=group.get("target_city"), reason="join_request_accepted"
    )

    return {
        "status": "success",
        "message": f"Join request accepted. {user_info.get('full_name', 'User')} is now a member.",
        "data": {
            "group_id": group_id,
            "user_id": user_id,
            "user_name": user_info.get("full_name"),
            "status": "accepted",
        },
        "matching": matching_result,
    }


@router.post("/{group_id}/reject-request/{user_id}", response_model=dict)
async def reject_join_request(
    group_id: str, user_id: str, token: str = Depends(require_user_token)
):
    """Reject a user's request to join the group (creator only)."""
    supabase = get_admin_client()
    current_user_id = resolve_auth_user_to_app_id(supabase, token)

    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = group_response.data
    if group["creator_user_id"] != current_user_id:
        raise HTTPException(status_code=403, detail="Only the group creator can reject join requests")

    member_response = (
        supabase.table("group_members")
        .select("*")
        .eq("group_id", group_id)
        .eq("user_id", user_id)
        .eq("status", "pending")
        .execute()
    )
    if not member_response.data:
        raise HTTPException(status_code=400, detail="No pending join request found for this user")

    user_info_response = (
        supabase.table("users").select("email, full_name").eq("id", user_id).single().execute()
    )
    user_info = user_info_response.data if user_info_response.data else {}

    supabase.table("group_members").update({"status": "rejected"}).eq(
        "group_id", group_id
    ).eq("user_id", user_id).execute()

    return {
        "status": "success",
        "message": f"Join request from {user_info.get('full_name', 'user')} has been rejected.",
        "data": {
            "group_id": group_id,
            "user_id": user_id,
            "user_name": user_info.get("full_name"),
            "status": "rejected",
        },
    }


# ---------------------------------------------------------------------------
# Leave / Remove
# ---------------------------------------------------------------------------

@router.delete("/{group_id}/leave", response_model=dict)
async def leave_group(group_id: str, token: str = Depends(require_user_token)):
    """Leave a group.  If creator leaves, ownership transfers or group is deleted."""
    supabase = get_admin_client()
    user_id = resolve_auth_user_to_app_id(supabase, token)

    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = group_response.data

    member_response = (
        supabase.table("group_members")
        .select("*")
        .eq("group_id", group_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not member_response.data:
        raise HTTPException(status_code=400, detail="You are not a member of this group")
    member = member_response.data[0]

    if member["is_creator"]:
        other_members_response = (
            supabase.table("group_members")
            .select("user_id")
            .eq("group_id", group_id)
            .eq("status", "accepted")
            .neq("user_id", user_id)
            .execute()
        )
        other_members = other_members_response.data or []

        if not other_members:
            supabase.table("group_members").delete().eq("group_id", group_id).execute()
            supabase.table("roommate_groups").delete().eq("id", group_id).execute()
            return {
                "status": "success",
                "message": "Successfully left the group. The group was deleted as you were the only member.",
                "data": {"group_id": group_id, "group_name": group["group_name"], "group_deleted": True},
            }

        new_creator = random.choice(other_members)
        new_creator_id = new_creator["user_id"]
        supabase.table("group_members").update({"is_creator": True}).eq(
            "group_id", group_id
        ).eq("user_id", new_creator_id).execute()
        supabase.table("roommate_groups").update({"creator_user_id": new_creator_id}).eq(
            "id", group_id
        ).execute()
        supabase.table("group_members").delete().eq("group_id", group_id).eq(
            "user_id", user_id
        ).execute()

        new_creator_user = (
            supabase.table("users")
            .select("full_name, email")
            .eq("id", new_creator_id)
            .single()
            .execute()
        )
        new_creator_name = (
            (new_creator_user.data.get("full_name") or new_creator_user.data.get("email"))
            if new_creator_user.data
            else "another member"
        )
        return {
            "status": "success",
            "message": f"Successfully left the group. Ownership transferred to {new_creator_name}.",
            "data": {
                "group_id": group_id,
                "group_name": group["group_name"],
                "ownership_transferred": True,
                "new_creator_id": new_creator_id,
            },
        }

    supabase.table("group_members").delete().eq("group_id", group_id).eq(
        "user_id", user_id
    ).execute()

    aggregation_result: dict = {"status": "skipped"}
    try:
        aggregation_result = aggregate_and_persist_group_preferences(group_id)
    except Exception as e:
        aggregation_result = {"status": "error", "message": str(e)}

    matching_result = await maybe_trigger_legacy_stable_matching(
        target_city=group.get("target_city"), reason="member_left"
    )

    return {
        "status": "success",
        "message": "Successfully left the group",
        "data": {"group_id": group_id, "group_name": group["group_name"]},
        "aggregation": aggregation_result,
        "matching": matching_result,
    }


@router.delete("/{group_id}/members/{member_user_id}", response_model=dict)
async def remove_member(
    group_id: str, member_user_id: str, token: str = Depends(require_user_token)
):
    """Remove a member from the group (creator only)."""
    supabase = get_admin_client()
    current_user_id = resolve_auth_user_to_app_id(supabase, token)

    group_response = (
        supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    )
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    group = group_response.data
    if group["creator_user_id"] != current_user_id:
        raise HTTPException(status_code=403, detail="Only the group creator can remove members")

    member_response = (
        supabase.table("group_members")
        .select("*")
        .eq("group_id", group_id)
        .eq("user_id", member_user_id)
        .execute()
    )
    if not member_response.data:
        raise HTTPException(status_code=400, detail="User is not a member of this group")
    if member_response.data[0]["is_creator"]:
        raise HTTPException(status_code=400, detail="Cannot remove the group creator")

    supabase.table("group_members").delete().eq("group_id", group_id).eq(
        "user_id", member_user_id
    ).execute()

    aggregation_result: dict = {"status": "skipped"}
    try:
        aggregation_result = aggregate_and_persist_group_preferences(group_id)
    except Exception as e:
        aggregation_result = {"status": "error", "message": str(e)}

    matching_result = await maybe_trigger_legacy_stable_matching(
        target_city=group.get("target_city"), reason="member_removed"
    )

    return {
        "status": "success",
        "message": "Member removed successfully",
        "aggregation": aggregation_result,
        "matching": matching_result,
    }
