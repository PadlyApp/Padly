from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.db import supabase

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

