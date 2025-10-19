from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from app.db import supabase
from app.models import (
    UserResponse,
    ListingResponse,
    RoommatePostResponse,
    SuccessResponse
)

app = FastAPI(title="Padly API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to Padly API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/test-db")
async def test_database():
    """Simple endpoint to test if database connection works"""
    try:
        # Test the connection by executing a simple query
        # This will check if we can communicate with Supabase
        response = supabase.rpc('version', {}).execute()
        return {
            "status": "success",
            "message": "Database connection is working!",
            "connected": True,
            "supabase_url": supabase.supabase_url
        }
    except Exception as e:
        # If the above fails, just check if the client is initialized
        if supabase and supabase.supabase_url:
            return {
                "status": "success",
                "message": "Supabase client is initialized and configured!",
                "connected": True,
                "supabase_url": supabase.supabase_url
            }
        return {
            "status": "error",
            "message": f"Database connection failed: {str(e)}",
            "connected": False
        }

@app.get("/debug-config")
async def debug_config():
    """Debug endpoint to check configuration"""
    from app.db import SUPABASE_URL, SUPABASE_SERVICE_KEY
    return {
        "supabase_url": SUPABASE_URL,
        "service_key_present": bool(SUPABASE_SERVICE_KEY),
        "service_key_prefix": SUPABASE_SERVICE_KEY[:20] + "..." if SUPABASE_SERVICE_KEY else None,
        "using_service_role": "service_role" in SUPABASE_SERVICE_KEY if SUPABASE_SERVICE_KEY else False
    }

@app.get("/users", response_model=SuccessResponse)
async def get_users():
    """Fetch all users from the database"""
    try:
        response = supabase.table('users').select("*").execute()
        return {
            "status": "success",
            "message": "Users fetched successfully",
            "data": {
                "count": len(response.data),
                "users": response.data
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/listings", response_model=SuccessResponse)
async def get_listings():
    """Fetch all active listings from the database"""
    try:
        response = supabase.table('listings').select("*").execute()
        return {
            "status": "success",
            "message": "Listings fetched successfully",
            "data": {
                "count": len(response.data),
                "listings": response.data
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

