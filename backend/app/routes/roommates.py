"""
Roommate Post routes
CRUD operations for roommate posts and groups
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from app.dependencies.auth import get_user_token, require_user_token
from app.services.supabase_client import SupabaseHTTPClient
from app.models import RoommatePostCreate, RoommatePostUpdate

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

