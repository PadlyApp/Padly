import sys
import os
import asyncio

# Add backend directory to Python path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, backend_path)

from app.services.data_parser import fetch_parsed_data_for_algorithms
from datetime import datetime

def check_hard_constraints(group, listing):
    """
    Check if a listing passes all hard constraints for a group.
    Returns True if all constraints pass, False otherwise.
    
    Hard Constraints:
    1. City match
    2. State/Province match
    3. Budget (rent <= max_budget)
    4. Bedroom count match
    5. Move-in date availability
    6. Lease type match
    """
    
    # 1. City Match
    if group.get("target_city") != listing.get("city"):
        return False
    
    # 2. State/Province Match
    if group.get("target_state_province") != listing.get("state_province"):
        return False
    
    # 3. Budget Constraint (rent must be within budget)
    if listing.get("rent_amount") and group.get("max_budget"):
        if listing["rent_amount"] > group["max_budget"]:
            return False
    
    # 4. Bedroom Count Match
    if group.get("target_bedrooms") != listing.get("number_of_bedrooms"):
        return False
    
    # 5. Move-in Date Availability
    # Listing must be available by the time group wants to move in
    if listing.get("available_date") and group.get("move_in_date_start"):
        listing_date = datetime.fromisoformat(listing["available_date"].replace('Z', '+00:00'))
        group_date = datetime.fromisoformat(group["move_in_date_start"].replace('Z', '+00:00'))
        if listing_date > group_date:
            return False
    
    # 6. Lease Type Match
    if group.get("target_lease_type") != listing.get("lease_type"):
        return False
    
    # All constraints passed
    return True


def find_matches_for_group(group, listings):
    """
    Find all listings that pass hard constraints for a given group.
    Returns list of valid listings.
    """
    matches = []
    
    for listing in listings:
        if check_hard_constraints(group, listing):
            matches.append(listing)
    
    return matches


async def greedy_search():
    """Fetch data from Supabase and find matches for each group"""
    
    print("Fetching data from Supabase...")
    
    # Get all parsed data
    data = await fetch_parsed_data_for_algorithms()
    
    listings = data['listings']
    groups = data['groups']
    
    print(f"\n{'='*80}")
    print(f"GREEDY ALGORITHM MATCHING RESULTS")
    print(f"{'='*80}")
    print(f"Total Listings: {len(listings)}")
    print(f"Total Groups: {len(groups)}")
    print(f"{'='*80}\n")
    
    # Find matches for each group
    for idx, group in enumerate(groups, 1):
        matches = find_matches_for_group(group, listings)
        
        print(f"GROUP {idx}: {group.get('group_name', 'Unnamed Group')}")
        print(f"  ID: {group.get('id')}")
        print(f"  Requirements:")
        print(f"    • City: {group.get('target_city')}, State: {group.get('target_state_province')}")
        print(f"    • Max Budget: ${group.get('max_budget')}")
        print(f"    • Bedrooms: {group.get('target_bedrooms')}")
        print(f"    • Lease Type: {group.get('target_lease_type')}")
        print(f"    • Move-in Date: {group.get('move_in_date_start')}")
        print(f"  MATCHES FOUND: {len(matches)}")
        
        if matches:
            for match_idx, listing in enumerate(matches, 1):
                print(f"    [{match_idx}] {listing.get('title', 'Untitled Listing')}")
                print(f"        ID: {listing.get('id')}")
                print(f"        Rent: ${listing.get('price_per_month')}/mo | Bedrooms: {listing.get('number_of_bedrooms')}")
                print(f"        Location: {listing.get('city')}, {listing.get('state_province')}")
                print(f"        Lease: {listing.get('lease_type')} | Available: {listing.get('available_date')}")
        else:
            print(f"    ❌ No matching listings found")
        
        print(f"{'-'*80}\n")

if __name__ == "__main__":
    asyncio.run(greedy_search())
