"""
Authentication dependencies
Handles JWT token extraction from request headers
"""

from fastapi import Header, HTTPException
from typing import Optional, Any

from app.config import settings


async def require_admin_key(
    x_admin_secret: Optional[str] = Header(None)
) -> None:
    """
    Verify the X-Admin-Secret header matches the ADMIN_SECRET env variable.

    All /api/admin/* routes must depend on this to prevent unauthenticated
    access to service-role operations.

    Raises:
        HTTPException 401: if header is missing or incorrect
    """
    expected = settings.admin_secret
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin endpoints are disabled: ADMIN_SECRET is not configured on the server."
        )
    if x_admin_secret != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-Admin-Secret header."
        )


async def get_user_token(
    authorization: Optional[str] = Header(None)
) -> Optional[str]:
    """
    Extract JWT token from Authorization header.
    
    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")
    
    Returns:
        JWT token string or None if not provided
    
    Raises:
        HTTPException: If authorization header format is invalid
    
    Usage:
        @app.get("/api/users")
        async def list_users(token: str = Depends(get_user_token)):
            client = get_user_client(token)
            ...
    """
    if not authorization:
        # No token provided - allow anonymous access
        # RLS will handle permissions when enabled
        return None
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected 'Bearer <token>'"
        )
    
    # Extract token after "Bearer "
    token = authorization[7:]
    
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authorization token is empty"
        )
    
    return token


async def require_user_token(
    authorization: Optional[str] = Header(None)
) -> str:
    """
    Extract JWT token from Authorization header (required).
    Same as get_user_token but raises 401 if token is missing.
    
    Args:
        authorization: Authorization header value
    
    Returns:
        JWT token string
    
    Raises:
        HTTPException: If token is missing or invalid
    
    Usage:
        @app.post("/api/listings")
        async def create_listing(token: str = Depends(require_user_token)):
            client = get_user_client(token)
            ...
    """
    token = await get_user_token(authorization)
    
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authorization required. Please provide a valid JWT token."
        )
    
    return token


def resolve_auth_user(supabase_client: Any, token: str) -> Any:
    """
    Validate ``token`` with Supabase Auth and return the auth user object.

    Always uses the module-level ``supabase_anon`` client for the actual
    ``auth.get_user(token)`` call, regardless of the ``supabase_client``
    argument.  This is intentional: supabase-py 2.x dispatches an internal
    auth-state-change event after ``get_user(jwt)``, which can overwrite the
    PostgREST Authorization header on whatever client was used.  If we let
    that happen on the ``supabase_admin`` singleton the very next
    ``admin.table(...).execute()`` call would run with the user's JWT instead
    of the service-role key, causing RLS failures (→ unhandled exception →
    HTTP 500).  Using ``supabase_anon`` is safe because that client is never
    used for PostgREST DB queries, so its header state does not matter.

    The ``supabase_client`` parameter is kept for backward-compatibility but
    is no longer forwarded to ``auth.get_user``.

    Usage:
        supabase = get_admin_client()
        auth_user = resolve_auth_user(supabase, token)
        auth_user_id = auth_user.id
    """
    try:
        from supabase_auth.errors import AuthApiError
    except ImportError:
        AuthApiError = None  # type: ignore[assignment,misc]

    # Import here to avoid circular imports at module load time.
    try:
        from app.db import supabase_anon as _validator
    except Exception:
        # Fallback – should never happen in normal operation.
        _validator = supabase_client  # type: ignore[assignment]

    try:
        response = _validator.auth.get_user(token)
    except Exception as exc:
        if AuthApiError and isinstance(exc, AuthApiError):
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc

    if not response or not response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return response.user
