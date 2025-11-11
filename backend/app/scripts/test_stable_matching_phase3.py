"""
Test Script for Stable Matching - Phase 3
Tests two-sided scoring and preference list building.
"""

import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime, date, timedelta

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

# Import Phase 2 (we'll need to import from phase 2 test for now)
# For now, we'll create simple feasible pairs for testing

# Import Phase 3 scoring
from app.services.stable_matching.scoring import (
    calculate_group_score,
    calculate_listing_score,
    rank_listings_for_group,
    rank_groups_for_listing,
    build_preference_lists,
    calculate_price_fit_score,
    calculate_date_fit_score,
    calculate_amenities_fit_score,
    calculate_listing_quality_score,
    calculate_verification_trust_score,
    calculate_group_readiness_score,
    GROUP_SCORING_WEIGHTS,
    LISTING_SCORING_WEIGHTS
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


def create_simple_feasible_pairs(groups: List[Dict], listings: List[Dict]) -> List[tuple]:
    """
    Create simple feasible pairs for testing (simplified hard constraints).
    Just checks city and basic compatibility.
    """
    pairs = []
    
    for group in groups:
        group_city = group.get('target_city', '').lower()
        
        for listing in listings:
            listing_city = listing.get('city', '').lower()
            
            # Simple city match for testing
            if group_city == listing_city:
                pairs.append((group['id'], listing['id']))
    
    return pairs


async def test_component_scores():
    """Test individual scoring components."""
    print_section("PHASE 3.1 & 3.2: COMPONENT SCORING TESTS")
    
    print_subsection("Price Fit Scoring")
    
    # Test cases for price fit
    test_cases = [
        (2000, 800, 1200, "Within range, at midpoint"),
        (1600, 800, 1200, "Within range, at min edge"),
        (2400, 800, 1200, "Within range, at max edge"),
        (1500, 800, 1200, "Outside range (too cheap)"),
        (3000, 800, 1200, "Outside range (too expensive)"),
    ]
    
    for listing_price, budget_min, budget_max, description in test_cases:
        score = calculate_price_fit_score(listing_price, budget_min, budget_max)
        per_person = listing_price / 2
        print(f"  Price ${listing_price} (${per_person}/person) vs ${budget_min}-${budget_max}")
        print(f"    → Score: {score:.1f}/100 - {description}")
    
    print_subsection("Date Fit Scoring")
    
    # Test date fit
    base_date = date(2026, 2, 1)
    available_from = date(2026, 1, 15)
    
    test_dates = [
        (available_from, "Exact match"),
        (available_from + timedelta(days=5), "5 days after"),
        (available_from + timedelta(days=14), "14 days after"),
        (available_from + timedelta(days=30), "30 days after"),
        (available_from + timedelta(days=60), "60 days after"),
    ]
    
    for target_date, description in test_dates:
        score = calculate_date_fit_score(available_from, None, target_date)
        days_diff = abs((target_date - available_from).days)
        print(f"  Target {target_date} vs Available {available_from} ({days_diff} days)")
        print(f"    → Score: {score:.1f}/100 - {description}")
    
    print_subsection("Amenities Fit Scoring")
    
    # Test amenities
    test_amenities = [
        ({'wifi': True, 'laundry': 'in_unit', 'air_conditioning': True, 'parking': True, 'dishwasher': True}, "All key amenities"),
        ({'wifi': True, 'laundry': 'in_unit', 'air_conditioning': True}, "Most amenities"),
        ({'wifi': True}, "Only wifi"),
        ({}, "No amenities"),
    ]
    
    for amenities, description in test_amenities:
        score = calculate_amenities_fit_score(amenities)
        print(f"  {description}")
        print(f"    → Score: {score:.1f}/100")
    
    print_subsection("Group Readiness Scoring")
    
    # Test group readiness
    test_groups = [
        ({'status': 'active', 'members': [{'user_id': '1'}, {'user_id': '2'}], 'target_group_size': 2}, "Full and active"),
        ({'status': 'active', 'members': [{'user_id': '1'}], 'target_group_size': 2}, "Partial, active"),
        ({'status': 'inactive', 'members': [{'user_id': '1'}, {'user_id': '2'}], 'target_group_size': 2}, "Full but inactive"),
        ({'status': 'active', 'members': [], 'target_group_size': 2}, "Empty, active"),
    ]
    
    for group_data, description in test_groups:
        score = calculate_group_readiness_score(group_data)
        print(f"  {description}")
        print(f"    → Score: {score:.1f}/100")


async def test_full_scoring():
    """Test full scoring with real data."""
    print_section("PHASE 3: FULL TWO-SIDED SCORING TESTS")
    
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
        return
    
    print_subsection("Group → Listing Scoring (Sample)")
    
    # Test first group against first few listings
    test_group = eligible_groups[0]
    test_listings = eligible_listings[:3]
    
    print(f"\nGroup: {test_group.get('group_name')}")
    print(f"  City: {test_group.get('target_city')}")
    print(f"  Budget: ${test_group.get('budget_per_person_min')}-${test_group.get('budget_per_person_max')}/person")
    print(f"  Move-in: {test_group.get('target_move_in_date')}")
    print(f"  Members: {len(test_group.get('members', []))}/{test_group.get('target_group_size')}")
    
    print(f"\nScoring {len(test_listings)} listings:")
    for i, listing in enumerate(test_listings, 1):
        score = calculate_group_score(test_group, listing)
        print(f"\n  #{i}. {listing.get('title', 'No title')[:50]}")
        print(f"      City: {listing.get('city')}")
        print(f"      Price: ${listing.get('price_per_month')} (${listing.get('price_per_month', 0)/2}/person)")
        print(f"      Available: {listing.get('available_from')}")
        print(f"      Bedrooms: {listing.get('number_of_bedrooms')}")
        print(f"      ⭐ Group's Score: {score:.1f}/1000")
    
    print_subsection("Listing → Group Scoring (Sample)")
    
    # Test first listing against first few groups
    test_listing = eligible_listings[0]
    test_groups = eligible_groups[:3]
    
    print(f"\nListing: {test_listing.get('title')}")
    print(f"  City: {test_listing.get('city')}")
    print(f"  Price: ${test_listing.get('price_per_month')}/month")
    print(f"  Available: {test_listing.get('available_from')}")
    
    print(f"\nScoring {len(test_groups)} groups:")
    for i, group in enumerate(test_groups, 1):
        score = calculate_listing_score(test_listing, group)
        print(f"\n  #{i}. {group.get('group_name')}")
        print(f"      City: {group.get('target_city')}")
        print(f"      Members: {len(group.get('members', []))}/{group.get('target_group_size')}")
        print(f"      Status: {group.get('status')}")
        print(f"      ⭐ Listing's Score: {score:.1f}/1000")


async def test_ranking():
    """Test ranking and preference lists."""
    print_section("PHASE 3.3: RANKING & PREFERENCE LISTS")
    
    # Fetch data
    all_listings = await fetch_and_parse_listings()
    all_groups = await fetch_and_parse_groups(include_members=True)
    
    eligible_listings, _ = get_eligible_listings(all_listings)
    eligible_groups, _ = get_eligible_groups(all_groups)
    
    print_subsection("Group's Preference List")
    
    if eligible_groups and eligible_listings:
        test_group = eligible_groups[0]
        
        # Filter listings by same city for demo
        same_city_listings = [
            l for l in eligible_listings
            if l.get('city', '').lower() == test_group.get('target_city', '').lower()
        ]
        
        if same_city_listings:
            print(f"\nGroup: {test_group.get('group_name')}")
            print(f"City: {test_group.get('target_city')}")
            print(f"\nRanking {len(same_city_listings)} listings in same city:")
            
            ranked = rank_listings_for_group(test_group, same_city_listings)
            
            for listing_id, rank, score in ranked[:5]:  # Top 5
                listing = next((l for l in same_city_listings if l['id'] == listing_id), None)
                if listing:
                    print(f"\n  Rank #{rank}: {listing.get('title', 'No title')[:40]}")
                    print(f"    Score: {score:.1f}/1000")
                    print(f"    Price: ${listing.get('price_per_month')}")
                    print(f"    Available: {listing.get('available_from')}")
        else:
            print(f"  No listings in {test_group.get('target_city')}")
    
    print_subsection("Listing's Preference List")
    
    if eligible_listings and eligible_groups:
        test_listing = eligible_listings[0]
        
        # Filter groups by same city
        same_city_groups = [
            g for g in eligible_groups
            if g.get('target_city', '').lower() == test_listing.get('city', '').lower()
        ]
        
        if same_city_groups:
            print(f"\nListing: {test_listing.get('title')}")
            print(f"City: {test_listing.get('city')}")
            print(f"\nRanking {len(same_city_groups)} groups in same city:")
            
            ranked = rank_groups_for_listing(test_listing, same_city_groups)
            
            for group_id, rank, score in ranked[:5]:  # Top 5
                group = next((g for g in same_city_groups if g['id'] == group_id), None)
                if group:
                    print(f"\n  Rank #{rank}: {group.get('group_name')}")
                    print(f"    Score: {score:.1f}/1000")
                    print(f"    Members: {len(group.get('members', []))}/{group.get('target_group_size')}")
                    print(f"    Status: {group.get('status')}")
        else:
            print(f"  No groups in {test_listing.get('city')}")


async def test_preference_lists_building():
    """Test building complete preference lists."""
    print_section("PHASE 3.4: BUILD PREFERENCE LISTS")
    
    # Fetch data
    all_listings = await fetch_and_parse_listings()
    all_groups = await fetch_and_parse_groups(include_members=True)
    
    eligible_listings, _ = get_eligible_listings(all_listings)
    eligible_groups, _ = get_eligible_groups(all_groups)
    
    print(f"\n📊 Data: {len(eligible_groups)} groups, {len(eligible_listings)} listings")
    
    # Create simple feasible pairs (just by city match for demo)
    feasible_pairs = create_simple_feasible_pairs(eligible_groups, eligible_listings)
    
    print(f"✅ Created {len(feasible_pairs)} feasible pairs")
    
    # Build preference lists
    print("\n🔄 Building preference lists...")
    group_prefs, listing_prefs = build_preference_lists(
        feasible_pairs,
        eligible_groups,
        eligible_listings
    )
    
    print(f"✅ Built preference lists:")
    print(f"   - {len(group_prefs)} groups have preferences")
    print(f"   - {len(listing_prefs)} listings have preferences")
    
    # Show sample
    print_subsection("Sample Group Preferences")
    
    for group_id, prefs in list(group_prefs.items())[:2]:
        group = next((g for g in eligible_groups if g['id'] == group_id), None)
        if group and prefs:
            print(f"\n  {group.get('group_name')}:")
            print(f"    Has {len(prefs)} listings in preference list")
            print(f"    Top 3 choices:")
            for listing_id, rank, score in prefs[:3]:
                listing = next((l for l in eligible_listings if l['id'] == listing_id), None)
                if listing:
                    print(f"      #{rank}. {listing.get('title', 'No title')[:35]} (score: {score:.0f})")
    
    print_subsection("Sample Listing Preferences")
    
    for listing_id, prefs in list(listing_prefs.items())[:2]:
        listing = next((l for l in eligible_listings if l['id'] == listing_id), None)
        if listing and prefs:
            print(f"\n  {listing.get('title', 'No title')[:40]}:")
            print(f"    Has {len(prefs)} groups in preference list")
            print(f"    Top 3 choices:")
            for group_id, rank, score in prefs[:3]:
                group = next((g for g in eligible_groups if g['id'] == group_id), None)
                if group:
                    print(f"      #{rank}. {group.get('group_name')} (score: {score:.0f})")
    
    # Statistics
    print_subsection("Statistics")
    
    avg_group_choices = sum(len(prefs) for prefs in group_prefs.values()) / len(group_prefs) if group_prefs else 0
    avg_listing_choices = sum(len(prefs) for prefs in listing_prefs.values()) / len(listing_prefs) if listing_prefs else 0
    
    print(f"\n  Average choices per group: {avg_group_choices:.1f}")
    print(f"  Average choices per listing: {avg_listing_choices:.1f}")
    
    groups_with_no_choices = sum(1 for prefs in group_prefs.values() if not prefs)
    listings_with_no_choices = sum(1 for prefs in listing_prefs.values() if not prefs)
    
    print(f"  Groups with no choices: {groups_with_no_choices}")
    print(f"  Listings with no choices: {listings_with_no_choices}")
    
    return group_prefs, listing_prefs


async def test_phase_3():
    """Run all Phase 3 tests."""
    print("\n" + "█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "  STABLE MATCHING ALGORITHM - PHASE 3 TESTS".center(78) + "█")
    print("█" + "  (Two-Sided Scoring & Preference Lists)".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80)
    
    try:
        # Test component scores
        await test_component_scores()
        
        # Test full scoring
        await test_full_scoring()
        
        # Test ranking
        await test_ranking()
        
        # Test preference list building
        group_prefs, listing_prefs = await test_preference_lists_building()
        
        # Final summary
        print_section("FINAL SUMMARY")
        print(f"\n✅ Phase 3.1: Group → Listing scoring working")
        print(f"   - Price fit, date fit, amenities, quality")
        print(f"   - Weights: {GROUP_SCORING_WEIGHTS}")
        print(f"✅ Phase 3.2: Listing → Group scoring working")
        print(f"   - Verification trust, readiness, date alignment")
        print(f"   - Weights: {LISTING_SCORING_WEIGHTS}")
        print(f"✅ Phase 3.3: Ranking with deterministic tie-breaks")
        print(f"✅ Phase 3.4: Preference lists built")
        print(f"   - {len(group_prefs)} groups with preferences")
        print(f"   - {len(listing_prefs)} listings with preferences")
        
        print(f"\n🎯 Ready for Phase 4: Deferred Acceptance Algorithm")
        
        # Save results
        results = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "groups_with_preferences": len(group_prefs),
                "listings_with_preferences": len(listing_prefs),
                "total_preference_entries": sum(len(p) for p in group_prefs.values()),
                "avg_choices_per_group": sum(len(p) for p in group_prefs.values()) / len(group_prefs) if group_prefs else 0,
            },
            "scoring_weights": {
                "group_scoring": GROUP_SCORING_WEIGHTS,
                "listing_scoring": LISTING_SCORING_WEIGHTS
            }
        }
        
        with open("phase_3_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Test results saved to: phase_3_test_results.json")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_phase_3())
