"""
Interactions API — assembled from sub-routers.

Sub-modules:
    swipes          — swipe event capture and history
    recommendations — sessions, feedback, passive engagement
    group_saves     — group save/unsave, group-liked listings
    interested      — user interested-listings
    analytics       — behavior vectors, data logging (views, searches)
"""

from fastapi import APIRouter

from .swipes import router as swipes_router
from .recommendations import router as recommendations_router
from .group_saves import router as group_saves_router
from .interested import router as interested_router
from .analytics import router as analytics_router

router = APIRouter(prefix="/api/interactions", tags=["interactions"])

router.include_router(swipes_router)
router.include_router(recommendations_router)
router.include_router(group_saves_router)
router.include_router(interested_router)
router.include_router(analytics_router)

__all__ = ["router"]
