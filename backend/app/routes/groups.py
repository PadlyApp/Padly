"""
Roommate Groups API Routes
CRUD operations for roommate groups and member management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from app.dependencies.auth import get_user_token, require_user_token
from app.dependencies.supabase import get_admin_client
from app.models import RoommateGroupCreate, RoommateGroupUpdate, RoommateGroupResponse
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/roommate-groups", tags=["Roommate Groups"])


# =============================================================================
# Pydantic Models for Requests/Responses
# =============================================================================

class GroupMemberInvite(BaseModel):
    """Model for inviting a user to a group"""
    user_email: str
    message: Optional[str] = None


class GroupMemberResponse(BaseModel):
    """Model for group member response"""
    id: str
    group_id: str
    user_id: str
    is_creator: bool
    status: str
    joined_at: datetime
    # User details (joined from users table)
    user_email: Optional[str] = None
    user_name: Optional[str] = None


class GroupWithMembers(BaseModel):
    """Model for group with member details"""
    id: str
    creator_user_id: str
    group_name: str
    description: Optional[str]
    target_city: str
    budget_per_person_min: Optional[float]
    budget_per_person_max: Optional[float]
    target_move_in_date: Optional[str]
    target_group_size: int
    status: str
    created_at: datetime
    updated_at: datetime
    members: List[GroupMemberResponse]
    member_count: int


# =============================================================================
# Group CRUD Endpoints
# =============================================================================

@router.get("", response_model=dict)
async def list_groups(
    token: Optional[str] = Depends(get_user_token),
    status: Optional[str] = Query(None, description="Filter by status (active, inactive, matched)"),
    city: Optional[str] = Query(None, description="Filter by target city"),
    my_groups: bool = Query(False, description="Only show groups I'm a member of"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    List roommate groups with optional filters.
    
    Query params:
    - status: Filter by group status
    - city: Filter by target city
    - my_groups: Only show groups the current user is a member of
    - limit: Max results (default: 100)
    - offset: Pagination offset
    """
    supabase = get_admin_client()
    
    # Build query
    query = supabase.table('roommate_groups').select('*')
    
    # Apply filters
    if status:
        query = query.eq('status', status)
    if city:
        query = query.ilike('target_city', f'%{city}%')
    
    # Order and paginate
    query = query.order('created_at', desc=True).range(offset, offset + limit - 1)
    
    response = query.execute()
    groups = response.data
    
    # If my_groups is requested, filter by membership
    if my_groups and token:
        # Get current user from token
        user_response = supabase.auth.get_user(token)
        if user_response:
            auth_user_id = user_response.user.id
            
            # Look up the user in the users table by auth_id
            user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
            
            if user_record.data:
                user_id = user_record.data[0]['id']
                
                # Get groups where user is an ACCEPTED member (not pending or rejected)
                member_response = supabase.table('group_members')\
                    .select('group_id')\
                    .eq('user_id', user_id)\
                    .eq('status', 'accepted')\
                    .execute()
                
                member_group_ids = [m['group_id'] for m in member_response.data]
                groups = [g for g in groups if g['id'] in member_group_ids]
            else:
                # User not found in users table, return empty
                groups = []
    
    # Calculate actual accepted member count for each group
    if groups:
        group_ids = [g['id'] for g in groups]
        
        # Get all accepted members for these groups
        members_response = supabase.table('group_members')\
            .select('group_id')\
            .in_('group_id', group_ids)\
            .eq('status', 'accepted')\
            .execute()
        
        # Count members per group
        member_counts = {}
        for member in members_response.data:
            gid = member['group_id']
            member_counts[gid] = member_counts.get(gid, 0) + 1
        
        # Update each group with the accurate count
        for group in groups:
            group['current_member_count'] = member_counts.get(group['id'], 0)
    
    return {
        "status": "success",
        "count": len(groups),
        "data": groups
    }

# =============================================================================
# User's Pending Join Requests
# =============================================================================

@router.get("/my-pending-requests", response_model=dict)
async def get_my_pending_requests(token: str = Depends(require_user_token)):
    """
    Get all pending join requests for the current user.
    
    Returns list of groups where the user has a pending join request.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    user_id = user_record.data[0]['id']
    
    # Get all pending memberships for this user
    pending_response = supabase.table('group_members')\
        .select('group_id, joined_at, roommate_groups(id, group_name, target_city, status)')\
        .eq('user_id', user_id)\
        .eq('status', 'pending')\
        .execute()
    
    pending_requests = []
    for membership in pending_response.data:
        group_data = membership.get('roommate_groups', {}) if membership.get('roommate_groups') else {}
        pending_requests.append({
            'group_id': membership['group_id'],
            'group_name': group_data.get('group_name'),
            'target_city': group_data.get('target_city'),
            'group_status': group_data.get('status'),
            'requested_at': membership.get('joined_at')
        })
    
    return {
        "status": "success",
        "count": len(pending_requests),
        "data": pending_requests
    }


# Group Discovery & User-to-Group Matching
# =============================================================================

@router.get("/discover", response_model=dict)
async def discover_groups(
    city: str = Query(..., description="Target city"),
    budget_min: Optional[float] = Query(None, description="Minimum budget per person"),
    budget_max: Optional[float] = Query(None, description="Maximum budget per person"),
    move_in_date: Optional[str] = Query(None, description="Target move-in date (ISO format)"),
    min_compatibility_score: int = Query(50, ge=0, le=100, description="Minimum compatibility score"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    token: str = Depends(require_user_token)
):
    """
    Discover compatible roommate groups based on user preferences.
    
    Returns groups ranked by compatibility score with detailed reasons.
    """
    from app.services.user_group_matching import find_compatible_groups
    
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    user_id = user_response.user.id
    
    # Get user from database
    user_db_response = supabase.table("users").select("*").eq("id", user_id).single().execute()
    
    if not user_db_response.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    user = user_db_response.data
    
    # Get or build user preferences
    prefs_response = supabase.table("personal_preferences").select("*").eq("user_id", user_id).execute()
    
    if prefs_response.data:
        user_prefs = prefs_response.data[0]
    else:
        # Use query parameters as preferences if no stored preferences
        user_prefs = {"target_city": city, "budget_min": budget_min, "budget_max": budget_max, "move_in_date": move_in_date}
    
    # Override with query params if provided
    if budget_min is not None:
        user_prefs["budget_min"] = budget_min
    if budget_max is not None:
        user_prefs["budget_max"] = budget_max
    if move_in_date is not None:
        user_prefs["move_in_date"] = move_in_date
    
    # Ensure city is set
    if not user_prefs.get("target_city"):
        user_prefs["target_city"] = city
    
    # Find compatible groups
    compatible_groups = await find_compatible_groups(user_id=user_id, user_prefs=user_prefs, min_score=min_compatibility_score, limit=limit)
    
    # Format response
    formatted_groups = []
    for group in compatible_groups:
        # Get member details
        members_response = supabase.table("group_members").select("*, users(id, full_name, company_name, school_name, verification_status)").eq("group_id", group["id"]).eq("status", "accepted").execute()
        
        members = []
        for member_data in members_response.data:
            user_data = member_data.get("users", {}) if isinstance(member_data.get("users"), dict) else {}
            members.append({"id": user_data.get("id"), "full_name": user_data.get("full_name"), "company_name": user_data.get("company_name"), "school_name": user_data.get("school_name"), "verification_status": user_data.get("verification_status"), "is_creator": member_data.get("is_creator", False)})
        
        # Calculate open spots
        current_count = group.get("current_member_count", len(members))
        target_size = group.get("target_group_size")
        open_spots = (target_size - current_count) if target_size else None
        
        formatted_groups.append({"id": group["id"], "group_name": group["group_name"], "description": group.get("description"), "target_city": group["target_city"], "budget_per_person_min": group.get("budget_per_person_min"), "budget_per_person_max": group.get("budget_per_person_max"), "target_move_in_date": str(group["target_move_in_date"]) if group.get("target_move_in_date") else None, "target_group_size": target_size, "current_member_count": current_count, "open_spots": open_spots, "members": members, "compatibility": group["compatibility"], "created_at": str(group["created_at"]) if group.get("created_at") else None})
    
    return {"status": "success", "count": len(formatted_groups), "groups": formatted_groups}


@router.get("/{group_id}/pending-requests", response_model=dict)
async def get_pending_requests(group_id: str, token: str = Depends(require_user_token)):
    """Get pending join requests for a group (creator only).
    
    Returns list of users who requested to join with compatibility scores.
    """
    from app.services.user_group_matching import calculate_user_group_compatibility
    
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    current_user_id = user_record.data[0]['id']
    
    # Verify user is group creator
    group_response = supabase.table("roommate_groups").select("*").eq("id", group_id).single().execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    if group["creator_user_id"] != current_user_id:
        raise HTTPException(status_code=403, detail="Only group creator can view pending requests")
    
    # Get pending members
    pending_response = supabase.table("group_members").select("*, users(id, email, full_name, company_name, school_name, verification_status, profile_picture_url)").eq("group_id", group_id).eq("status", "pending").execute()
    
    # Calculate compatibility for each pending user
    requests = []
    for member_data in pending_response.data:
        user_data = member_data.get("users", {}) if isinstance(member_data.get("users"), dict) else {}
        user_id = user_data.get("id")
        
        if not user_id:
            continue
        
        # Get user preferences
        prefs_response = supabase.table("personal_preferences").select("*").eq("user_id", user_id).execute()
        
        user_prefs = prefs_response.data[0] if prefs_response.data else {}
        
        # Calculate compatibility
        compatibility = calculate_user_group_compatibility(user_data, user_prefs, group)
        
        requests.append({"user_id": user_id, "full_name": user_data.get("full_name"), "email": user_data.get("email"), "company_name": user_data.get("company_name"), "school_name": user_data.get("school_name"), "verification_status": user_data.get("verification_status"), "profile_picture_url": user_data.get("profile_picture_url"), "requested_at": str(member_data.get("joined_at")) if member_data.get("joined_at") else None, "user_preferences": {"budget_min": user_prefs.get("budget_min"), "budget_max": user_prefs.get("budget_max"), "target_city": user_prefs.get("target_city"), "move_in_date": str(user_prefs.get("move_in_date")) if user_prefs.get("move_in_date") else None, "lifestyle_preferences": user_prefs.get("lifestyle_preferences", {})}, "compatibility": compatibility})
    
    # Sort by compatibility score (highest first)
    requests.sort(key=lambda r: r["compatibility"]["score"], reverse=True)
    
    return {"status": "success", "count": len(requests), "requests": requests}



@router.get("/{group_id}", response_model=dict)
async def get_group(
    group_id: str,
    token: Optional[str] = Depends(get_user_token),
    include_members: bool = Query(True, description="Include member details")
):
    """
    Get a single roommate group by ID.
    Optionally includes member details.
    """
    supabase = get_admin_client()
    
    # Get group
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    # Include members if requested
    if include_members:
        members_response = supabase.table('group_members')\
            .select('*, users(id, email, full_name)')\
            .eq('group_id', group_id)\
            .execute()
        
        # Format member data
        members = []
        for member in members_response.data:
            user_data = member.get('users', {}) if isinstance(member.get('users'), dict) else {}
            members.append({
                'id': member.get('id'),
                'group_id': member.get('group_id'),
                'user_id': member.get('user_id'),
                'is_creator': member.get('is_creator', False),
                'status': member.get('status', 'unknown'),
                'joined_at': member.get('joined_at'),
                'user_email': user_data.get('email'),
                'user_name': user_data.get('full_name')
            })
        
        group['members'] = members
        group['member_count'] = len([m for m in members if m.get('status') == 'accepted'])
    
    return {
        "status": "success",
        "data": group
    }


@router.post("", response_model=dict)
async def create_group(
    group_data: RoommateGroupCreate,
    token: str = Depends(require_user_token)
):
    """
    Create a new roommate group.
    Requires authentication.
    Creates the group and adds the creator as the first member.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found. Please complete your profile first.")
    
    user_id = user_record.data[0]['id']
    
    # Create group
    group_dict = group_data.model_dump(exclude_none=True)
    group_dict['creator_user_id'] = user_id
    
    # Convert non-JSON-serializable types
    from decimal import Decimal
    from datetime import date as date_type, datetime as datetime_type
    for key, value in group_dict.items():
        if isinstance(value, Decimal):
            group_dict[key] = float(value)
        elif isinstance(value, date_type) and not isinstance(value, datetime_type):
            group_dict[key] = value.isoformat()  # Convert date to "YYYY-MM-DD" string

    group_response = supabase.table('roommate_groups')\
        .insert(group_dict)\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=500, detail="Failed to create group")
    
    created_group = group_response.data[0]
    group_id = created_group['id']
    
    # Add creator as first member
    member_data = {
        'group_id': group_id,
        'user_id': user_id,
        'is_creator': True,
        'status': 'accepted'
    }
    
    supabase.table('group_members').insert(member_data).execute()
    
    # 🔥 TRIGGER STABLE MATCHING for the new group's city
    # Option 3: Hybrid re-matching - preserves confirmed matches
    target_city = created_group.get('target_city')
    matching_result = {'status': 'skipped', 'message': 'No city specified'}
    
    if target_city:
        from app.routes.stable_matching import run_matching, RunMatchingRequest
        
        try:
            matching_request = RunMatchingRequest(city=target_city, date_flexibility_days=30)
            matching_response = await run_matching(matching_request)
            matching_result = {
                "status": "success",
                "city": target_city,
                "total_matches": len(matching_response.matches),
                "message": matching_response.message
            }
        except Exception as e:
            # Don't fail group creation if matching fails
            matching_result = {"status": "error", "message": str(e)}
    
    return {
        "status": "success",
        "message": "Group created successfully",
        "data": created_group,
        "matching": matching_result
    }


@router.put("/{group_id}", response_model=dict)
async def update_group(
    group_id: str,
    group_data: RoommateGroupUpdate,
    token: str = Depends(require_user_token)
):
    """
    Update a roommate group.
    Requires authentication.
    Only the creator can update the group.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    user_id = user_record.data[0]['id']
    
    # Check if user is creator (only creator can update)
    member_response = supabase.table('group_members')\
        .select('is_creator')\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .eq('status', 'accepted')\
        .execute()
    
    if not member_response.data:
        raise HTTPException(status_code=403, detail="You are not a member of this group")
    
    if not member_response.data[0].get('is_creator'):
        raise HTTPException(status_code=403, detail="Only the group creator can edit the group")
    
    # Get the group
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    # Update group
    update_dict = group_data.model_dump(exclude_none=True)
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    updated_response = supabase.table('roommate_groups')\
        .update(update_dict)\
        .eq('id', group_id)\
        .execute()
    
    # TRIGGER STABLE MATCHING if preference fields changed
    preference_fields = [
        'budget_per_person_min', 'budget_per_person_max', 
        'target_move_in_date', 'target_city'
    ]
    
    matching_result = {'status': 'skipped', 'message': 'No preference changes detected'}
    
    if any(field in update_dict for field in preference_fields):
        from app.routes.stable_matching import run_matching, RunMatchingRequest
        
        target_city = group.get('target_city')
        if target_city:
            try:
                matching_request = RunMatchingRequest(city=target_city, date_flexibility_days=30)
                matching_response = await run_matching(matching_request)
                matching_result = {
                    "status": "success",
                    "city": target_city,
                    "total_matches": len(matching_response.matches),
                    "message": matching_response.message
                }
            except Exception as e:
                matching_result = {"status": "error", "message": str(e)}
    
    return {
        "status": "success",
        "message": "Group updated successfully",
        "data": updated_response.data[0] if updated_response.data else None,
        "matching": matching_result
    }


@router.delete("/{group_id}", response_model=dict)
async def delete_group(
    group_id: str,
    token: str = Depends(require_user_token)
):
    """
    Delete a roommate group.
    Requires authentication.
    Only the creator can delete the group.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    user_id = user_record.data[0]['id']
    
    # Check if user is creator
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    if group['creator_user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Only the group creator can delete this group")
    
    # Delete group members first (in case cascade doesn't work)
    supabase.table('group_members')\
        .delete()\
        .eq('group_id', group_id)\
        .execute()
    
    # Delete group
    supabase.table('roommate_groups')\
        .delete()\
        .eq('id', group_id)\
        .execute()
    
    return {
        "status": "success",
        "message": "Group deleted successfully"
    }


# =============================================================================
# Member Management Endpoints
# =============================================================================

@router.get("/{group_id}/members", response_model=dict)
async def get_group_members(
    group_id: str,
    token: Optional[str] = Depends(get_user_token),
    status_filter: Optional[str] = Query(None, description="Filter by member status")
):
    """
    Get all members of a group.
    Includes user details.
    """
    supabase = get_admin_client()
    
    # Check if group exists
    group_response = supabase.table('roommate_groups')\
        .select('id')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Get members
    query = supabase.table('group_members')\
        .select('*, users(id, email, full_name, profile_picture_url)')\
        .eq('group_id', group_id)
    
    if status_filter:
        query = query.eq('status', status_filter)
    
    members_response = query.execute()
    
    # Format member data
    members = []
    for member in members_response.data:
        user_data = member.get('users', {}) if isinstance(member.get('users'), dict) else {}
        members.append({
            'id': member.get('id'),
            'group_id': member.get('group_id'),
            'user_id': member.get('user_id'),
            'is_creator': member.get('is_creator', False),
            'status': member.get('status', 'unknown'),
            'joined_at': member.get('joined_at'),
            'user_email': user_data.get('email'),
            'user_name': user_data.get('full_name'),
            'user_picture': user_data.get('profile_picture_url')
        })
    
    return {
        "status": "success",
        "count": len(members),
        "data": members
    }


@router.post("/{group_id}/invite", response_model=dict)
async def invite_to_group(
    group_id: str,
    invite_data: GroupMemberInvite,
    token: str = Depends(require_user_token)
):
    """
    Invite a user to join the group by email.
    Requires authentication.
    Only group members can invite others.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    inviter_id = user_response.user.id
    
    # Check if group exists and user is a member
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    # Check if inviter is a member
    is_creator = group['creator_user_id'] == inviter_id
    
    if not is_creator:
        member_response = supabase.table('group_members')\
            .select('*')\
            .eq('group_id', group_id)\
            .eq('user_id', inviter_id)\
            .eq('status', 'accepted')\
            .execute()
        
        if not member_response.data:
            raise HTTPException(status_code=403, detail="Only group members can invite others")
    
    # Find user by email
    invited_user_response = supabase.table('users')\
        .select('id, email, full_name')\
        .eq('email', invite_data.user_email)\
        .single()\
        .execute()
    
    if not invited_user_response.data:
        raise HTTPException(status_code=404, detail=f"User with email {invite_data.user_email} not found")
    
    invited_user_id = invited_user_response.data['id']
    
    # Check if user is already a member or has pending invite
    existing_member = supabase.table('group_members')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('user_id', invited_user_id)\
        .execute()
    
    if existing_member.data:
        status = existing_member.data[0]['status']
        if status == 'accepted':
            raise HTTPException(status_code=400, detail="User is already a member of this group")
        elif status == 'pending':
            raise HTTPException(status_code=400, detail="User already has a pending invitation")
        elif status == 'rejected':
            # Update status back to pending
            supabase.table('group_members')\
                .update({'status': 'pending'})\
                .eq('id', existing_member.data[0]['id'])\
                .execute()
            
            return {
                "status": "success",
                "message": "Invitation re-sent successfully",
                "data": {
                    "group_id": group_id,
                    "invited_user_email": invite_data.user_email,
                    "status": "pending"
                }
            }
    
    # Create invitation
    member_data = {
        'group_id': group_id,
        'user_id': invited_user_id,
        'is_creator': False,
        'status': 'pending'
    }
    
    invite_response = supabase.table('group_members')\
        .insert(member_data)\
        .execute()
    
    # TODO: Send email notification to invited user
    
    return {
        "status": "success",
        "message": "Invitation sent successfully",
        "data": {
            "group_id": group_id,
            "invited_user_email": invite_data.user_email,
            "invited_user_name": invited_user_response.data.get('full_name'),
            "status": "pending"
        }
    }


@router.post("/{group_id}/request-join", response_model=dict)
async def request_join_group(
    group_id: str,
    token: str = Depends(require_user_token)
):
    """
    Request to join a group (self-invite).
    Creates a pending invitation for the current user.
    Requires authentication.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found. Please complete your profile first.")
    
    user_id = user_record.data[0]['id']
    
    # Check if user is already an accepted member of ANY group (including solo groups)
    # Users must leave their current group (even solo) before joining another
    existing_group_membership = supabase.table('group_members')\
        .select('group_id, roommate_groups(group_name, is_solo)')\
        .eq('user_id', user_id)\
        .eq('status', 'accepted')\
        .execute()
    
    if existing_group_membership.data and len(existing_group_membership.data) > 0:
        existing_group = existing_group_membership.data[0]
        group_info = existing_group.get('roommate_groups', {})
        is_solo = group_info.get('is_solo', False)
        group_name = group_info.get('group_name', 'a group')
        
        if is_solo:
            raise HTTPException(
                status_code=400, 
                detail="You are currently in a solo group. Please leave your solo group first before requesting to join another group."
            )
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"You are already a member of '{group_name}'. You can only be in one group at a time. Please leave your current group first."
            )
    
    # Check if group exists
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    # Check if user already has a pending request for THIS group
    existing_member = supabase.table('group_members')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .execute()
    
    if existing_member.data:
        status = existing_member.data[0]['status']
        if status == 'accepted':
            raise HTTPException(status_code=400, detail="You are already a member of this group")
        elif status == 'pending':
            raise HTTPException(status_code=400, detail="You already have a pending request to join")
        elif status == 'rejected':
            # Update status back to pending
            supabase.table('group_members')\
                .update({'status': 'pending'})\
                .eq('id', existing_member.data[0]['id'])\
                .execute()
            
            return {
                "status": "success",
                "message": "Join request sent successfully",
                "data": {
                    "group_id": group_id,
                    "group_name": group['group_name'],
                    "status": "pending"
                }
            }
    
    # Check if group is full
    current_members = supabase.table('group_members')\
        .select('user_id')\
        .eq('group_id', group_id)\
        .eq('status', 'accepted')\
        .execute()
    
    if len(current_members.data) >= group['target_group_size']:
        raise HTTPException(status_code=400, detail="Group is already full")
    
    # Create join request (pending invitation)
    member_data = {
        'group_id': group_id,
        'user_id': user_id,
        'is_creator': False,
        'status': 'pending'
    }
    
    supabase.table('group_members')\
        .insert(member_data)\
        .execute()
    
    return {
        "status": "success",
        "message": "Join request sent successfully. You can accept it from the Invitations page.",
        "data": {
            "group_id": group_id,
            "group_name": group['group_name'],
            "status": "pending"
        }
    }


@router.post("/{group_id}/join", response_model=dict)
async def join_group(
    group_id: str,
    token: str = Depends(require_user_token)
):
    """
    Accept invitation and join a group.
    Requires authentication.
    User must have a pending invitation.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    user_id = user_response.user.id
    
    # Check if group exists
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    # Check if user has pending invitation
    member_response = supabase.table('group_members')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .execute()
    
    if not member_response.data:
        raise HTTPException(status_code=400, detail="You don't have an invitation to this group")
    
    member = member_response.data[0]
    
    if member['status'] == 'accepted':
        raise HTTPException(status_code=400, detail="You are already a member of this group")
    
    if member['status'] == 'rejected':
        raise HTTPException(status_code=400, detail="You previously rejected this invitation")
    
    # Check if group is full
    target_size = group.get('target_group_size')
    if target_size is not None:
        current_members = supabase.table('group_members')\
            .select('user_id')\
            .eq('group_id', group_id)\
            .eq('status', 'accepted')\
            .execute()
        
        if len(current_members.data) >= target_size:
            raise HTTPException(status_code=400, detail="Group is already full")
    
    # Accept invitation
    supabase.table('group_members')\
        .update({'status': 'accepted'})\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .execute()
    
    # 🔥 AGGREGATE MEMBER PREFERENCES into group preferences
    from app.services.group_preferences_aggregator import calculate_aggregate_group_preferences
    
    aggregation_result = {'status': 'skipped'}
    try:
        aggregate_prefs = calculate_aggregate_group_preferences(group_id)
        
        # Update group with aggregated preferences
        update_data = {}
        
        if aggregate_prefs.get('budget_per_person_min') is not None:
            update_data['budget_per_person_min'] = float(aggregate_prefs['budget_per_person_min'])
        if aggregate_prefs.get('budget_per_person_max') is not None:
            update_data['budget_per_person_max'] = float(aggregate_prefs['budget_per_person_max'])
        if aggregate_prefs.get('target_move_in_date'):
            update_data['target_move_in_date'] = str(aggregate_prefs['target_move_in_date'])
        if aggregate_prefs.get('target_bedrooms'):
            update_data['target_bedrooms'] = aggregate_prefs['target_bedrooms']
        if aggregate_prefs.get('target_bathrooms'):
            update_data['target_bathrooms'] = aggregate_prefs['target_bathrooms']
        
        if update_data:
            supabase.table('roommate_groups').update(update_data).eq('id', group_id).execute()
            aggregation_result = {
                'status': 'success',
                'updated_fields': list(update_data.keys()),
                'aggregate_prefs': {
                    'budget_min': update_data.get('budget_per_person_min'),
                    'budget_max': update_data.get('budget_per_person_max'),
                    'move_in_date': update_data.get('target_move_in_date'),
                    'bedrooms': update_data.get('target_bedrooms'),
                    'bathrooms': update_data.get('target_bathrooms')
                }
            }
    except Exception as e:
        aggregation_result = {'status': 'error', 'message': str(e)}
    
    # 🔥 TRIGGER STABLE MATCHING
    from app.routes.stable_matching import run_matching, RunMatchingRequest
    
    target_city = group.get('target_city')
    matching_result = {'status': 'skipped', 'message': 'No city specified'}
    
    if target_city:
        try:
            matching_request = RunMatchingRequest(city=target_city, date_flexibility_days=30)
            matching_response = await run_matching(matching_request)
            matching_result = {
                "status": "success",
                "city": target_city,
                "total_matches": len(matching_response.matches),
                "message": matching_response.message
            }
        except Exception as e:
            matching_result = {"status": "error", "message": str(e)}
    
    # Get updated group info
    updated_group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    updated_group = updated_group_response.data if updated_group_response.data else group
    
    return {
        "status": "success",
        "message": "Successfully joined the group",
        "data": {
            "group_id": group_id,
            "group_name": group['group_name'],
            "current_member_count": updated_group.get('current_member_count', 1)
        },
        "preference_aggregation": aggregation_result,
        "matching": matching_result
    }



@router.post("/{group_id}/reject", response_model=dict)
async def reject_invitation(
    group_id: str,
    token: str = Depends(require_user_token)
):
    """
    Reject a group invitation.
    Requires authentication.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    user_id = user_record.data[0]['id']
    
    # Check if user has pending invitation
    member_response = supabase.table('group_members')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .eq('status', 'pending')\
        .execute()
    
    if not member_response.data:
        raise HTTPException(status_code=400, detail="No pending invitation found")
    
    # Reject invitation
    supabase.table('group_members')\
        .update({'status': 'rejected'})\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .execute()
    
    return {
        "status": "success",
        "message": "Invitation rejected"
    }


@router.post("/{group_id}/accept-request/{user_id}", response_model=dict)
async def accept_join_request(
    group_id: str,
    user_id: str,
    token: str = Depends(require_user_token)
):
    """
    Accept a user's request to join the group (creator only).
    
    This allows group creators to approve solo users who want to join their group.
    """
    supabase = get_admin_client()
    
    # Get current user (group creator)
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    current_user_id = user_record.data[0]['id']
    
    # Check if group exists and current user is creator
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    if group['creator_user_id'] != current_user_id:
        raise HTTPException(status_code=403, detail="Only the group creator can accept join requests")
    
    # Check if target user has a pending request
    member_response = supabase.table('group_members')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .eq('status', 'pending')\
        .execute()
    
    if not member_response.data:
        raise HTTPException(status_code=400, detail="No pending join request found for this user")
    
    # Check if group is full
    target_size = group.get('target_group_size')
    if target_size is not None:
        current_members = supabase.table('group_members')\
            .select('user_id')\
            .eq('group_id', group_id)\
            .eq('status', 'accepted')\
            .execute()
        
        if len(current_members.data) >= target_size:
            raise HTTPException(status_code=400, detail="Group is already full")
    
    # Accept the request
    supabase.table('group_members')\
        .update({'status': 'accepted'})\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .execute()
    
    # Cancel all OTHER pending requests for this user (they can only be in one group)
    supabase.table('group_members')\
        .delete()\
        .eq('user_id', user_id)\
        .eq('status', 'pending')\
        .neq('group_id', group_id)\
        .execute()
    
    # Get user info for response
    user_info_response = supabase.table('users')\
        .select('email, full_name')\
        .eq('id', user_id)\
        .single()\
        .execute()
    
    user_info = user_info_response.data if user_info_response.data else {}
    
    # 🔥 TRIGGER STABLE MATCHING
    from app.routes.stable_matching import run_matching, RunMatchingRequest
    
    target_city = group.get('target_city')
    matching_result = {'status': 'skipped', 'message': 'No city specified'}
    
    if target_city:
        try:
            matching_request = RunMatchingRequest(city=target_city, date_flexibility_days=30)
            matching_response = await run_matching(matching_request)
            matching_result = {
                "status": "success",
                "city": target_city,
                "total_matches": len(matching_response.matches),
                "message": matching_response.message
            }
        except Exception as e:
            matching_result = {"status": "error", "message": str(e)}
    
    return {
        "status": "success",
        "message": f"Join request accepted. {user_info.get('full_name', 'User')} is now a member.",
        "data": {
            "group_id": group_id,
            "user_id": user_id,
            "user_name": user_info.get('full_name'),
            "user_email": user_info.get('email'),
            "status": "accepted"
        },
        "matching": matching_result
    }


@router.post("/{group_id}/reject-request/{user_id}", response_model=dict)
async def reject_join_request(
    group_id: str,
    user_id: str,
    token: str = Depends(require_user_token)
):
    """
    Reject a user's request to join the group (creator only).
    
    This allows group creators to decline solo users who want to join their group.
    """
    supabase = get_admin_client()
    
    # Get current user (group creator)
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    current_user_id = user_record.data[0]['id']
    
    # Check if group exists and current user is creator
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    if group['creator_user_id'] != current_user_id:
        raise HTTPException(status_code=403, detail="Only the group creator can reject join requests")
    
    # Check if target user has a pending request
    member_response = supabase.table('group_members')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .eq('status', 'pending')\
        .execute()
    
    if not member_response.data:
        raise HTTPException(status_code=400, detail="No pending join request found for this user")
    
    # Get user info for response
    user_info_response = supabase.table('users')\
        .select('email, full_name')\
        .eq('id', user_id)\
        .single()\
        .execute()
    
    user_info = user_info_response.data if user_info_response.data else {}
    
    # Reject the request (set status to rejected)
    supabase.table('group_members')\
        .update({'status': 'rejected'})\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .execute()
    
    return {
        "status": "success",
        "message": f"Join request from {user_info.get('full_name', 'user')} has been rejected.",
        "data": {
            "group_id": group_id,
            "user_id": user_id,
            "user_name": user_info.get('full_name'),
            "user_email": user_info.get('email'),
            "status": "rejected"
        }
    }


@router.delete("/{group_id}/leave", response_model=dict)
async def leave_group(
    group_id: str,
    token: str = Depends(require_user_token)
):
    """
    Leave a group.
    Requires authentication.
    If creator leaves:
      - If other members exist, ownership transfers to another member
      - If no other members, the group is deleted
    """
    import random
    
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    user_id = user_record.data[0]['id']
    
    # Check if group exists and get group info
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    # Check if user is member
    member_response = supabase.table('group_members')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .execute()
    
    if not member_response.data:
        raise HTTPException(status_code=400, detail="You are not a member of this group")
    
    member = member_response.data[0]
    
    # Handle creator leaving
    if member['is_creator']:
        # Get all other accepted members
        other_members_response = supabase.table('group_members')\
            .select('user_id')\
            .eq('group_id', group_id)\
            .eq('status', 'accepted')\
            .neq('user_id', user_id)\
            .execute()
        
        other_members = other_members_response.data or []
        
        if len(other_members) == 0:
            # Creator is the only member - delete the group
            # First delete all group_members entries (including pending requests)
            supabase.table('group_members')\
                .delete()\
                .eq('group_id', group_id)\
                .execute()
            
            # Then delete the group itself
            supabase.table('roommate_groups')\
                .delete()\
                .eq('id', group_id)\
                .execute()
            
            return {
                "status": "success",
                "message": "Successfully left the group. The group was deleted as you were the only member.",
                "data": {
                    "group_id": group_id,
                    "group_name": group['group_name'],
                    "group_deleted": True
                }
            }
        else:
            # Transfer ownership to a random remaining member
            new_creator = random.choice(other_members)
            new_creator_id = new_creator['user_id']
            
            # Update the new creator's is_creator flag
            supabase.table('group_members')\
                .update({'is_creator': True})\
                .eq('group_id', group_id)\
                .eq('user_id', new_creator_id)\
                .execute()
            
            # Update group's creator_user_id
            supabase.table('roommate_groups')\
                .update({'creator_user_id': new_creator_id})\
                .eq('id', group_id)\
                .execute()
            
            # Remove the old creator from the group
            supabase.table('group_members')\
                .delete()\
                .eq('group_id', group_id)\
                .eq('user_id', user_id)\
                .execute()
            
            # Get new creator's name for response
            new_creator_user = supabase.table('users')\
                .select('full_name, email')\
                .eq('id', new_creator_id)\
                .single()\
                .execute()
            
            new_creator_name = new_creator_user.data.get('full_name') or new_creator_user.data.get('email') if new_creator_user.data else 'another member'
            
            return {
                "status": "success",
                "message": f"Successfully left the group. Ownership transferred to {new_creator_name}.",
                "data": {
                    "group_id": group_id,
                    "group_name": group['group_name'],
                    "ownership_transferred": True,
                    "new_creator_id": new_creator_id
                }
            }
    
    # Regular member leaving - just remove them
    supabase.table('group_members')\
        .delete()\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .execute()
    
    # 🔄 AGGREGATE PREFERENCES after member leaves
    from app.services.group_preferences_aggregator import calculate_aggregate_group_preferences
    
    aggregation_result = {'status': 'skipped'}
    try:
        aggregate_prefs = calculate_aggregate_group_preferences(group_id)
        
        # Update group with aggregated preferences
        update_data = {}
        
        if aggregate_prefs.get('budget_per_person_min') is not None:
            update_data['budget_per_person_min'] = float(aggregate_prefs['budget_per_person_min'])
        if aggregate_prefs.get('budget_per_person_max') is not None:
            update_data['budget_per_person_max'] = float(aggregate_prefs['budget_per_person_max'])
        if aggregate_prefs.get('target_move_in_date'):
            update_data['target_move_in_date'] = str(aggregate_prefs['target_move_in_date'])
        if aggregate_prefs.get('target_bedrooms'):
            update_data['target_bedrooms'] = aggregate_prefs['target_bedrooms']
        if aggregate_prefs.get('target_bathrooms'):
            update_data['target_bathrooms'] = aggregate_prefs['target_bathrooms']
        
        if update_data:
            supabase.table('roommate_groups').update(update_data).eq('id', group_id).execute()
            aggregation_result = {
                'status': 'success',
                'updated_fields': list(update_data.keys()),
                'aggregate_prefs': {
                    'budget_min': update_data.get('budget_per_person_min'),
                    'budget_max': update_data.get('budget_per_person_max'),
                    'move_in_date': update_data.get('target_move_in_date'),
                    'bedrooms': update_data.get('target_bedrooms'),
                    'bathrooms': update_data.get('target_bathrooms')
                }
            }
    except Exception as e:
        aggregation_result = {'status': 'error', 'message': str(e)}
    
    # 🔥 TRIGGER STABLE MATCHING after member leaves
    from app.routes.stable_matching import run_matching, RunMatchingRequest
    
    target_city = group.get('target_city')
    matching_result = {'status': 'skipped', 'message': 'No city specified'}
    
    if target_city:
        try:
            matching_request = RunMatchingRequest(city=target_city, date_flexibility_days=30)
            matching_response = await run_matching(matching_request)
            matching_result = {
                "status": "success",
                "city": target_city,
                "total_matches": len(matching_response.matches),
                "message": matching_response.message
            }
        except Exception as e:
            matching_result = {"status": "error", "message": str(e)}
    
    return {
        "status": "success",
        "message": "Successfully left the group",
        "data": {
            "group_id": group_id,
            "group_name": group['group_name']
        },
        "aggregation": aggregation_result,
        "matching": matching_result
    }


@router.delete("/{group_id}/members/{member_user_id}", response_model=dict)
async def remove_member(
    group_id: str,
    member_user_id: str,
    token: str = Depends(require_user_token)
):
    """
    Remove a member from the group.
    Requires authentication.
    Only the creator can remove members.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the current user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    current_user_id = user_record.data[0]['id']
    
    # Check if current user is creator
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    if group['creator_user_id'] != current_user_id:
        raise HTTPException(status_code=403, detail="Only the group creator can remove members")
    
    # Check if target user is member
    member_response = supabase.table('group_members')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('user_id', member_user_id)\
        .execute()
    
    if not member_response.data:
        raise HTTPException(status_code=400, detail="User is not a member of this group")
    
    member = member_response.data[0]
    
    if member['is_creator']:
        raise HTTPException(status_code=400, detail="Cannot remove the group creator")
    
    # Remove member using composite key
    supabase.table('group_members')\
        .delete()\
        .eq('group_id', group_id)\
        .eq('user_id', member_user_id)\
        .execute()
    
    # 🔥 RE-AGGREGATE MEMBER PREFERENCES (now with one less member)
    from app.services.group_preferences_aggregator import calculate_aggregate_group_preferences
    
    aggregation_result = {'status': 'skipped'}
    try:
        aggregate_prefs = calculate_aggregate_group_preferences(group_id)
        
        # Update group with aggregated preferences
        update_data = {}
        
        if aggregate_prefs.get('budget_per_person_min') is not None:
            update_data['budget_per_person_min'] = float(aggregate_prefs['budget_per_person_min'])
        if aggregate_prefs.get('budget_per_person_max') is not None:
            update_data['budget_per_person_max'] = float(aggregate_prefs['budget_per_person_max'])
        if aggregate_prefs.get('target_move_in_date'):
            update_data['target_move_in_date'] = str(aggregate_prefs['target_move_in_date'])
        if aggregate_prefs.get('target_bedrooms'):
            update_data['target_bedrooms'] = aggregate_prefs['target_bedrooms']
        if aggregate_prefs.get('target_bathrooms'):
            update_data['target_bathrooms'] = aggregate_prefs['target_bathrooms']
        
        if update_data:
            supabase.table('roommate_groups').update(update_data).eq('id', group_id).execute()
            aggregation_result = {
                'status': 'success',
                'updated_fields': list(update_data.keys()),
                'aggregate_prefs': {
                    'budget_min': update_data.get('budget_per_person_min'),
                    'budget_max': update_data.get('budget_per_person_max'),
                    'move_in_date': update_data.get('target_move_in_date'),
                    'bedrooms': update_data.get('target_bedrooms'),
                    'bathrooms': update_data.get('target_bathrooms')
                }
            }
    except Exception as e:
        aggregation_result = {'status': 'error', 'message': str(e)}
    
    # 🔥 TRIGGER STABLE MATCHING
    from app.routes.stable_matching import run_matching, RunMatchingRequest
    
    target_city = group.get('target_city')
    matching_result = {'status': 'skipped', 'message': 'No city specified'}
    
    if target_city:
        try:
            matching_request = RunMatchingRequest(city=target_city, date_flexibility_days=30)
            matching_response = await run_matching(matching_request)
            matching_result = {
                "status": "success",
                "city": target_city,
                "total_matches": len(matching_response.matches),
                "message": matching_response.message
            }
        except Exception as e:
            matching_result = {"status": "error", "message": str(e)}
    
    return {
        "status": "success",
        "message": "Member removed successfully",
        "aggregation": aggregation_result,
        "matching": matching_result
    }


# =============================================================================
# Integration with Stable Matching
# =============================================================================

@router.get("/{group_id}/matches", response_model=dict)
async def get_group_matches(
    group_id: str,
    token: Optional[str] = Depends(get_user_token)
):
    """
    Get stable matches for a specific group.
    Returns active matches from the stable matching system.
    """
    supabase = get_admin_client()
    
    # Check if group exists
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Get matches from stable_matches table
    matches_response = supabase.table('stable_matches')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('status', 'active')\
        .order('group_rank')\
        .execute()
    
    matches = matches_response.data
    
    # Enrich with listing details
    for match in matches:
        listing_response = supabase.table('listings')\
            .select('*')\
            .eq('id', match['listing_id'])\
            .single()\
            .execute()
        
        if listing_response.data:
            match['listing'] = listing_response.data
    
    return {
        "status": "success",
        "group_id": group_id,
        "count": len(matches),
        "data": matches
    }


@router.get("/{group_id}/eligible-listings", response_model=dict)
async def get_eligible_listings_for_group(
    group_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max listings to return"),
    token: Optional[str] = Depends(get_user_token)
):
    """
    Get listings that match the group's HARD CONSTRAINTS only.
    
    This endpoint returns all listings that are feasible for the group based on:
    - Location match (same city)
    - Budget compatibility (per-person price within group's budget range)
    - Move-in date compatibility (within ±30 days of target date)
    - Required attributes (furnished, utilities, pets, parking, etc.)
    
    Unlike /matches (which returns LNS-optimized stable matches), this returns
    ALL listings that pass hard constraints - useful for browsing/exploration.
    
    Returns listings sorted by price (lowest first).
    """
    from app.services.stable_matching import (
        build_feasible_pairs,
        get_feasibility_statistics
    )
    
    supabase = get_admin_client()
    
    # Get group details
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    target_city = group.get('target_city')
    
    if not target_city:
        raise HTTPException(
            status_code=400, 
            detail="Group must have a target city to find eligible listings"
        )
    
    # Get active listings in the same city
    listings_response = supabase.table('listings')\
        .select('*')\
        .eq('city', target_city)\
        .eq('status', 'active')\
        .execute()
    
    all_listings = listings_response.data if listings_response.data else []
    
    if not all_listings:
        return {
            "status": "success",
            "group_id": group_id,
            "group_constraints": {
                "target_city": target_city,
                "budget_min": group.get('budget_per_person_min'),
                "budget_max": group.get('budget_per_person_max'),
                "target_move_in_date": str(group.get('target_move_in_date')) if group.get('target_move_in_date') else None
            },
            "count": 0,
            "listings": [],
            "message": f"No active listings found in {target_city}"
        }
    
    # Build feasible pairs (hard constraint filtering)
    feasible_pairs, rejection_reasons = build_feasible_pairs(
        groups=[group],
        listings=all_listings,
        date_delta_days=30,
        include_rejection_reasons=True
    )
    
    # Extract listing IDs that passed hard constraints
    eligible_listing_ids = set(listing_id for _, listing_id in feasible_pairs)
    
    # Filter and enrich listings
    eligible_listings = []
    for listing in all_listings:
        if listing['id'] in eligible_listing_ids:
            # Calculate per-person price
            price = float(listing.get('price_per_month', 0))
            listing['price_per_person'] = round(price / 2, 2)  # 2-person groups
            eligible_listings.append(listing)
    
    # Sort by price (lowest first)
    eligible_listings.sort(key=lambda x: x.get('price_per_month', float('inf')))
    
    # Apply limit
    eligible_listings = eligible_listings[:limit]
    
    # Get statistics
    stats = get_feasibility_statistics([group], all_listings, feasible_pairs)
    
    return {
        "status": "success",
        "group_id": group_id,
        "group_constraints": {
            "target_city": target_city,
            "budget_min": group.get('budget_per_person_min'),
            "budget_max": group.get('budget_per_person_max'),
            "target_move_in_date": str(group.get('target_move_in_date')) if group.get('target_move_in_date') else None,
            "target_furnished": group.get('target_furnished'),
            "target_utilities_included": group.get('target_utilities_included')
        },
        "stats": {
            "total_listings_in_city": stats['total_listings'],
            "eligible_count": stats['total_feasible_pairs'],
            "rejected_count": stats['listings_with_no_options']
        },
        "count": len(eligible_listings),
        "listings": eligible_listings
    }


@router.post("/{group_id}/confirm-match", response_model=dict)
async def confirm_match_as_group(
    group_id: str,
    token: str = Depends(require_user_token)
):
    """
    Confirm the current stable match as the group.
    
    This sets group_confirmed_at timestamp on the match.
    A match is fully confirmed when BOTH group and listing owner confirm.
    
    Confirmed matches are preserved during re-matching - only unconfirmed
    matches are recalculated when new groups join or preferences change.
    """
    from datetime import datetime, timezone
    
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    current_user_id = user_record.data[0]['id']
    
    # Check if user is a member of this group
    member_check = supabase.table('group_members')\
        .select('user_id, is_creator')\
        .eq('group_id', group_id)\
        .eq('user_id', current_user_id)\
        .eq('status', 'accepted')\
        .execute()
    
    if not member_check.data:
        raise HTTPException(status_code=403, detail="Only group members can confirm matches")
    
    # Get the active match for this group
    match_response = supabase.table('stable_matches')\
        .select('*, listings(id, title, city, price_per_month)')\
        .eq('group_id', group_id)\
        .eq('status', 'active')\
        .execute()
    
    if not match_response.data:
        raise HTTPException(status_code=404, detail="No active match found for this group")
    
    match = match_response.data[0]
    
    # Check if already confirmed by group
    if match.get('group_confirmed_at'):
        return {
            "status": "already_confirmed",
            "message": "This match was already confirmed by your group",
            "match_id": match['id'],
            "group_confirmed_at": match['group_confirmed_at'],
            "listing_confirmed_at": match.get('listing_confirmed_at'),
            "fully_confirmed": match.get('listing_confirmed_at') is not None
        }
    
    # Confirm the match
    now = datetime.now(timezone.utc).isoformat()
    
    update_response = supabase.table('stable_matches')\
        .update({'group_confirmed_at': now})\
        .eq('id', match['id'])\
        .execute()
    
    # Check if now fully confirmed
    listing_confirmed = match.get('listing_confirmed_at') is not None
    fully_confirmed = listing_confirmed  # Group just confirmed, so fully_confirmed depends on listing
    
    listing_info = match.get('listings', {})
    
    return {
        "status": "success",
        "message": "Match confirmed by group" + (" - Waiting for listing owner" if not fully_confirmed else " - Both parties confirmed!"),
        "match_id": match['id'],
        "listing": {
            "id": listing_info.get('id'),
            "title": listing_info.get('title'),
            "city": listing_info.get('city'),
            "price_per_month": listing_info.get('price_per_month')
        },
        "group_confirmed_at": now,
        "listing_confirmed_at": match.get('listing_confirmed_at'),
        "fully_confirmed": fully_confirmed
    }


@router.delete("/{group_id}/reject-match", response_model=dict)
async def reject_match_as_group(
    group_id: str,
    token: str = Depends(require_user_token)
):
    """
    Reject the current stable match as the group.
    
    This removes the match and optionally triggers re-matching
    to find a new match for the group.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    current_user_id = user_record.data[0]['id']
    
    # Check if user is a member of this group
    member_check = supabase.table('group_members')\
        .select('user_id')\
        .eq('group_id', group_id)\
        .eq('user_id', current_user_id)\
        .eq('status', 'accepted')\
        .execute()
    
    if not member_check.data:
        raise HTTPException(status_code=403, detail="Only group members can reject matches")
    
    # Get the active match for this group
    match_response = supabase.table('stable_matches')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('status', 'active')\
        .execute()
    
    if not match_response.data:
        raise HTTPException(status_code=404, detail="No active match found for this group")
    
    match = match_response.data[0]
    
    # Check if already confirmed by BOTH parties - can't reject a fully confirmed match
    if match.get('group_confirmed_at') and match.get('listing_confirmed_at'):
        raise HTTPException(
            status_code=400, 
            detail="Cannot reject a fully confirmed match. Contact support if needed."
        )
    
    # Mark the match as cancelled
    supabase.table('stable_matches')\
        .update({'status': 'cancelled'})\
        .eq('id', match['id'])\
        .execute()
    
    # Get group to trigger re-matching
    group_response = supabase.table('roommate_groups')\
        .select('target_city')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    matching_result = {'status': 'skipped', 'message': 'No city specified'}
    
    if group_response.data and group_response.data.get('target_city'):
        from app.routes.stable_matching import run_matching, RunMatchingRequest
        
        target_city = group_response.data['target_city']
        try:
            matching_request = RunMatchingRequest(city=target_city, date_flexibility_days=30)
            matching_response = await run_matching(matching_request)
            matching_result = {
                "status": "success",
                "city": target_city,
                "total_matches": len(matching_response.matches),
                "message": "Re-matching completed"
            }
        except Exception as e:
            matching_result = {"status": "error", "message": str(e)}
    
    return {
        "status": "success",
        "message": "Match rejected. Re-matching triggered to find new options.",
        "rejected_match_id": match['id'],
        "matching": matching_result
    }


@router.get("/{group_id}/compatible-users", response_model=dict)
async def get_compatible_users(
    group_id: str,
    token: str = Depends(require_user_token)
):
    """
    Get users who are compatible with the group's hard constraints.
    
    Filters users based on:
    - Target city match
    - Budget overlap
    - Move-in date compatibility (within 30 days)
    - Not already a member or has pending invitation
    
    Returns user profiles with their preferences for invitation.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    auth_user_id = user_response.user.id
    
    # Look up the user in the users table by auth_id
    user_record = supabase.table('users').select('id').eq('auth_id', auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    
    current_user_id = user_record.data[0]['id']
    
    # Get the group details
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    # Check if current user is a member of this group
    member_check = supabase.table('group_members')\
        .select('user_id')\
        .eq('group_id', group_id)\
        .eq('user_id', current_user_id)\
        .eq('status', 'accepted')\
        .execute()
    
    if not member_check.data:
        raise HTTPException(status_code=403, detail="Only group members can view compatible users")
    
    # Get existing members and pending invitations to exclude them
    existing_members = supabase.table('group_members')\
        .select('user_id')\
        .eq('group_id', group_id)\
        .execute()
    
    excluded_user_ids = [m['user_id'] for m in existing_members.data]
    
    # Get all users with their preferences
    users_response = supabase.table('users')\
        .select('id, email, full_name, profile_picture_url, company_name, school_name, verification_status, bio')\
        .execute()
    
    # Get all personal preferences
    prefs_response = supabase.table('personal_preferences')\
        .select('*')\
        .execute()
    
    # Create a map of user_id -> preferences
    prefs_map = {p['user_id']: p for p in prefs_response.data}
    
    # Filter users based on hard constraints
    compatible_users = []
    
    group_city = group.get('target_city', '').lower().strip()
    group_budget_min = group.get('budget_per_person_min') or 0
    group_budget_max = group.get('budget_per_person_max') or float('inf')
    group_move_in = group.get('target_move_in_date')
    
    for user_data in users_response.data:
        user_id = user_data['id']
        
        # Skip excluded users (already members or self)
        if user_id in excluded_user_ids:
            continue
        
        prefs = prefs_map.get(user_id, {})
        
        # Hard constraint 1: City match
        user_city = (prefs.get('target_city') or '').lower().strip()
        if group_city and user_city and group_city != user_city:
            # Allow partial match (e.g., "sf" matches "san francisco")
            if group_city not in user_city and user_city not in group_city:
                continue
        
        # Hard constraint 2: Budget overlap
        user_budget_min = prefs.get('budget_min') or 0
        user_budget_max = prefs.get('budget_max') or float('inf')
        
        # Check if ranges overlap
        if user_budget_max < group_budget_min or user_budget_min > group_budget_max:
            continue
        
        # Hard constraint 3: Move-in date compatibility (within 30 days)
        if group_move_in and prefs.get('move_in_date'):
            from datetime import datetime, timedelta
            try:
                group_date = datetime.fromisoformat(str(group_move_in).replace('Z', '+00:00')).date() if isinstance(group_move_in, str) else group_move_in
                user_date = datetime.fromisoformat(str(prefs['move_in_date']).replace('Z', '+00:00')).date() if isinstance(prefs['move_in_date'], str) else prefs['move_in_date']
                
                date_diff = abs((group_date - user_date).days)
                if date_diff > 30:
                    continue
            except (ValueError, TypeError):
                pass  # If dates can't be parsed, don't filter on this constraint
        
        # Calculate compatibility score (soft constraints)
        compatibility_score = 100  # Start with perfect score
        compatibility_reasons = []
        
        # Check lifestyle preferences overlap
        user_lifestyle = prefs.get('lifestyle_preferences', {}) or {}
        
        # Add user to compatible list
        compatible_users.append({
            'id': user_id,
            'email': user_data.get('email'),
            'full_name': user_data.get('full_name'),
            'profile_picture_url': user_data.get('profile_picture_url'),
            'company_name': user_data.get('company_name'),
            'school_name': user_data.get('school_name'),
            'verification_status': user_data.get('verification_status'),
            'bio': user_data.get('bio'),
            'preferences': {
                'target_city': prefs.get('target_city'),
                'budget_min': prefs.get('budget_min'),
                'budget_max': prefs.get('budget_max'),
                'move_in_date': str(prefs.get('move_in_date')) if prefs.get('move_in_date') else None,
                'lifestyle_preferences': user_lifestyle,
                'preferred_neighborhoods': prefs.get('preferred_neighborhoods', [])
            },
            'compatibility_score': compatibility_score
        })
    
    # Sort by compatibility score (highest first)
    compatible_users.sort(key=lambda u: u['compatibility_score'], reverse=True)
    
    return {
        "status": "success",
        "group_id": group_id,
        "group_constraints": {
            "target_city": group.get('target_city'),
            "budget_min": group.get('budget_per_person_min'),
            "budget_max": group.get('budget_per_person_max'),
            "move_in_date": str(group.get('target_move_in_date')) if group.get('target_move_in_date') else None
        },
        "count": len(compatible_users),
        "users": compatible_users
    }

# =============================================================================
