"""
Padly API - Main Application
A trusted platform for students, interns, and early-career professionals 
to find housing and compatible roommates.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import (
    users_router,
    listings_router,
    roommates_router,
    preferences_router,
    admin_router,
    authenticated_admin_router,
    auth_router,
    matches_router,
    recommendations_router,
    interactions_router,
    options_router,
)
from app.routes.roommate_intros import router as roommate_intros_router
from app.routes.groups import router as groups_router

# Initialize FastAPI application
app = FastAPI(
    title="Padly API",
    version="1.0.0",
    description="Backend API for Padly - Housing and Roommate Matching Platform",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS (Starlette returns 400 on failed preflight — usually wrong Origin)
_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://[::1]:3000",
]
_extra = os.getenv("CORS_ORIGINS", "").strip()
if _extra:
    _cors_origins.extend(o.strip() for o in _extra.split(",") if o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # IPv6 loopback [::1], any dev port, or LAN when using `next dev -H 0.0.0.0`
    allow_origin_regex=(
        r"^https?://((localhost|127\.0\.0\.1|\[::1\])(:\d+)?|"
        r"192\.168\.\d{1,3}\.\d{1,3}(:\d+)?|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?)$"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(listings_router)
app.include_router(roommates_router)
app.include_router(groups_router)  # Roommate groups endpoints
app.include_router(preferences_router)
app.include_router(matches_router)
app.include_router(admin_router)
app.include_router(authenticated_admin_router)
app.include_router(recommendations_router)
app.include_router(interactions_router)
app.include_router(options_router)
app.include_router(roommate_intros_router)


# Root endpoints
@app.get("/", tags=["root"])
async def root():
    """Welcome endpoint"""
    return {
        "message": "Welcome to Padly API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["root"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Padly API",
        "version": "1.0.0"
    }
