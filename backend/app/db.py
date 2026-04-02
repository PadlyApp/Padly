from supabase import create_client, Client
from dotenv import load_dotenv
import os
from pathlib import Path

# Load the .env file from the backend directory (one level up from app/)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
VERIFY_JWT = os.getenv("VERIFY_JWT", "false").lower() == "true"
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# Validation
if not SUPABASE_URL:
    raise ValueError("Missing SUPABASE_URL in environment")
if not SUPABASE_ANON_KEY:
    raise ValueError("Missing SUPABASE_ANON_KEY in environment")
if not SUPABASE_SERVICE_KEY:
    raise ValueError("Missing SUPABASE_SERVICE_KEY in environment")

# Create clients
# Service role client (admin operations, bypasses RLS)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Anon client (public operations, respects RLS)
supabase_anon: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Legacy alias for backward compatibility
supabase = supabase_admin
