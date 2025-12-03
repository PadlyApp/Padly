#!/usr/bin/env python3
"""
Migration Runner Script
Applies SQL migrations to Supabase database
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.supabase_client import SupabaseHTTPClient


async def run_migration(migration_file: str):
    """
    Read and execute a migration file against Supabase
    
    Args:
        migration_file: Path to the SQL migration file
    """
    
    # Read migration file
    if not os.path.exists(migration_file):
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)
    
    with open(migration_file, 'r') as f:
        migration_sql = f.read()
    
    print(f"📋 Loading migration: {migration_file}")
    print(f"📊 SQL Length: {len(migration_sql)} characters")
    print("\n" + "="*60)
    print("MIGRATION CONTENT:")
    print("="*60)
    print(migration_sql)
    print("="*60 + "\n")
    
    # Get Supabase credentials from environment
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not service_key:
        print("❌ Missing Supabase credentials!")
        print("   SUPABASE_URL:", supabase_url)
        print("   SUPABASE_SERVICE_KEY:", "SET" if service_key else "NOT SET")
        sys.exit(1)
    
    print("✅ Supabase credentials loaded")
    print(f"   URL: {supabase_url}")
    
    # Create client with service key (admin access)
    client = SupabaseHTTPClient(token=service_key)
    
    try:
        print("\n🚀 Executing migration...")
        
        # Execute the SQL migration
        # Note: Supabase HTTP client doesn't directly support raw SQL
        # We'll use the native PostgreSQL connection via psql or Supabase API
        
        # For now, we'll provide instructions for manual execution
        print("\n⚠️  Supabase HTTP Client doesn't support raw SQL execution")
        print("\nTo apply this migration, please use one of these methods:")
        print("\n1️⃣  RECOMMENDED: Via Supabase Dashboard")
        print("   - Go to: https://app.supabase.com/")
        print("   - Navigate to: SQL Editor")
        print("   - Copy the migration SQL above")
        print("   - Paste and execute")
        
        print("\n2️⃣  Via PostgreSQL Client (if you have CLI access)")
        print("   psql <connection_string> < migration_file.sql")
        
        print("\n3️⃣  Via Supabase Python SDK")
        print("   - Install: pip install supabase")
        print("   - See: https://supabase.com/docs/reference/python/execute-sql")
        
        return False
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point"""
    
    # Default to 003_expand_personal_preferences if no argument
    migration_file = sys.argv[1] if len(sys.argv) > 1 else "migrations/003_expand_personal_preferences.sql"
    
    # Ensure relative path is from backend directory
    if not os.path.isabs(migration_file):
        backend_dir = Path(__file__).parent
        migration_file = os.path.join(backend_dir, migration_file)
    
    print("\n🔄 PADLY DATABASE MIGRATION RUNNER\n")
    
    success = await run_migration(migration_file)
    
    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n⚠️  Please apply the migration manually using one of the methods above")


if __name__ == "__main__":
    asyncio.run(main())
