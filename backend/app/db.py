"""
Supabase client singletons.

Reads credentials from ``app.config.settings`` (which loads the ``.env``
file automatically via pydantic-settings).  No direct ``os.getenv`` calls
are needed here.
"""

from supabase import create_client, Client

from app.config import settings

SUPABASE_URL: str = settings.supabase_url
SUPABASE_ANON_KEY: str = settings.supabase_anon_key
SUPABASE_SERVICE_KEY: str = settings.supabase_service_key

# Service role client (admin operations, bypasses RLS)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Anon client (public operations, respects RLS)
supabase_anon: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Legacy alias for backward compatibility
supabase = supabase_admin
