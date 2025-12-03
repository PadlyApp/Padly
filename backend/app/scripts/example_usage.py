"""
Example: Using Parsed Data in Algorithms

This file demonstrates how to use the data parser service to get
listings and groups data, and how to work with the parsed JSON objects.
"""

import asyncio
import json
from app.services.data_parser import (
    fetch_and_parse_listings,
    fetch_and_parse_groups,
    fetch_parsed_data_for_algorithms,
    fetch_user_preferences,
    fetch_roommate_post
)


async def example_1_fetch_listings():
    """Example 1: Fetch and display all active listings"""
    print("=" * 80)
    print("EXAMPLE 1: Fetch Active Listings")
    print("=" * 80)
    
    listings = await fetch_and_parse_listings(status_filter="active")
    
    print(f"\nFound {len(listings)} active listings\n")
    
    for listing in listings[:3]:  # Show first 3
        print(f"📍 {listing['title']}")
        print(f"   Price: ${listing['price_per_month']}/month")
        print(f"   Location: {listing['city']}, {listing['state_province']}")
        print(f"   Bedrooms: {listing['number_of_bedrooms']}")
        print(f"   Type: {listing['property_type']}")
        print()
    
    return listings


async def example_2_fetch_groups():
    """Example 2: Fetch and display roommate groups"""
    print("=" * 80)
    print("EXAMPLE 2: Fetch Roommate Groups")
    print("=" * 80)
    
    groups = await fetch_and_parse_groups(
        status_filter="active",
        include_members=True
    )
    
    print(f"\nFound {len(groups)} active groups\n")
    
    for group in groups:
        print(f"👥 {group['group_name']}")
        print(f"   City: {group['target_city']}")
        print(f"   Budget: ${group['budget_per_person_min']}-${group['budget_per_person_max']} per person")
        print(f"   Size: {group.get('current_size', 0)}/{group['target_group_size']}")
        print()
    
    return groups


async def example_3_fetch_all_data():
    """Example 3: Fetch all algorithm data at once"""
    print("=" * 80)
    print("EXAMPLE 3: Fetch All Algorithm Data")
    print("=" * 80)
    
    data = await fetch_parsed_data_for_algorithms()
    
    listings = data['listings']
    groups = data['groups']
    
    print(f"\nFetched {len(listings)} listings and {len(groups)} groups")
    print("\nThis data is ready to use in matching algorithms!")
    
    return data


async def example_4_filter_by_price():
    """Example 4: Filter listings by price range"""
    print("=" * 80)
    print("EXAMPLE 4: Filter Listings by Price")
    print("=" * 80)
    
    listings = await fetch_and_parse_listings(status_filter="active")
    
    min_price = 2000
    max_price = 3000
    
    filtered = [
        listing for listing in listings
        if min_price <= listing['price_per_month'] <= max_price
    ]
    
    print(f"\nFound {len(filtered)} listings between ${min_price}-${max_price}/month\n")
    
    for listing in filtered:
        print(f"💰 {listing['title']}: ${listing['price_per_month']}/month")
    
    return filtered


async def example_5_filter_by_city():
    """Example 5: Filter by city and property type"""
    print("=" * 80)
    print("EXAMPLE 5: Filter by City and Property Type")
    print("=" * 80)
    
    listings = await fetch_and_parse_listings(status_filter="active")
    
    target_city = "San Francisco"
    property_type = "entire_place"
    
    filtered = [
        listing for listing in listings
        if listing['city'] == target_city and 
           listing['property_type'] == property_type
    ]
    
    print(f"\nFound {len(filtered)} '{property_type}' listings in {target_city}\n")
    
    for listing in filtered:
        print(f"🏠 {listing['title']}")
        print(f"   {listing['number_of_bedrooms']} bed, ${listing['price_per_month']}/month")
        print()
    
    return filtered


async def example_6_check_amenities():
    """Example 6: Filter listings by amenities"""
    print("=" * 80)
    print("EXAMPLE 6: Filter by Amenities")
    print("=" * 80)
    
    listings = await fetch_and_parse_listings(status_filter="active")
    
    required_amenities = ["wifi", "laundry", "parking"]
    
    filtered = []
    for listing in listings:
        amenities = listing.get('amenities', {})
        if all(amenities.get(am, False) for am in required_amenities):
            filtered.append(listing)
    
    print(f"\nFound {len(filtered)} listings with {', '.join(required_amenities)}\n")
    
    for listing in filtered:
        print(f"✅ {listing['title']}")
        print(f"   Amenities: {', '.join([k for k, v in listing['amenities'].items() if v])}")
        print()
    
    return filtered


async def example_7_score_listings():
    """Example 7: Score listings based on preferences"""
    print("=" * 80)
    print("EXAMPLE 7: Score Listings by Preferences")
    print("=" * 80)
    
    listings = await fetch_and_parse_listings(status_filter="active")
    
    # Mock user preferences
    user_prefs = {
        'target_city': 'San Francisco',
        'budget_max': 2500,
        'preferred_amenities': ['wifi', 'laundry', 'ac'],
        'furnished': True
    }
    
    def calculate_match_score(listing):
        score = 0
        
        # City match (30 points)
        if listing['city'] == user_prefs['target_city']:
            score += 30
        
        # Budget match (25 points)
        if listing['price_per_month'] <= user_prefs['budget_max']:
            score += 25
        
        # Furnished match (15 points)
        if listing['furnished'] == user_prefs['furnished']:
            score += 15
        
        # Amenities match (30 points - 10 per amenity)
        amenities = listing.get('amenities', {})
        for amenity in user_prefs['preferred_amenities']:
            if amenities.get(amenity, False):
                score += 10
        
        return score
    
    # Score and sort listings
    scored_listings = []
    for listing in listings:
        score = calculate_match_score(listing)
        scored_listings.append({
            'listing': listing,
            'match_score': score
        })
    
    scored_listings.sort(key=lambda x: x['match_score'], reverse=True)
    
    print(f"\nTop 5 Matches:\n")
    
    for i, item in enumerate(scored_listings[:5], 1):
        listing = item['listing']
        score = item['match_score']
        print(f"{i}. {listing['title']} - Score: {score}/100")
        print(f"   ${listing['price_per_month']}/month | {listing['city']}")
        print()
    
    return scored_listings


async def example_8_export_json():
    """Example 8: Export data to JSON files"""
    print("=" * 80)
    print("EXAMPLE 8: Export to JSON Files")
    print("=" * 80)
    
    data = await fetch_parsed_data_for_algorithms()
    
    # Export listings
    with open('example_listings.json', 'w') as f:
        json.dump(data['listings'], f, indent=2)
    print(f"\n✓ Exported {len(data['listings'])} listings to example_listings.json")
    
    # Export groups
    with open('example_groups.json', 'w') as f:
        json.dump(data['groups'], f, indent=2)
    print(f"✓ Exported {len(data['groups'])} groups to example_groups.json")
    
    # Export combined
    with open('example_combined.json', 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✓ Exported combined data to example_combined.json")
    
    print("\nFiles saved successfully!")


async def run_all_examples():
    """Run all examples"""
    try:
        await example_1_fetch_listings()
        print("\n")
        
        await example_2_fetch_groups()
        print("\n")
        
        await example_3_fetch_all_data()
        print("\n")
        
        await example_4_filter_by_price()
        print("\n")
        
        await example_5_filter_by_city()
        print("\n")
        
        await example_6_check_amenities()
        print("\n")
        
        await example_7_score_listings()
        print("\n")
        
        await example_8_export_json()
        print("\n")
        
        print("=" * 80)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_examples())
