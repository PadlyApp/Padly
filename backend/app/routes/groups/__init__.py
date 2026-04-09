"""
Roommate Groups API — assembled from sub-routers.

Sub-modules:
    crud       — list, get, create, update, delete
    members    — invite, join, leave, accept/reject, remove
    discovery  — discover, pending-requests, compatible-users
    listings   — matches, eligible-listings, ranked-listings, neural-ranked
"""

from fastapi import APIRouter

from .crud import router as crud_router
from .members import router as members_router
from .discovery import router as discovery_router
from .listings import router as listings_router

router = APIRouter(prefix="/api/roommate-groups", tags=["Roommate Groups"])

router.include_router(crud_router)
router.include_router(members_router)
router.include_router(discovery_router)
router.include_router(listings_router)

__all__ = ["router"]
