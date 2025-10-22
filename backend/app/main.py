"""
Padly API - Main Application
A trusted platform for students, interns, and early-career professionals 
to find housing and compatible roommates.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import (
    users_router, 
    listings_router,
    roommates_router,
    preferences_router,
    admin_router,
)

# Initialize FastAPI application
app = FastAPI(
    title="Padly API",
    version="1.0.0",
    description="Backend API for Padly - Housing and Roommate Matching Platform",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js frontend
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(users_router)
app.include_router(listings_router)
app.include_router(roommates_router)
app.include_router(preferences_router)
app.include_router(admin_router)


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
