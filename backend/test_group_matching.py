"""
Test the stable matching API with a specific group ID
Group ID: 026a7755-9001-43f3-87b3-21e781f99881
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.dependencies.supabase import get_admin_client


async def test_group_matching():
    """Test matching for a specific group"""
    
    group_id = "026a7755-9001-43f3-87b3-21e781f99881"
    
    print("="*80)
    print(f"TESTING STABLE MATCHING FOR GROUP: {group_id}")
    print("="*80)
    
    supabase = get_admin_client()
    
    # 1. First, get the group details
    print(f"\n📋 Step 1: Fetching group details...")
    group_response = supabase.table('roommate_groups').select('*').eq('id', group_id).execute()
    
    if not group_response.data:
        print(f"❌ Group not found: {group_id}")
        return
    
    group = group_response.data[0]
    print(f"   ✅ Found group:")
    print(f"      Name: {group.get('group_name')}")
    print(f"      City: {group.get('target_city')}")
    print(f"      Size: {group.get('target_group_size')} members")
    print(f"      Budget per person: ${group.get('budget_per_person_min')}-${group.get('budget_per_person_max')}")
    print(f"      Move-in: {group.get('target_move_in_date')}")
    print(f"      Status: {group.get('status')}")
    
    city = group.get('target_city')
    
    if not city:
        print("\n❌ Group has no city set")
        return
    
    # 2. Find eligible listings in the same city
    print(f"\n🏠 Step 2: Finding eligible listings in {city}...")
    
    listings_response = supabase.table('listings').select('*').eq('city', city).eq('status', 'active').execute()
    
    print(f"   Found {len(listings_response.data)} active listings in {city}")
    
    # 3. Now run the actual matching algorithm
    print(f"\n🚀 Step 3: Running stable matching algorithm...")
    print(f"   City: {city}")
    
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    
    # Run matching for this city
    response = client.post(
        "/api/stable-matches/run",
        json={
            "city": city,
            "batch_size": 50,
            "dry_run": False
        }
    )
    
    print(f"\n📊 Step 4: Results")
    print(f"   Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Status: {data.get('status')}")
        print(f"   Execution time: {data.get('execution_time_seconds')}s")
        
        diagnostics = data.get('diagnostics', {})
        print(f"\n   Diagnostics:")
        print(f"      Eligible groups: {diagnostics.get('eligible_groups_count')}")
        print(f"      Eligible listings: {diagnostics.get('eligible_listings_count')}")
        print(f"      Feasible pairs: {diagnostics.get('feasible_pairs_count')}")
        print(f"      Matched groups: {diagnostics.get('matched_groups_count')}")
        print(f"      Matched listings: {diagnostics.get('matched_listings_count')}")
        print(f"      Match quality: {diagnostics.get('match_quality_score')}")
        
        # 5. Check if our specific group got matched
        print(f"\n🔍 Step 5: Checking matches for group {group_id}...")
        
        matches_response = client.get(f"/api/stable-matches/active?group_id={group_id}")
        
        if matches_response.status_code == 200:
            matches_data = matches_response.json()
            match_count = matches_data.get('count', 0)
            
            print(f"   Found {match_count} match(es) for this group")
            
            if match_count > 0:
                for i, match in enumerate(matches_data.get('matches', []), 1):
                    print(f"\n   Match #{i}:")
                    print(f"      Match ID: {match.get('id')}")
                    print(f"      Listing ID: {match.get('listing_id')}")
                    print(f"      Group rank: {match.get('group_rank')}")
                    print(f"      Listing rank: {match.get('listing_rank')}")
                    print(f"      Group score: {match.get('group_score')}")
                    print(f"      Listing score: {match.get('listing_score')}")
                    print(f"      Is stable: {match.get('is_stable')}")
                    print(f"      Matched at: {match.get('matched_at')}")
                    print(f"      Expires: {match.get('expires_at')}")
                    print(f"      City: {match.get('city')}")
                    
                    # Get listing details
                    listing_id = match.get('listing_id')
                    listing_response = supabase.table('listings').select('*').eq('id', listing_id).execute()
                    
                    if listing_response.data:
                        listing = listing_response.data[0]
                        print(f"\n      Listing Details:")
                        print(f"         Title: {listing.get('title')}")
                        print(f"         Address: {listing.get('address_line_1')}, {listing.get('city')}")
                        print(f"         Rent: ${listing.get('price_per_month')}/month")
                        print(f"         Bedrooms: {listing.get('number_of_bedrooms')}")
                        print(f"         Bathrooms: {listing.get('number_of_bathrooms')}")
            else:
                print(f"\n   ⚠️  No matches found for this group")
                print(f"   Possible reasons:")
                print(f"      - No feasible pairs (hard constraints not met)")
                print(f"      - Group was outbid by other groups")
                print(f"      - Listings preferred other groups")
        
    else:
        print(f"   ❌ Error: {response.status_code}")
        print(f"   {response.json()}")
    
    print(f"\n{'='*80}\n")


if __name__ == '__main__':
    asyncio.run(test_group_matching())
