"""
Supabase client factory
Provides user and admin Supabase clients
"""

from supabase import Client, create_client
from typing import Optional
from app.db import (
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_KEY,
    supabase_admin
)


def get_user_client(user_token: Optional[str] = None) -> Client:
    """
    Create Supabase client for user operations.
    
    When RLS is enabled, this client will respect row-level security policies.
    - Without token: Acts as anonymous user (auth.uid() = NULL)
    - With token: Acts as authenticated user (auth.uid() = user's ID from JWT)
    
    Args:
        user_token: Optional JWT token from user's Authorization header
    
    Returns:
        Supabase client configured with user context
    
    Usage:
        # In a route with JWT dependency
        token = Depends(get_user_token)
        client = get_user_client(token)
        
        # Query will respect RLS when enabled
        response = client.table('users').select('*').execute()
    
    Important:
        - Always use ANON_KEY as the project key
        - Set user JWT via .postgrest.auth() for RLS enforcement
        - When RLS is disabled (dev), works with or without token
        - When RLS is enabled (prod), token determines access
    """
    # Create client with project's anon key
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    
    if user_token:
        # Set Authorization header with user's JWT
        # This tells Supabase to act as this user for RLS
        client.postgrest.auth(user_token)
    
    return client


def get_admin_client() -> Client:
    """
    Get admin Supabase client (bypasses RLS).
    
    This client uses SERVICE_ROLE_KEY and bypasses ALL row-level security.
    
    ⚠️ SECURITY WARNING:
        - NEVER expose this client or its responses directly to users
        - Only use in admin-protected routes
        - Only use for backend operations requiring full access
    
    Returns:
        Supabase client with service role permissions
    
    Usage:
        # In admin-only routes
        client = get_admin_client()
        
        # Can access any data regardless of RLS
        response = client.table('users').select('*').execute()

    Implementation note — singleton safety
    ----------------------------------------
    ``supabase_admin`` is a module-level singleton shared across all requests.
    supabase-py 2.x dispatches internal auth-state-change events that can
    overwrite ``postgrest.auth()`` when certain auth methods are called on the
    client.  ``resolve_auth_user`` now always uses ``supabase_anon`` for
    ``auth.get_user(token)`` to prevent this, but we still reset the header
    here as a belt-and-suspenders guard before every DB interaction.
    """
    supabase_admin.postgrest.auth(SUPABASE_SERVICE_KEY)
    return supabase_admin


def reset_admin_postgrest_auth() -> None:
    """
    Explicitly reset the supabase_admin PostgREST Authorization header back
    to the service-role key.

    Call this immediately after any ``auth.*`` operation performed on the
    ``supabase_admin`` singleton to prevent a stale user JWT from leaking
    into subsequent PostgREST queries.
    """
    supabase_admin.postgrest.auth(SUPABASE_SERVICE_KEY)
