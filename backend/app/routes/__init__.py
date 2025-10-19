"""
Routes package
API endpoint definitions
"""

from .users import router as users_router
from .listings import router as listings_router
from .admin import router as admin_router

__all__ = [
    "users_router",
    "listings_router",
    "admin_router",
]
