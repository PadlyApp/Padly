"""
Authentication routes
Handles user signup, login, and JWT token management with Supabase Auth
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from typing import Optional
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
        
        # Check if session is available (might be None if email confirmation required)
        if auth_response.session is None:
            # Return a different response model for email confirmation case
            return Response(
                content='{"status": "email_confirmation_required", "message": "Account created successfully. Please check your email to confirm your account before signing in.", "user_id": "' + auth_response.user.id + '"}',
                status_code=202,
                media_type="application/json"
            )
        
        # Create user profile in users table
        user_profile = {
            "auth_id": auth_response.user.id,
            "email": user_data.email,
            "full_name": user_data.full_name,
        }
        
        # Insert user profile using service client (to bypass RLS during creation)
        from app.db import supabase_admin
        profile_response = supabase_admin.table("users").insert(user_profile).execute()
        
        return AuthResponse(
            access_token=auth_response.session.access_token,
            refresh_token=auth_response.session.refresh_token,
            expires_in=auth_response.session.expires_in,
            user={
                "id": auth_response.user.id,
                "email": auth_response.user.email,
                "full_name": user_data.full_name,
                "profile": profile_response.data[0] if profile_response.data else None
            }
        )
        
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
        profile_response = supabase_anon.table("users").select("*").eq("auth_id", auth_response.user.id).execute()
        
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


@router.post("/refresh")
async def refresh_token(token: str = Depends(get_user_token)):
    """
    Refresh JWT token.
    """
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Refresh token required"
        )
    
    try:
        auth_response = supabase_anon.auth.refresh_session()
        
        return {
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "expires_in": auth_response.session.expires_in
        }
        
    except Exception as e:
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
        supabase_anon.auth.sign_out()
        return {"message": "Successfully signed out"}
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Sign out failed: {str(e)}"
        )


@router.get("/me")
async def get_current_user(token: str = Depends(get_user_token)):
    """
    Get current authenticated user profile.
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
        
        # Get user profile
        profile_response = supabase_anon.table("users").select("*").eq("auth_id", user_response.user.id).execute()
        
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