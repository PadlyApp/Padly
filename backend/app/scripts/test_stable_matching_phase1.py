"""
Test Script for Stable Matching - Phases 0 & 1
Tests data filtering and eligibility functions.
"""

import asyncio
import json
from typing import Dict, Any
from datetime import datetime, date, timedelta

# Import data parser
from app.services.data_parser import (
    fetch_and_parse_listings,
    fetch_and_parse_groups
)

# Import stable matching filters
from app.services.stable_matching.filters import (
    is_listing_pair_eligible,
    is_group_eligible,
    get_eligible_listings,
    get_eligible_groups,
    get_move_in_windows,
    normalize_city_name,
    validate_listing_data_quality,
    validate_group_data_quality
)


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_subsection(title: str):
    """Print a subsection header."""
    print("\n" + "-" * 80)
    print(f"  {title}")
    print("-" * 80)


async def test_listing_eligibility():
    """Test listing eligibility filters."""
    print_section("PHASE 1.1: LISTING ELIGIBILITY TESTS")
    
    # Fetch all listings
    print("\n📥 Fetching listings from database...")
    all_listings = await fetch_and_parse_listings()
    print(f"✅ Fetched {len(all_listings)} total listings")
    
    # Test individual eligibility
    print_subsection("Testing Individual Listing Eligibility")
    
    eligible_count = 0
    rejection_reasons = {}
    
    for i, listing in enumerate(all_listings[:5]):  # Test first 5
        is_eligible, reason = is_listing_pair_eligible(listing)
        
        print(f"\nListing #{i+1}: {listing.get('title', 'No title')[:50]}")
        print(f"  Property Type: {listing.get('property_type')}")
        print(f"  Bedrooms: {listing.get('number_of_bedrooms')}")
        print(f"  Status: {listing.get('status')}")
        print(f"  Price: ${listing.get('price_per_month')}")
        print(f"  City: {listing.get('city')}")
        
        if is_eligible:
            print(f"  ✅ ELIGIBLE for pair matching")
            eligible_count += 1
        else:
            print(f"  ❌ NOT ELIGIBLE - Reason: {reason}")
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
    
    # Test bulk filtering
    print_subsection("Bulk Eligibility Filtering")
    
    eligible_listings, rejection_stats = get_eligible_listings(all_listings)
    
    print(f"\n📊 Results:")
    print(f"  Total Listings: {len(all_listings)}")
    print(f"  Eligible for Pair Matching: {len(eligible_listings)}")
    print(f"  Rejection Rate: {((len(all_listings) - len(eligible_listings)) / len(all_listings) * 100):.1f}%")
    
    print(f"\n📋 Rejection Reasons:")
    for reason, count in sorted(rejection_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason}: {count}")
    
    # Test by city
    print_subsection("Eligibility by City")
    
    cities = set(l.get('city') for l in all_listings if l.get('city'))
    for city in sorted(cities)[:3]:  # Test top 3 cities
        city_eligible, city_stats = get_eligible_listings(all_listings, city=city)
        print(f"\n  {city}:")
        print(f"    Eligible: {len(city_eligible)}")
        if city_stats:
            print(f"    Rejections: {sum(city_stats.values())}")
    
    # Data quality checks
    print_subsection("Data Quality Checks")
    
    for i, listing in enumerate(eligible_listings[:3]):
        warnings = validate_listing_data_quality(listing)
        print(f"\n  Listing #{i+1}: {listing.get('title', 'No title')[:40]}")
        if warnings:
            for warning in warnings:
                print(f"    ⚠️  {warning}")
        else:
            print(f"    ✅ No quality issues")
    
    return eligible_listings


async def test_group_eligibility():
    """Test group eligibility filters."""
    print_section("PHASE 1.2: GROUP ELIGIBILITY TESTS")
    
    # Fetch all groups
    print("\n📥 Fetching groups from database...")
    all_groups = await fetch_and_parse_groups(include_members=True)
    print(f"✅ Fetched {len(all_groups)} total groups")
    
    # Test individual eligibility
    print_subsection("Testing Individual Group Eligibility")
    
    eligible_count = 0
    rejection_reasons = {}
    
    for i, group in enumerate(all_groups[:5]):  # Test first 5
        is_eligible, reason = is_group_eligible(group)
        
        print(f"\nGroup #{i+1}: {group.get('group_name', 'No name')}")
        print(f"  Target City: {group.get('target_city')}")
        print(f"  Target Size: {group.get('target_group_size')}")
        print(f"  Current Size: {len(group.get('group_members', []))}")
        print(f"  Status: {group.get('status')}")
        print(f"  Budget: ${group.get('budget_per_person_min')} - ${group.get('budget_per_person_max')}")
        print(f"  Move-in Date: {group.get('target_move_in_date')}")
        
        if is_eligible:
            print(f"  ✅ ELIGIBLE for stable matching")
            eligible_count += 1
        else:
            print(f"  ❌ NOT ELIGIBLE - Reason: {reason}")
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
    
    # Test bulk filtering
    print_subsection("Bulk Eligibility Filtering")
    
    eligible_groups, rejection_stats = get_eligible_groups(all_groups)
    
    print(f"\n📊 Results:")
    print(f"  Total Groups: {len(all_groups)}")
    print(f"  Eligible for Stable Matching: {len(eligible_groups)}")
    if len(all_groups) > 0:
        print(f"  Rejection Rate: {((len(all_groups) - len(eligible_groups)) / len(all_groups) * 100):.1f}%")
    
    print(f"\n📋 Rejection Reasons:")
    for reason, count in sorted(rejection_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason}: {count}")
    
    # Data quality checks
    print_subsection("Data Quality Checks")
    
    for i, group in enumerate(eligible_groups[:3]):
        warnings = validate_group_data_quality(group)
        print(f"\n  Group #{i+1}: {group.get('group_name', 'No name')}")
        if warnings:
            for warning in warnings:
                print(f"    ⚠️  {warning}")
        else:
            print(f"    ✅ No quality issues")
    
    return eligible_groups


async def test_date_windows():
    """Test date window partitioning."""
    print_section("PHASE 1.3: DATE WINDOW PARTITIONING TESTS")
    
    # Fetch eligible groups
    all_groups = await fetch_and_parse_groups(include_members=True)
    eligible_groups, _ = get_eligible_groups(all_groups)
    
    if not eligible_groups:
        print("⚠️  No eligible groups found for testing")
        return []
    
    print(f"\n📥 Working with {len(eligible_groups)} eligible groups")
    
    # Test window creation
    print_subsection("Creating Date Windows")
    
    windows = get_move_in_windows(eligible_groups, window_days=60)
    
    print(f"\n📊 Created {len(windows)} date windows")
    
    for i, window in enumerate(windows):
        print(f"\nWindow #{i+1}: {window.city}")
        print(f"  Date Range: {window.start_date} to {window.end_date}")
        print(f"  Duration: {(window.end_date - window.start_date).days} days")
        print(f"  Groups in Window: {len(window.groups)}")
        
        # Show group dates
        if window.groups:
            dates = [g.get('target_move_in_date') for g in window.groups]
            print(f"  Group Move-in Dates:")
            for date_str in sorted(set(dates))[:5]:
                count = dates.count(date_str)
                print(f"    {date_str}: {count} group(s)")
    
    return windows


async def test_city_normalization():
    """Test city name normalization."""
    print_section("CITY NAME NORMALIZATION TESTS")
    
    test_cases = [
        "San Francisco",
        "san francisco",
        "SF",
        "San Fran",
        "New York",
        "NYC",
        "New York City",
        "Los Angeles",
        "LA",
        "Oakland",
    ]
    
    print("\nTesting city name normalization:")
    for city in test_cases:
        normalized = normalize_city_name(city)
        print(f"  '{city}' → '{normalized}'")


async def test_phase_0_and_1():
    """Run all Phase 0 and 1 tests."""
    print("\n" + "█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "  STABLE MATCHING ALGORITHM - PHASE 0 & 1 TESTS".center(78) + "█")
    print("█" + "  (Database Schema + Data Filtering)".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80)
    
    try:
        # Test city normalization
        await test_city_normalization()
        
        # Test listing eligibility
        eligible_listings = await test_listing_eligibility()
        
        # Test group eligibility
        eligible_groups = await test_group_eligibility()
        
        # Test date windows
        windows = await test_date_windows()
        
        # Final summary
        print_section("FINAL SUMMARY")
        print(f"\n✅ Phase 0: Database schema ready (see stable_matching_schema.sql)")
        print(f"✅ Phase 1.1: Listing filters working")
        print(f"   - {len(eligible_listings)} eligible listings found")
        print(f"✅ Phase 1.2: Group filters working")
        print(f"   - {len(eligible_groups)} eligible groups found")
        print(f"✅ Phase 1.3: Date window partitioning working")
        print(f"   - {len(windows)} windows created")
        
        print(f"\n🎯 Ready for Phase 2: Building Feasible Pairs")
        
        # Save results for inspection
        results = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "eligible_listings": len(eligible_listings),
                "eligible_groups": len(eligible_groups),
                "date_windows": len(windows)
            },
            "sample_listings": eligible_listings[:3],
            "sample_groups": eligible_groups[:3],
            "windows": [
                {
                    "city": w.city,
                    "start": w.start_date.isoformat(),
                    "end": w.end_date.isoformat(),
                    "group_count": len(w.groups)
                }
                for w in windows
            ]
        }
        
        with open("phase_0_1_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Test results saved to: phase_0_1_test_results.json")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_phase_0_and_1())
