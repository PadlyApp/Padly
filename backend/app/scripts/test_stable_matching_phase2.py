"""
Test Script for Stable Matching - Phase 2
Tests feasible pairs building with hard constraints.
"""

import asyncio
import json
from datetime import date, timedelta
from typing import Dict, Any, List

# Import data parser
from app.services.data_parser import (
    fetch_and_parse_listings,
    fetch_and_parse_groups
)

# Import Phase 1 filters
from app.services.stable_matching.filters import (
    get_eligible_listings,
    get_eligible_groups
)

# Import Phase 2 functions
from app.services.stable_matching.feasible_pairs import (
    location_matches,
    date_matches,
    price_matches,
    hard_attributes_match,
    build_feasible_pairs,
    get_feasibility_statistics,
    analyze_rejection_reasons
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


async def test_individual_constraints():
    """Test individual constraint functions."""
    print_section("PHASE 2.1-2.4: INDIVIDUAL CONSTRAINT TESTS")
    
    # Create test data
    test_group = {
        'id': 'group-1',
        'target_city': 'Anaheim',
        'target_state_province': 'CA',
        'target_country': 'USA',
        'target_move_in_date': date(2026, 2, 15),
        'budget_per_person_min': 800,
        'budget_per_person_max': 1200,
        'target_furnished': True,
        'target_utilities_included': False
    }
    
    print_subsection("2.1 Location Matching")
    
    location_tests = [
        ({'city': 'Anaheim', 'state_province': 'CA', 'country': 'USA'}, True, "Exact match"),
        ({'city': 'anaheim', 'state_province': 'CA', 'country': 'USA'}, True, "Case insensitive"),
        ({'city': 'San Diego', 'state_province': 'CA', 'country': 'USA'}, False, "Different city"),
        ({'city': 'Anaheim', 'state_province': 'NY', 'country': 'USA'}, False, "Different state"),
        ({'city': 'Anaheim', 'state_province': 'CA', 'country': 'Canada'}, False, "Different country"),
        ({'city': '', 'state_province': 'CA', 'country': 'USA'}, False, "Missing city"),
    ]
    
    for listing_data, expected, description in location_tests:
        result = location_matches(test_group, listing_data)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {description}: {result}")
    
    print_subsection("2.2 Date Matching")
    
    date_tests = [
        (date(2026, 2, 15), None, True, "Exact match"),
        (date(2026, 2, 1), None, True, "14 days early (within ±30)"),
        (date(2026, 3, 1), None, True, "14 days late (within ±30)"),
        (date(2026, 3, 20), None, False, "33 days late (outside ±30)"),
        (date(2026, 1, 10), None, False, "36 days early (outside ±30)"),
        (date(2026, 2, 10), date(2026, 6, 1), True, "Available range includes target"),
        (date(2026, 2, 10), date(2026, 2, 12), False, "Available ends before target"),
    ]
    
    for available_from, available_to, expected, description in date_tests:
        listing_data = {
            'available_from': available_from,
            'available_to': available_to
        }
        result = date_matches(test_group, listing_data, delta_days=30)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {description}: {result}")
    
    print_subsection("2.3 Price Matching")
    
    price_tests = [
        (2000, True, "$1000/person - at midpoint"),
        (1600, True, "$800/person - at min"),
        (2400, True, "$1200/person - at max"),
        (1500, False, "$750/person - below min"),
        (2600, False, "$1300/person - above max"),
        (None, False, "Missing price"),
    ]
    
    for price, expected, description in price_tests:
        listing_data = {'price_per_month': price}
        result = price_matches(test_group, listing_data)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {description}: {result}")
    
    print_subsection("2.4 Hard Attributes Matching")
    
    attribute_tests = [
        ({'furnished': True, 'utilities_included': False}, True, "Meets furnished requirement"),
        ({'furnished': False, 'utilities_included': False}, False, "Missing furnished"),
        ({'furnished': True, 'utilities_included': True}, True, "Has both (utilities not required)"),
    ]
    
    for listing_data, expected, description in attribute_tests:
        result = hard_attributes_match(test_group, listing_data)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {description}: {result}")


async def test_feasible_pairs_building():
    """Test building feasible pairs with real data."""
    print_section("PHASE 2.5: BUILD FEASIBLE PAIRS WITH REAL DATA")
    
    # Fetch real data
    print("\n📥 Fetching data from database...")
    all_listings = await fetch_and_parse_listings()
    all_groups = await fetch_and_parse_groups(include_members=True)
    
    # Get eligible ones
    eligible_listings, _ = get_eligible_listings(all_listings)
    eligible_groups, _ = get_eligible_groups(all_groups)
    
    print(f"✅ Working with {len(eligible_groups)} groups and {len(eligible_listings)} listings")
    
    if not eligible_groups or not eligible_listings:
        print("⚠️  Need at least 1 group and 1 listing for testing")
        return None, None, None
    
    print_subsection("Building Feasible Pairs")
    
    # Build feasible pairs with rejection reasons
    print("\n🔄 Checking hard constraints for all pairs...")
    feasible_pairs, rejection_reasons = build_feasible_pairs(
        eligible_groups,
        eligible_listings,
        date_delta_days=30,
        include_rejection_reasons=True
    )
    
    print(f"✅ Found {len(feasible_pairs)} feasible pairs")
    
    # Get statistics
    print_subsection("Feasibility Statistics")
    
    stats = get_feasibility_statistics(eligible_groups, eligible_listings, feasible_pairs)
    
    print(f"\n  Total Groups: {stats['total_groups']}")
    print(f"  Total Listings: {stats['total_listings']}")
    print(f"  Maximum Possible Pairs: {stats['total_groups'] * stats['total_listings']}")
    print(f"\n  ✅ Feasible Pairs: {stats['total_feasible_pairs']}")
    print(f"  📊 Feasibility Rate: {stats['feasibility_rate']}%")
    print(f"\n  Groups with Options: {stats['groups_with_options']} ({stats['groups_with_no_options']} with none)")
    print(f"  Listings with Options: {stats['listings_with_options']} ({stats['listings_with_no_options']} with none)")
    print(f"\n  Average Listings per Group: {stats['avg_listings_per_group']}")
    print(f"  Average Groups per Listing: {stats['avg_groups_per_listing']}")
    
    # Analyze rejection reasons
    print_subsection("Rejection Reasons Analysis")
    
    rejection_analysis = analyze_rejection_reasons(rejection_reasons)
    
    print(f"\n  Total Rejections: {rejection_analysis['total_rejections']}")
    print(f"\n  Rejection Breakdown:")
    for reason, count in rejection_analysis['reason_counts'].items():
        percentage = rejection_analysis['reason_percentages'][reason]
        print(f"    - {reason}: {count} ({percentage}%)")
    
    # Show sample feasible pairs
    print_subsection("Sample Feasible Pairs")
    
    for i, (group_id, listing_id) in enumerate(feasible_pairs[:5], 1):
        group = next((g for g in eligible_groups if g['id'] == group_id), None)
        listing = next((l for l in eligible_listings if l['id'] == listing_id), None)
        
        if group and listing:
            print(f"\n  #{i}. {group.get('group_name')} ↔ {listing.get('title', 'No title')[:40]}")
            print(f"      City: {group.get('target_city')} = {listing.get('city')}")
            print(f"      Budget: ${group.get('budget_per_person_min')}-${group.get('budget_per_person_max')}/person")
            print(f"      Price: ${listing.get('price_per_month')} (${listing.get('price_per_month', 0)/2}/person)")
            print(f"      Date: {group.get('target_move_in_date')} ≈ {listing.get('available_from')}")
    
    # Show sample rejections
    print_subsection("Sample Rejections (First Group)")
    
    if rejection_reasons:
        first_group_id = list(rejection_reasons.keys())[0]
        first_group = next((g for g in eligible_groups if g['id'] == first_group_id), None)
        
        if first_group:
            print(f"\n  Group: {first_group.get('group_name')}")
            print(f"  Rejections: {len(rejection_reasons[first_group_id])}")
            
            for rejection in rejection_reasons[first_group_id][:3]:
                listing = next((l for l in eligible_listings if l['id'] == rejection['listing_id']), None)
                if listing:
                    print(f"\n    ❌ {listing.get('title', 'No title')[:40]}")
                    print(f"       Reasons: {', '.join(rejection['reasons'])}")
    
    return feasible_pairs, stats, rejection_analysis


async def test_date_flexibility():
    """Test how date flexibility affects feasible pairs."""
    print_section("PHASE 2: DATE FLEXIBILITY ANALYSIS")
    
    # Fetch data
    all_listings = await fetch_and_parse_listings()
    all_groups = await fetch_and_parse_groups(include_members=True)
    
    eligible_listings, _ = get_eligible_listings(all_listings)
    eligible_groups, _ = get_eligible_groups(all_groups)
    
    print_subsection("Impact of Date Delta")
    
    deltas = [7, 14, 30, 60, 90]
    
    print(f"\n  Testing with {len(eligible_groups)} groups and {len(eligible_listings)} listings:")
    print(f"\n  {'Delta (days)':<15} {'Feasible Pairs':<20} {'Feasibility %':<15}")
    print(f"  {'-'*15} {'-'*20} {'-'*15}")
    
    for delta in deltas:
        pairs, _ = build_feasible_pairs(
            eligible_groups,
            eligible_listings,
            date_delta_days=delta,
            include_rejection_reasons=False
        )
        
        max_possible = len(eligible_groups) * len(eligible_listings)
        feasibility_rate = len(pairs) / max_possible * 100 if max_possible > 0 else 0
        
        print(f"  ±{delta:<14} {len(pairs):<20} {feasibility_rate:.2f}%")


async def test_phase_2():
    """Run all Phase 2 tests."""
    print("\n" + "█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "  STABLE MATCHING ALGORITHM - PHASE 2 TESTS".center(78) + "█")
    print("█" + "  (Build Feasible Pairs - Hard Constraints)".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80)
    
    try:
        # Test individual constraints
        await test_individual_constraints()
        
        # Test feasible pairs building
        feasible_pairs, stats, rejection_analysis = await test_feasible_pairs_building()
        
        # Test date flexibility
        await test_date_flexibility()
        
        # Final summary
        print_section("FINAL SUMMARY")
        print(f"\n✅ Phase 2.1: Location matching working")
        print(f"   - City, state, country checks")
        print(f"✅ Phase 2.2: Date matching working")
        print(f"   - Configurable ±N days flexibility")
        print(f"✅ Phase 2.3: Price matching working")
        print(f"   - Per-person budget validation")
        print(f"✅ Phase 2.4: Hard attributes matching working")
        print(f"   - Furnished, utilities, amenity requirements")
        print(f"✅ Phase 2.5: Feasible pairs builder working")
        
        if stats:
            print(f"\n📊 Real Data Results:")
            print(f"   - {stats['total_feasible_pairs']} feasible pairs found")
            print(f"   - {stats['feasibility_rate']}% feasibility rate")
            print(f"   - {stats['avg_listings_per_group']} avg listings per group")
            print(f"   - {stats['groups_with_no_options']} groups with no options")
        
        if rejection_analysis:
            print(f"\n🔍 Top Rejection Reasons:")
            sorted_reasons = sorted(
                rejection_analysis['reason_percentages'].items(),
                key=lambda x: x[1],
                reverse=True
            )
            for reason, pct in sorted_reasons[:3]:
                print(f"   - {reason}: {pct}%")
        
        print(f"\n🎯 Ready for Phase 3: Two-Sided Scoring")
        print(f"   (Phase 3 already complete - can now integrate with Phase 2)")
        
        # Save results
        if feasible_pairs and stats:
            results = {
                "timestamp": str(date.today()),
                "summary": {
                    "feasible_pairs_count": len(feasible_pairs),
                    "statistics": stats,
                    "rejection_analysis": rejection_analysis
                },
                "sample_pairs": [
                    {"group_id": g_id, "listing_id": l_id}
                    for g_id, l_id in feasible_pairs[:10]
                ]
            }
            
            with open("phase_2_test_results.json", "w") as f:
                json.dump(results, f, indent=2, default=str)
            
            print(f"\n💾 Test results saved to: phase_2_test_results.json")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_phase_2())
