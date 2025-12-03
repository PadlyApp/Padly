#!/usr/bin/env python3
"""
Populate dummy preferences for all users
This script adds test data to the personal_preferences table for all existing users
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.supabase_client import SupabaseHTTPClient


# Dummy preference templates
DUMMY_PREFERENCES = [
    {
        "target_city": "San Francisco",
        "target_state_province": "CA",
        "budget_min": 1500,
        "budget_max": 2500,
        "required_bedrooms": 1,
        "move_in_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
        "target_lease_type": "fixed",
        "target_lease_duration_months": 12,
        "target_bathrooms": 1.0,
        "target_furnished": True,
        "target_utilities_included": False,
        "target_deposit_amount": 1500,
        "target_house_rules": "No smoking, quiet hours after 10pm",
    },
    {
        "target_city": "Los Angeles",
        "target_state_province": "CA",
        "budget_min": 1200,
        "budget_max": 2000,
        "required_bedrooms": 2,
        "move_in_date": (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d"),
        "target_lease_type": "month_to_month",
        "target_lease_duration_months": 6,
        "target_bathrooms": 1.5,
        "target_furnished": False,
        "target_utilities_included": True,
        "target_deposit_amount": 1200,
        "target_house_rules": "Pet-friendly preferred",
    },
    {
        "target_city": "New York",
        "target_state_province": "NY",
        "budget_min": 1800,
        "budget_max": 3000,
        "required_bedrooms": 1,
        "move_in_date": (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d"),
        "target_lease_type": "fixed",
        "target_lease_duration_months": 12,
        "target_bathrooms": 1.0,
        "target_furnished": False,
        "target_utilities_included": False,
        "target_deposit_amount": 2000,
        "target_house_rules": "Vegetarian household",
    },
    {
        "target_city": "Chicago",
        "target_state_province": "IL",
        "budget_min": 1000,
        "budget_max": 1800,
        "required_bedrooms": 2,
        "move_in_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
        "target_lease_type": "fixed",
        "target_lease_duration_months": 12,
        "target_bathrooms": 1.0,
        "target_furnished": True,
        "target_utilities_included": True,
        "target_deposit_amount": 1000,
        "target_house_rules": "Early birds welcome",
    },
    {
        "target_city": "Austin",
        "target_state_province": "TX",
        "budget_min": 1100,
        "budget_max": 1900,
        "required_bedrooms": 1,
        "move_in_date": (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d"),
        "target_lease_type": "month_to_month",
        "target_lease_duration_months": 3,
        "target_bathrooms": 1.0,
        "target_furnished": False,
        "target_utilities_included": False,
        "target_deposit_amount": 1100,
        "target_house_rules": "Music enthusiasts, occasional jam sessions",
    },
]


async def populate_preferences():
    """
    Fetch all users and populate them with dummy preferences
    """
    # Get service key from environment
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not service_key:
        print("❌ Missing SUPABASE_SERVICE_KEY environment variable")
        sys.exit(1)
    
    client = SupabaseHTTPClient(token=service_key)
    
    try:
        # Fetch all users
        print("📋 Fetching all users...")
        users = await client.select(
            table="users",
            filters=None,
            limit=1000
        )
        
        if not users:
            print("⚠️  No users found in database")
            return
        
        print(f"✅ Found {len(users)} users")
        
        # Populate preferences for each user
        populated = 0
        skipped = 0
        failed = 0
        
        for i, user in enumerate(users):
            user_id = user.get("id")
            
            if not user_id:
                print(f"  ⚠️  User {i+1}: No ID found, skipping")
                skipped += 1
                continue
            
            # Check if preferences already exist
            existing = await client.select_one(
                table="personal_preferences",
                id_value=user_id,
                id_column="user_id"
            )
            
            if existing:
                print(f"  ⏭️  User {i+1} ({user.get('full_name', 'Unknown')}): Preferences already exist")
                skipped += 1
                continue
            
            # Get a dummy preference template (cycle through them)
            dummy_pref = DUMMY_PREFERENCES[i % len(DUMMY_PREFERENCES)]
            
            # Add user_id to the preference
            pref_data = {
                **dummy_pref,
                "user_id": user_id
            }
            
            try:
                # Insert the preference
                await client.insert(
                    table="personal_preferences",
                    data=pref_data
                )
                
                print(f"  ✅ User {i+1} ({user.get('full_name', 'Unknown')}): Preferences populated ({dummy_pref['target_city']})")
                populated += 1
                
            except Exception as e:
                print(f"  ❌ User {i+1} ({user.get('full_name', 'Unknown')}): Failed - {str(e)}")
                failed += 1
        
        print("\n" + "="*60)
        print(f"📊 SUMMARY")
        print("="*60)
        print(f"✅ Populated: {populated}")
        print(f"⏭️  Skipped (already exist): {skipped}")
        print(f"❌ Failed: {failed}")
        print(f"📈 Total processed: {len(users)}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def main():
    """Main entry point"""
    print("\n🚀 DUMMY PREFERENCES POPULATOR\n")
    await populate_preferences()
    print("\n✅ Done!\n")


if __name__ == "__main__":
    asyncio.run(main())
