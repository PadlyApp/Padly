"""
Services package
Business logic and external service clients

Supabase access is consolidated through the facade in
``app.services.supabase_client.SupabaseHTTPClient`` (async CRUD) or
``app.dependencies.supabase.get_admin_client`` (sync supabase-py ``Client``).
"""

__all__: list[str] = []
