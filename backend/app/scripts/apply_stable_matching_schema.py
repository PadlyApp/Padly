"""
Apply Stable Matching Schema to Supabase

This script helps apply the stable matching schema to the database.
Since Supabase Python client doesn't support raw SQL execution,
this script provides instructions and validation.

Run with:
    cd /Users/yousefmaher/Padly/backend
    python -m app.scripts.apply_stable_matching_schema
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.dependencies.supabase import get_admin_client

def main():
    print("\n" + "="*80)
    print("STABLE MATCHING SCHEMA APPLICATION")
    print("="*80)
    
    print("\n📋 Schema Location:")
    print("   app/schemas/stable_matching_schema.sql")
    
    print("\n🔧 What This Schema Does:")
    print("   ✓ Creates match_diagnostics table (stores matching round metrics)")
    print("   ✓ Creates stable_matches table (stores individual matches)")
    print("   ✓ Creates v_active_stable_matches view")
    print("   ✓ Creates expire_old_matches() function")
    print("   ✓ Creates auto-expiration trigger")
    print("   ✓ Adds indexes for performance")
    
    print("\n📤 TO APPLY THE SCHEMA:")
    print("   Option 1: Supabase Dashboard (Recommended)")
    print("   ─────────────────────────────────────────")
    print("   1. Go to: https://supabase.com/dashboard")
    print("   2. Select your project")
    print("   3. Go to: SQL Editor")
    print("   4. Click: New Query")
    print("   5. Copy contents from: app/schemas/stable_matching_schema.sql")
    print("   6. Paste and click: Run")
    
    print("\n   Option 2: Using psql (If you have direct DB access)")
    print("   ────────────────────────────────────────────────────")
    print("   psql <YOUR_DATABASE_URL> < app/schemas/stable_matching_schema.sql")
    
    print("\n✅ After Schema Application:")
    print("   Run Phase 5 tests to verify:")
    print("   python -m app.scripts.test_stable_matching_phase5")
    
    print("\n🔍 To check if tables exist:")
    supabase = get_admin_client()
    
    try:
        # Try to query match_diagnostics
        result = supabase.table('match_diagnostics').select('id').limit(0).execute()
        print("   ✅ match_diagnostics table exists")
    except Exception as e:
        if 'does not exist' in str(e) or 'schema cache' in str(e):
            print("   ❌ match_diagnostics table NOT FOUND")
        else:
            print(f"   ⚠️  Error checking match_diagnostics: {str(e)}")
    
    try:
        # Try to query stable_matches
        result = supabase.table('stable_matches').select('id').limit(0).execute()
        print("   ✅ stable_matches table exists")
    except Exception as e:
        if 'does not exist' in str(e) or 'schema cache' in str(e):
            print("   ❌ stable_matches table NOT FOUND")
        else:
            print(f"   ⚠️  Error checking stable_matches: {str(e)}")
    
    print("\n" + "="*80 + "\n")

if __name__ == '__main__':
    main()
