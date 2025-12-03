"""
Test script for data parser - fetches and displays parsed data from Supabase
Run with: python -m app.scripts.test_data_parser
"""

import asyncio
import json
from app.services.data_parser import (
    fetch_and_parse_listings,
    fetch_and_parse_groups,
    fetch_parsed_data_for_algorithms
)


async def main():
    """Test the data parser functions"""
    
    print("=" * 80)
    print("FETCHING AND PARSING DATA FROM SUPABASE")
    print("=" * 80)
    print()
    
    # Fetch all algorithm data at once
    print("Fetching all parsed data for algorithms...")
    data = await fetch_parsed_data_for_algorithms()
    
    listings = data['listings']
    groups = data['groups']
    
    print(f"\n✓ Successfully fetched {len(listings)} listings and {len(groups)} groups")
    print()
    
    # Display listings summary
    print("-" * 80)
    print("LISTINGS SUMMARY")
    print("-" * 80)
    for i, listing in enumerate(listings, 1):
        print(f"\n{i}. {listing['title']}")
        print(f"   ID: {listing['id']}")
        print(f"   City: {listing['city']}, {listing['state_province']}")
        print(f"   Price: ${listing['price_per_month']}/month")
        print(f"   Property Type: {listing['property_type']}")
        print(f"   Bedrooms: {listing['number_of_bedrooms']}")
        print(f"   Furnished: {listing['furnished']}")
        print(f"   Available: {listing['available_from']} to {listing['available_to'] or 'Open-ended'}")
        print(f"   Status: {listing['status']}")
    
    # Display groups summary
    print()
    print("-" * 80)
    print("GROUPS SUMMARY")
    print("-" * 80)
    if groups:
        for i, group in enumerate(groups, 1):
            print(f"\n{i}. {group['group_name']}")
            print(f"   ID: {group['id']}")
            print(f"   City: {group['target_city']}")
            print(f"   Budget: ${group['budget_per_person_min']} - ${group['budget_per_person_max']} per person")
            print(f"   Target Size: {group['target_group_size']}")
            print(f"   Current Size: {group.get('current_size', 0)}")
            print(f"   Status: {group['status']}")
            if 'members' in group:
                print(f"   Members: {len(group['members'])}")
    else:
        print("\nNo groups found in the database.")
    
    # Save to JSON files
    print()
    print("-" * 80)
    print("SAVING TO JSON FILES")
    print("-" * 80)
    
    # Save listings
    with open('parsed_listings.json', 'w') as f:
        json.dump(listings, f, indent=2)
    print(f"✓ Saved {len(listings)} listings to parsed_listings.json")
    
    # Save groups
    with open('parsed_groups.json', 'w') as f:
        json.dump(groups, f, indent=2)
    print(f"✓ Saved {len(groups)} groups to parsed_groups.json")
    
    # Save combined data
    with open('parsed_algorithm_data.json', 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✓ Saved combined data to parsed_algorithm_data.json")
    
    print()
    print("=" * 80)
    print("COMPLETE - Data successfully parsed and saved!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
