"""
User routes
CRUD operations for users table
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from app.dependencies.auth import get_user_token, require_user_token
from app.services.supabase_client import SupabaseHTTPClient
from app.models import UserCreate, UserUpdate, UserResponse
from app.services.controlled_vocab import (
    validate_company,
    validate_school,
    validate_role_title,
)

router = APIRouter(prefix="/api", tags=["users"])


def _validate_profile_catalog_fields(data: dict) -> dict:
    """
    Enforce controlled options for profile catalog fields.
    """
    if "company_name" in data:
        data["company_name"] = validate_company(data.get("company_name"))
    if "school_name" in data:
        data["school_name"] = validate_school(data.get("school_name"))
    if "role_title" in data:
        data["role_title"] = validate_role_title(data.get("role_title"))
    return data


@router.get("/users")
async def list_users(
    token: Optional[str] = Depends(get_user_token),
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    q: Optional[str] = Query(None, description="Case-insensitive search over full_name and email"),
):
    """
    List all users.
    
    - With JWT: Returns users visible to authenticated user (RLS when enabled)
    - Without JWT: Returns publicly visible users (RLS when enabled)
    - RLS disabled: Returns all users
    """
    client = SupabaseHTTPClient(token=token)
    filters = {}

    q_norm = (q or "").strip()
    if q_norm:
        filters["or"] = f"(full_name.ilike.*{q_norm}*,email.ilike.*{q_norm}*)"

    # Exclude the caller from results when authenticated.
    if token:
        try:
            from app.dependencies.supabase import get_admin_client

            admin_client = get_admin_client()
            user_response = admin_client.auth.get_user(token)
            auth_user_id = user_response.user.id if user_response and user_response.user else None
            if auth_user_id:
                me = (
                    admin_client.table("users")
                    .select("id")
                    .eq("auth_id", auth_user_id)
                    .limit(1)
                    .execute()
                )
                if me.data:
                    filters["id"] = f"neq.{me.data[0]['id']}"
        except Exception:
            # Best-effort only; if this lookup fails, still return searchable users.
            pass

    users = await client.select(
        table="users",
        filters=filters or None,
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
    try:
        data = _validate_profile_catalog_fields(data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    
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
    Verifies the user is updating their own profile before allowing the update.
    user_id can be either the users table 'id' or the 'auth_id'.
    """
    from app.dependencies.supabase import get_admin_client
    
    # First verify the token and get the auth user
    admin_client = get_admin_client()
    user_response = admin_client.auth.get_user(token)
    
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Try to find user by id first, then by auth_id
    user_record = admin_client.table('users').select('id, auth_id').eq('id', user_id).execute()
    
    if not user_record.data:
        # Try finding by auth_id
        user_record = admin_client.table('users').select('id, auth_id').eq('auth_id', user_id).execute()
    
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    actual_user_id = user_record.data[0]['id']
    record_auth_id = user_record.data[0].get('auth_id')
    
    # Verify the authenticated user owns this profile
    if record_auth_id != auth_user_id:
        raise HTTPException(status_code=403, detail="You can only update your own profile")
    
    # Convert Pydantic model to dict, excluding None values
    data = user_data.model_dump(exclude_none=True)
    
    if not data:
        raise HTTPException(status_code=400, detail="No data provided for update")

    try:
        data = _validate_profile_catalog_fields(data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Use admin client to bypass RLS for the update
    update_response = admin_client.table('users').update(data).eq('id', actual_user_id).execute()
    
    return {
        "status": "success",
        "message": "User updated successfully",
        "data": update_response.data[0] if update_response.data else None
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
