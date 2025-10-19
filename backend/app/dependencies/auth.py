"""
Authentication dependencies
Handles JWT token extraction from request headers
"""

from fastapi import Header, HTTPException
from typing import Optional


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
