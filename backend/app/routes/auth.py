"""
Authentication routes
Handles user signup, login, and JWT token management with Supabase Auth
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel, EmailStr
from app.db import supabase_anon
from app.dependencies.auth import get_user_token, resolve_auth_user

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
    created_auth_user_id = None

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

        created_auth_user_id = auth_response.user.id
        
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
        error_text = str(e)
        is_already_registered = (
            (hasattr(e, 'message') and "already registered" in str(e.message))
            or "already registered" in error_text.lower()
        )

        # Best-effort rollback so a partial signup doesn't leave a ghost auth user.
        if created_auth_user_id and not is_already_registered:
            try:
                from app.db import supabase_admin
                supabase_admin.auth.admin.delete_user(created_auth_user_id)
            except Exception:
                pass

        if 'row-level security policy' in error_text and 'table "users"' in error_text:
            raise HTTPException(
                status_code=500,
                detail=(
                    'Registration failed due to backend Supabase configuration. '
                    'Service role access for users table insert is not active.'
                )
            )
        if is_already_registered:
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

        # Block sign-in if email is not confirmed
        if not auth_response.user.email_confirmed_at:
            raise HTTPException(
                status_code=403,
                detail="Please verify your email address before signing in. Check your inbox for a confirmation link."
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
        
    except HTTPException:
        raise
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
        # Validate the JWT and get the Supabase auth user.
        # resolve_auth_user handles invalidated sessions (e.g. after sign-out)
        # with a clean 401 instead of an unhandled 500.
        from app.dependencies.supabase import get_admin_client

        admin = get_admin_client()
        auth_user = resolve_auth_user(supabase_anon, token)

        profile_response = admin.table("users").select("*").eq("auth_id", auth_user.id).execute()
        
        # If profile doesn't exist, create it
        if not profile_response.data:
            
            # Get user metadata from auth
            user_metadata = auth_user.user_metadata or {}
            full_name = (
                user_metadata.get("full_name")
                or user_metadata.get("name")
                or auth_user.email.split("@")[0]
            )
            profile_picture_url = user_metadata.get("avatar_url") or user_metadata.get("picture")

            # Create profile
            new_profile = {
                "auth_id": auth_user.id,
                "email": auth_user.email,
                "full_name": full_name,
            }
            if profile_picture_url:
                new_profile["profile_picture_url"] = profile_picture_url

            profile_response = admin.table("users").insert(new_profile).execute()

            # Auto-create solo group for new users (same as /signup)
            if profile_response.data:
                profile_id = profile_response.data[0].get("id")
                if profile_id:
                    existing_groups = admin.table("group_members")\
                        .select("group_id")\
                        .eq("user_id", profile_id)\
                        .eq("status", "accepted")\
                        .execute()

                    if not existing_groups.data:
                        solo_group_data = {
                            "creator_user_id": profile_id,
                            "group_name": f"{full_name}'s Housing Search",
                            "description": "Solo housing search",
                            "target_city": "San Francisco",
                            "target_group_size": 1,
                            "is_solo": True,
                            "status": "active"
                        }
                        group_response = admin.table("roommate_groups")\
                            .insert(solo_group_data)\
                            .execute()

                        if group_response.data:
                            solo_group = group_response.data[0]
                            member_data = {
                                "group_id": solo_group["id"],
                                "user_id": profile_id,
                                "is_creator": True,
                                "status": "accepted"
                            }
                            admin.table("group_members").insert(member_data).execute()

        profile = profile_response.data[0] if profile_response.data else None
        profile_id = profile.get("id") if profile else None

        # Check whether the user has ever saved housing preferences so the
        # frontend can decide to send them to /preferences-setup or /discover.
        has_preferences = False
        if profile_id:
            try:
                prefs_response = admin.table("personal_preferences")\
                    .select("user_id")\
                    .eq("user_id", profile_id)\
                    .limit(1)\
                    .execute()
                has_preferences = bool(prefs_response.data)
            except Exception:
                pass

        return {
            "user": {
                "id": auth_user.id,
                "email": auth_user.email,
                "profile": profile,
                "has_preferences": has_preferences,
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
