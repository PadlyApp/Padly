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
            user_id = user_response.user.id
            
            # Get groups where user is a member
            member_response = supabase.table('group_members')\
                .select('group_id')\
                .eq('user_id', user_id)\
                .execute()
            
            member_group_ids = [m['group_id'] for m in member_response.data]
            groups = [g for g in groups if g['id'] in member_group_ids]
    
    return {
        "status": "success",
        "count": len(groups),
        "data": groups
    }


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
    
    user_id = user_response.user.id
    
    # Create group
    group_dict = group_data.model_dump(exclude_none=True)
    group_dict['creator_user_id'] = user_id
    
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
    
    return {
        "status": "success",
        "message": "Group created successfully",
        "data": created_group
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
    Only the creator or group members can update.
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    user_id = user_response.user.id
    
    # Check if user is creator or member
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group = group_response.data
    
    # Check authorization (creator or member)
    is_creator = group['creator_user_id'] == user_id
    
    if not is_creator:
        # Check if user is a member
        member_response = supabase.table('group_members')\
            .select('*')\
            .eq('group_id', group_id)\
            .eq('user_id', user_id)\
            .eq('status', 'accepted')\
            .execute()
        
        if not member_response.data:
            raise HTTPException(status_code=403, detail="Only group members can update this group")
    
    # Update group
    update_dict = group_data.model_dump(exclude_none=True)
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    updated_response = supabase.table('roommate_groups')\
        .update(update_dict)\
        .eq('id', group_id)\
        .execute()
    
    return {
        "status": "success",
        "message": "Group updated successfully",
        "data": updated_response.data[0] if updated_response.data else None
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
    
    user_id = user_response.user.id
    
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
    
    # Delete group (cascade will delete members)
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
    
    # Check if user is already a member or has pending request
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
        .select('id')\
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
    current_members = supabase.table('group_members')\
        .select('id')\
        .eq('group_id', group_id)\
        .eq('status', 'accepted')\
        .execute()
    
    if len(current_members.data) >= group['target_group_size']:
        raise HTTPException(status_code=400, detail="Group is already full")
    
    # Accept invitation
    supabase.table('group_members')\
        .update({'status': 'accepted'})\
        .eq('id', member['id'])\
        .execute()
    
    return {
        "status": "success",
        "message": "Successfully joined the group",
        "data": {
            "group_id": group_id,
            "group_name": group['group_name']
        }
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
    
    user_id = user_response.user.id
    
    # Check if user has pending invitation
    member_response = supabase.table('group_members')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .eq('status', 'pending')\
        .execute()
    
    if not member_response.data:
        raise HTTPException(status_code=400, detail="No pending invitation found")
    
    member = member_response.data[0]
    
    # Reject invitation
    supabase.table('group_members')\
        .update({'status': 'rejected'})\
        .eq('id', member['id'])\
        .execute()
    
    return {
        "status": "success",
        "message": "Invitation rejected"
    }


@router.delete("/{group_id}/leave", response_model=dict)
async def leave_group(
    group_id: str,
    token: str = Depends(require_user_token)
):
    """
    Leave a group.
    Requires authentication.
    Creator cannot leave (must delete group or transfer ownership).
    """
    supabase = get_admin_client()
    
    # Get current user
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    user_id = user_response.user.id
    
    # Check if user is member
    member_response = supabase.table('group_members')\
        .select('*')\
        .eq('group_id', group_id)\
        .eq('user_id', user_id)\
        .execute()
    
    if not member_response.data:
        raise HTTPException(status_code=400, detail="You are not a member of this group")
    
    member = member_response.data[0]
    
    if member['is_creator']:
        raise HTTPException(
            status_code=400, 
            detail="Creator cannot leave the group. Please delete the group or transfer ownership."
        )
    
    # Remove member
    supabase.table('group_members')\
        .delete()\
        .eq('id', member['id'])\
        .execute()
    
    return {
        "status": "success",
        "message": "Successfully left the group"
    }


@router.delete("/{group_id}/members/{user_id}", response_model=dict)
async def remove_member(
    group_id: str,
    user_id: str,
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
    
    current_user_id = user_response.user.id
    
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
        .eq('user_id', user_id)\
        .execute()
    
    if not member_response.data:
        raise HTTPException(status_code=400, detail="User is not a member of this group")
    
    member = member_response.data[0]
    
    if member['is_creator']:
        raise HTTPException(status_code=400, detail="Cannot remove the group creator")
    
    # Remove member
    supabase.table('group_members')\
        .delete()\
        .eq('id', member['id'])\
        .execute()
    
    return {
        "status": "success",
        "message": "Member removed successfully"
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
