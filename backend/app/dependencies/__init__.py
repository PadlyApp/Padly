"""
Dependencies package for FastAPI
Provides auth and Supabase client factories
"""

from .auth import get_user_token
from .supabase import get_user_client, get_admin_client

__all__ = [
    "get_user_token",
    "get_user_client",
    "get_admin_client",
]
