"""
Routes package
API endpoint definitions organized by resource
"""

from .users import router as users_router
from .listings import router as listings_router
from .roommates import router as roommates_router
from .preferences import router as preferences_router
from .admin import router as admin_router, authenticated_router as authenticated_admin_router
from .auth import router as auth_router
from .matches import router as matches_router
from .recommendations import router as recommendations_router
from .interactions import router as interactions_router
from .options import router as options_router
from .roommate_intros import router as roommate_intros_router

__all__ = [
    "users_router",
    "listings_router",
    "roommates_router",
    "preferences_router",
    "admin_router",
    "authenticated_admin_router",
    "auth_router",
    "matches_router",
    "recommendations_router",
    "interactions_router",
    "options_router",
    "roommate_intros_router",
]
