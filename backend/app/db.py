from supabase import create_client, Client
from dotenv import load_dotenv
import os
from pathlib import Path
import base64
import json

# Load the .env file from the backend directory (one level up from app/)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
VERIFY_JWT = os.getenv("VERIFY_JWT", "false").lower() == "true"
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


def _extract_jwt_role(jwt_token: str) -> str | None:
    """Best-effort JWT payload parse to validate expected Supabase key role."""
    try:
        parts = jwt_token.split('.')
        if len(parts) < 2:
            return None
        payload = parts[1]
        # JWT uses URL-safe base64 without padding.
        padding = '=' * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode((payload + padding).encode('utf-8')).decode('utf-8')
        return json.loads(decoded).get('role')
    except Exception:
        return None

# Validation
if not SUPABASE_URL:
    raise ValueError("Missing SUPABASE_URL in environment")
if not SUPABASE_ANON_KEY:
    raise ValueError("Missing SUPABASE_ANON_KEY in environment")
if not SUPABASE_SERVICE_KEY:
    raise ValueError("Missing SUPABASE_SERVICE_KEY in environment")

if SUPABASE_SERVICE_KEY == SUPABASE_ANON_KEY:
    raise ValueError("Invalid configuration: SUPABASE_SERVICE_KEY matches SUPABASE_ANON_KEY")

service_role = _extract_jwt_role(SUPABASE_SERVICE_KEY)
if service_role != "service_role":
    raise ValueError(
        f"Invalid SUPABASE_SERVICE_KEY role: expected 'service_role', got '{service_role or 'unknown'}'"
    )

# Create clients
# Service role client (admin operations, bypasses RLS)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Anon client (public operations, respects RLS)
supabase_anon: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Legacy alias for backward compatibility
supabase = supabase_admin
