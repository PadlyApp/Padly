"""
Routes package
API endpoint definitions organized by resource
"""

from .users import router as users_router
from .listings import router as listings_router
from .roommates import router as roommates_router
from .preferences import router as preferences_router
from .admin import router as admin_router

__all__ = [
    "users_router",
    "listings_router",
    "roommates_router",
    "preferences_router",
    "admin_router",
]
