"""
User routes
CRUD operations for users table
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from app.dependencies.auth import get_user_token, require_user_token
from app.services.supabase_client import SupabaseHTTPClient
from app.models import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/users")
async def list_users(
    token: Optional[str] = Depends(get_user_token),
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
):
    """
    List all users.
    
    - With JWT: Returns users visible to authenticated user (RLS when enabled)
    - Without JWT: Returns publicly visible users (RLS when enabled)
    - RLS disabled: Returns all users
    """
    client = SupabaseHTTPClient(token=token)
    
    users = await client.select(
        table="users",
        limit=limit,
        offset=offset,
        order="created_at.desc"
    )
    
    return {
        "status": "success",
        "count": len(users),
        "data": users
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    token: Optional[str] = Depends(get_user_token)
):
    """
    Get a single user by ID.
    
    - With JWT: User must have permission to view (RLS when enabled)
    - Without JWT: User must be publicly visible (RLS when enabled)
    """
    client = SupabaseHTTPClient(token=token)
    
    user = await client.select_one(
        table="users",
        id_value=user_id
    )
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "status": "success",
        "data": user
    }


@router.post("/users")
async def create_user(
    user_data: UserCreate,
    token: Optional[str] = Depends(get_user_token)
):
    """
    Create a new user.
    
    - With JWT: User can create records they own (RLS when enabled)
    - Without JWT: Can create public records only (RLS when enabled)
    """
    client = SupabaseHTTPClient(token=token)
    
    # Convert Pydantic model to dict, excluding None values
    data = user_data.model_dump(exclude_none=True)
    
    user = await client.insert(
        table="users",
        data=data
    )
    
    return {
        "status": "success",
        "message": "User created successfully",
        "data": user
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    token: str = Depends(require_user_token)
):
    """
    Update a user.
    
    Requires authentication.
    - With RLS enabled: User can only update their own record
    - With RLS disabled: User can update any record (for testing)
    """
    client = SupabaseHTTPClient(token=token)
    
    # Convert Pydantic model to dict, excluding None values
    data = user_data.model_dump(exclude_none=True)
    
    if not data:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    user = await client.update(
        table="users",
        id_value=user_id,
        data=data
    )
    
    return {
        "status": "success",
        "message": "User updated successfully",
        "data": user
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    token: str = Depends(require_user_token)
):
    """
    Delete a user.
    
    Requires authentication.
    - With RLS enabled: User can only delete their own record
    - With RLS disabled: User can delete any record (for testing)
    """
    client = SupabaseHTTPClient(token=token)
    
    await client.delete(
        table="users",
        id_value=user_id
    )
    
    return {
        "status": "success",
        "message": "User deleted successfully"
    }
