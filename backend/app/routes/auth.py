"""
Authentication routes
Handles user signup, login, and JWT token management with Supabase Auth
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel, EmailStr
from app.db import supabase_anon
from app.dependencies.auth import get_user_token

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: dict


@router.post("/signup", response_model=AuthResponse)
async def signup(user_data: SignUpRequest):
    """
    Register a new user with Supabase Auth and create user profile.
    ALWAYS creates the user profile in public.users table.
    Also auto-creates a solo group for immediate housing search.
    """
    try:
        # Sign up with Supabase Auth
        auth_response = supabase_anon.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "full_name": user_data.full_name
                }
            }
        })
        
        if auth_response.user is None:
            raise HTTPException(
                status_code=400,
                detail="Failed to create user account"
            )
        
        # ALWAYS create user profile in users table (regardless of email confirmation)
        from app.db import supabase_admin
        
        # Check if profile already exists
        existing_profile = supabase_admin.table("users").select("*").eq("auth_id", auth_response.user.id).execute()
        
        if existing_profile.data:
            # Profile already exists, use it
            profile = existing_profile.data[0]
            profile_id = profile['id']
        else:
            # Create new profile
            user_profile = {
                "auth_id": auth_response.user.id,
                "email": user_data.email,
                "full_name": user_data.full_name,
            }
            profile_response = supabase_admin.table("users").insert(user_profile).execute()
            profile = profile_response.data[0] if profile_response.data else None
            profile_id = profile.get('id') if profile else None
        
        # 🔥 AUTO-CREATE SOLO GROUP for new users
        if profile_id:
            # Check if user already has a group
            existing_groups = supabase_admin.table("group_members")\
                .select("group_id")\
                .eq("user_id", profile_id)\
                .eq("status", "accepted")\
                .execute()
            
            if not existing_groups.data:
                # Create solo group
                solo_group_data = {
                    "creator_user_id": profile_id,
                    "group_name": f"{user_data.full_name}'s Housing Search",
                    "description": "Solo housing search",
                    "target_city": "San Francisco",  # Default, user can update
                    "target_group_size": 1,
                    "is_solo": True,
                    "status": "active"
                }
                
                group_response = supabase_admin.table("roommate_groups")\
                    .insert(solo_group_data)\
                    .execute()
                
                if group_response.data:
                    solo_group = group_response.data[0]
                    
                    # Add user as member
                    member_data = {
                        "group_id": solo_group['id'],
                        "user_id": profile_id,
                        "is_creator": True,
                        "status": "accepted"
                    }
                    
                    supabase_admin.table("group_members").insert(member_data).execute()
        
        # Check if session is available (might be None if email confirmation required)
        if auth_response.session is None:
            # Return a different response model for email confirmation case
            return Response(
                content='{"status": "email_confirmation_required", "message": "Account created successfully. Please check your email to confirm your account before signing in.", "user_id": "' + auth_response.user.id + '", "profile_id": "' + str(profile.get('id', '')) + '"}',
                status_code=202,
                media_type="application/json"
            )
        
        return AuthResponse(
            access_token=auth_response.session.access_token,
            refresh_token=auth_response.session.refresh_token,
            expires_in=auth_response.session.expires_in,
            user={
                "id": auth_response.user.id,
                "email": auth_response.user.email,
                "full_name": user_data.full_name,
                "profile": profile
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        if hasattr(e, 'message') and "already registered" in str(e.message):
            raise HTTPException(
                status_code=409,
                detail="User with this email already exists"
            )
        raise HTTPException(
            status_code=400,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/signin", response_model=AuthResponse)
async def signin(credentials: SignInRequest):
    """
    Sign in user with Supabase Auth.
    Auto-creates profile if missing (for legacy users).
    """
    try:
        # Sign in with Supabase Auth
        auth_response = supabase_anon.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if auth_response.user is None or auth_response.session is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        # Get user profile from users table
        from app.db import supabase_admin
        profile_response = supabase_admin.table("users").select("*").eq("auth_id", auth_response.user.id).execute()
        
        # If profile doesn't exist, create it (for legacy users)
        if not profile_response.data:
            user_metadata = auth_response.user.user_metadata or {}
            full_name = user_metadata.get("full_name", auth_response.user.email.split("@")[0])
            
            new_profile = {
                "auth_id": auth_response.user.id,
                "email": auth_response.user.email,
                "full_name": full_name,
            }
            
            profile_response = supabase_admin.table("users").insert(new_profile).execute()
        
        return AuthResponse(
            access_token=auth_response.session.access_token,
            refresh_token=auth_response.session.refresh_token,
            expires_in=auth_response.session.expires_in,
            user={
                "id": auth_response.user.id,
                "email": auth_response.user.email,
                "profile": profile_response.data[0] if profile_response.data else None
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh_token(body: RefreshRequest):
    """
    Refresh JWT token using the provided refresh token.
    """
    if not body.refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Refresh token required"
        )

    try:
        from app.db import supabase_admin
        auth_response = supabase_admin.auth.refresh_session(body.refresh_token)

        if not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        return {
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "expires_in": auth_response.session.expires_in,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token"
        )


@router.post("/signout")
async def signout(token: str = Depends(get_user_token)):
    """
    Sign out user and invalidate token.
    """
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    try:
        from app.db import supabase_admin
        supabase_admin.auth.admin.sign_out(token)
        return {"message": "Successfully signed out"}

    except Exception:
        # Best-effort — always return success so the client clears its state
        return {"message": "Successfully signed out"}


@router.get("/me")
async def get_current_user(token: str = Depends(get_user_token)):
    """
    Get current authenticated user profile.
    Auto-creates profile if missing.
    """
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    try:
        # Get user from JWT token
        user_response = supabase_anon.auth.get_user(token)
        
        if not user_response.user:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )
        
        # Get user profile — must use the admin client so that Row Level Security
        # on the users table does not block the lookup.
        from app.db import supabase_admin
        profile_response = supabase_admin.table("users").select("*").eq("auth_id", user_response.user.id).execute()
        
        # If profile doesn't exist, create it
        if not profile_response.data:
            
            # Get user metadata from auth
            user_metadata = user_response.user.user_metadata or {}
            full_name = user_metadata.get("full_name", user_response.user.email.split("@")[0])
            
            # Create profile
            new_profile = {
                "auth_id": user_response.user.id,
                "email": user_response.user.email,
                "full_name": full_name,
            }
            
            profile_response = supabase_admin.table("users").insert(new_profile).execute()
        
        return {
            "user": {
                "id": user_response.user.id,
                "email": user_response.user.email,
                "profile": profile_response.data[0] if profile_response.data else None
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
