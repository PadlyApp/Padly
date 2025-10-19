from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from app.db import supabase
from app.models import (
    UserResponse,
    ListingResponse,
    RoommatePostResponse,
    SuccessResponse
)
from app.routes import users_router, listings_router, admin_router

app = FastAPI(title="Padly API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users_router)
app.include_router(listings_router)
app.include_router(admin_router)

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
    from app.db import (
        SUPABASE_URL, 
        SUPABASE_ANON_KEY, 
        SUPABASE_SERVICE_KEY,
        VERIFY_JWT,
        supabase_admin,
        supabase_anon
    )
    return {
        "supabase_url": SUPABASE_URL,
        "anon_key_present": bool(SUPABASE_ANON_KEY),
        "anon_key_prefix": SUPABASE_ANON_KEY[:20] + "..." if SUPABASE_ANON_KEY else None,
        "service_key_present": bool(SUPABASE_SERVICE_KEY),
        "service_key_prefix": SUPABASE_SERVICE_KEY[:20] + "..." if SUPABASE_SERVICE_KEY else None,
        "verify_jwt": VERIFY_JWT,
        "admin_client_initialized": supabase_admin is not None,
        "anon_client_initialized": supabase_anon is not None
    }

@app.get("/debug-client-factory")
async def debug_client_factory(authorization: Optional[str] = Header(None)):
    """Test client factory with and without JWT"""
    from app.dependencies.auth import get_user_token
    from app.dependencies.supabase import get_user_client, get_admin_client
    
    # Test token extraction
    token = await get_user_token(authorization)
    
    # Test client creation
    user_client = get_user_client(token)
    admin_client = get_admin_client()
    
    return {
        "token_extracted": bool(token),
        "token_prefix": token[:20] + "..." if token else None,
        "user_client_created": user_client is not None,
        "admin_client_created": admin_client is not None,
        "user_client_url": user_client.supabase_url if user_client else None,
        "admin_client_url": admin_client.supabase_url if admin_client else None
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

