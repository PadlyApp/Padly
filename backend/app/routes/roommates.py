"""
Roommate Post routes
CRUD operations for roommate posts and groups
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from app.dependencies.auth import get_user_token, require_user_token
from app.services.supabase_client import SupabaseHTTPClient
from app.models import (
    RoommatePostCreate, 
    RoommatePostUpdate,
    RoommateGroupCreate,
    RoommateGroupUpdate,
    GroupMemberCreate
)

router = APIRouter(prefix="/api", tags=["roommates"])


@router.get("/roommate-posts")
async def list_roommate_posts(
    token: Optional[str] = Depends(get_user_token),
    status: Optional[str] = None,
    city: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
):
    """
    List all roommate posts with optional filters.
    
    Query params:
    - status: Filter by post status (active, inactive, matched)
    - city: Filter by target city
    - limit: Max results (default: 100)
    - offset: Pagination offset
    """
    client = SupabaseHTTPClient(token=token)
    
    filters = {}
    if status:
        filters["status"] = f"eq.{status}"
    if city:
        filters["target_city"] = f"ilike.*{city}*"
    
    posts = await client.select(
        table="roommate_posts",
        filters=filters,
        limit=limit,
        offset=offset,
        order="created_at.desc"
    )
    
    return {
        "status": "success",
        "count": len(posts),
        "data": posts
    }


@router.get("/roommate-posts/{post_id}")
async def get_roommate_post(
    post_id: str,
    token: Optional[str] = Depends(get_user_token)
):
    """Get a single roommate post by ID"""
    client = SupabaseHTTPClient(token=token)
    
    post = await client.select_one(
        table="roommate_posts",
        id_value=post_id
    )
    
    if not post:
        raise HTTPException(status_code=404, detail="Roommate post not found")
    
    return {
        "status": "success",
        "data": post
    }


@router.post("/roommate-posts")
async def create_roommate_post(
    post_data: RoommatePostCreate,
    token: str = Depends(require_user_token)
):
    """
    Create a new roommate post.
    Requires authentication.
    """
    client = SupabaseHTTPClient(token=token)
    
    data = post_data.model_dump(exclude_none=True)
    
    post = await client.insert(
        table="roommate_posts",
        data=data
    )
    
    return {
        "status": "success",
        "message": "Roommate post created successfully",
        "data": post
    }


@router.put("/roommate-posts/{post_id}")
async def update_roommate_post(
    post_id: str,
    post_data: RoommatePostUpdate,
    token: str = Depends(require_user_token)
):
    """
    Update a roommate post.
    Requires authentication.
    With RLS: User can only update their own posts
    """
    client = SupabaseHTTPClient(token=token)
    
    data = post_data.model_dump(exclude_none=True)
    
    if not data:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    post = await client.update(
        table="roommate_posts",
        id_value=post_id,
        data=data
    )
    
    return {
        "status": "success",
        "message": "Roommate post updated successfully",
        "data": post
    }


@router.delete("/roommate-posts/{post_id}")
async def delete_roommate_post(
    post_id: str,
    token: str = Depends(require_user_token)
):
    """
    Delete a roommate post.
    Requires authentication.
    With RLS: User can only delete their own posts
    """
    client = SupabaseHTTPClient(token=token)
    
    await client.delete(
        table="roommate_posts",
        id_value=post_id
    )
    
    return {
        "status": "success",
        "message": "Roommate post deleted successfully"
    }


# ============================================================================
# ROOMMATE GROUPS ENDPOINTS
# ============================================================================

@router.get("/roommate-groups")
async def list_roommate_groups(
    token: Optional[str] = Depends(get_user_token),
    status: Optional[str] = None,
    city: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
):
    """
    List all roommate groups with optional filters.
    
    Query params:
    - status: Filter by group status (active, inactive, matched)
    - city: Filter by target city
    - limit: Max results (default: 100)
    - offset: Pagination offset
    """
    client = SupabaseHTTPClient(token=token)
    
    filters = {}
    if status:
        filters["status"] = f"eq.{status}"
    if city:
        filters["target_city"] = f"ilike.*{city}*"
    
    groups = await client.select(
        table="roommate_groups",
        filters=filters,
        limit=limit,
        offset=offset,
        order="created_at.desc"
    )
    
    return {
        "status": "success",
        "count": len(groups),
        "data": groups
    }


@router.get("/roommate-groups/{group_id}")
async def get_roommate_group(
    group_id: str,
    token: Optional[str] = Depends(get_user_token)
):
    """Get a single roommate group by ID"""
    client = SupabaseHTTPClient(token=token)
    
    group = await client.select_one(
        table="roommate_groups",
        id_value=group_id
    )
    
    if not group:
        raise HTTPException(status_code=404, detail="Roommate group not found")
    
    return {
        "status": "success",
        "data": group
    }


@router.post("/roommate-groups")
async def create_roommate_group(
    group_data: RoommateGroupCreate,
    token: str = Depends(require_user_token)
):
    """
    Create a new roommate group.
    Requires authentication.
    """
    client = SupabaseHTTPClient(token=token)
    
    data = group_data.model_dump(exclude_none=True)
    
    group = await client.insert(
        table="roommate_groups",
        data=data
    )
    
    return {
        "status": "success",
        "message": "Roommate group created successfully",
        "data": group
    }


@router.put("/roommate-groups/{group_id}")
async def update_roommate_group(
    group_id: str,
    group_data: RoommateGroupUpdate,
    token: str = Depends(require_user_token)
):
    """
    Update a roommate group.
    Requires authentication.
    With RLS: User can only update groups they created
    """
    client = SupabaseHTTPClient(token=token)
    
    data = group_data.model_dump(exclude_none=True)
    
    if not data:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    group = await client.update(
        table="roommate_groups",
        id_value=group_id,
        data=data
    )
    
    return {
        "status": "success",
        "message": "Roommate group updated successfully",
        "data": group
    }


@router.delete("/roommate-groups/{group_id}")
async def delete_roommate_group(
    group_id: str,
    token: str = Depends(require_user_token)
):
    """
    Delete a roommate group.
    Requires authentication.
    With RLS: User can only delete groups they created
    """
    client = SupabaseHTTPClient(token=token)
    
    await client.delete(
        table="roommate_groups",
        id_value=group_id
    )
    
    return {
        "status": "success",
        "message": "Roommate group deleted successfully"
    }


# ============================================================================
# GROUP MEMBERS ENDPOINTS
# ============================================================================

@router.get("/roommate-groups/{group_id}/members")
async def list_group_members(
    group_id: str,
    token: Optional[str] = Depends(get_user_token)
):
    """
    List all members of a specific roommate group.
    """
    client = SupabaseHTTPClient(token=token)
    
    members = await client.select(
        table="group_members",
        filters={"group_id": f"eq.{group_id}"},
        order="joined_at.asc"
    )
    
    return {
        "status": "success",
        "count": len(members),
        "data": members
    }


@router.post("/roommate-groups/{group_id}/members")
async def add_group_member(
    group_id: str,
    member_data: GroupMemberCreate,
    token: str = Depends(require_user_token)
):
    """
    Add a member to a roommate group.
    Requires authentication.
    """
    client = SupabaseHTTPClient(token=token)
    
    # Ensure the group_id in the URL matches the one in the payload
    data = member_data.model_dump(exclude_none=True)
    if data.get("group_id") != group_id:
        raise HTTPException(
            status_code=400, 
            detail="Group ID in URL must match group ID in payload"
        )
    
    member = await client.insert(
        table="group_members",
        data=data
    )
    
    return {
        "status": "success",
        "message": "Member added to group successfully",
        "data": member
    }


@router.delete("/roommate-groups/{group_id}/members/{user_id}")
async def remove_group_member(
    group_id: str,
    user_id: str,
    token: str = Depends(require_user_token)
):
    """
    Remove a member from a roommate group.
    Requires authentication.
    With RLS: Only group creator or the member themselves can remove
    """
    client = SupabaseHTTPClient(token=token)
    
    # Delete by composite key (group_id, user_id)
    # Note: Supabase client might need special handling for composite keys
    await client.delete(
        table="group_members",
        filters={
            "group_id": f"eq.{group_id}",
            "user_id": f"eq.{user_id}"
        }
    )
    
    return {
        "status": "success",
        "message": "Member removed from group successfully"
    }

