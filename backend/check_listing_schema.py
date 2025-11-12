"""
Check what fields are actually in the listings table
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.dependencies.supabase import get_admin_client
import json


def check_listing_schema():
    """Check what fields exist in listings table"""
    
    print("="*80)
    print("CHECKING LISTINGS TABLE SCHEMA")
    print("="*80)
    
    supabase = get_admin_client()
    
    # Get one listing to see all fields
    response = supabase.table('listings').select('*').limit(1).execute()
    
    if response.data:
        listing = response.data[0]
        print(f"\n📋 Available fields in listings table:")
        print(json.dumps(listing, indent=2, default=str))
        
        print(f"\n📝 Field names:")
        for field in sorted(listing.keys()):
            value = listing[field]
            value_type = type(value).__name__
            print(f"   - {field}: {value_type} = {value}")
    else:
        print("No listings found")
    
    print(f"\n{'='*80}\n")


if __name__ == '__main__':
    check_listing_schema()
