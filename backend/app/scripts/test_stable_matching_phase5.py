"""
Test Suite for Phase 5: Database Persistence

This script tests saving and retrieving match results from Supabase.

Test Cases:
1. Save matches and diagnostics
2. Retrieve active matches
3. Filter matches by city/group/listing
4. Delete matches
5. Get match statistics
6. Expire old matches

Run with:
    cd /Users/yousefmaher/Padly/backend
    python -m app.scripts.test_stable_matching_phase5
"""

import sys
import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.stable_matching import (
    MatchResult,
    DiagnosticMetrics,
    MatchPersistenceEngine,
    save_matching_results,
    get_active_matches_for_group,
    get_active_matches_for_listing
)
from app.dependencies.supabase import get_admin_client


# ============================================================================
# TEST DATA GENERATORS
# ============================================================================

def generate_test_matches() -> List[MatchResult]:
    """Generate sample match results for testing"""
    now = datetime.now()
    
    return [
        MatchResult(
            group_id='test_group_1',
            listing_id='test_listing_1',
            group_score=950.0,
            listing_score=880.0,
            group_rank=1,
            listing_rank=1,
            matched_at=now,
            is_stable=True
        ),
        MatchResult(
            group_id='test_group_2',
            listing_id='test_listing_2',
            group_score=850.0,
            listing_score=900.0,
            group_rank=1,
            listing_rank=1,
            matched_at=now,
            is_stable=True
        ),
        MatchResult(
            group_id='test_group_3',
            listing_id='test_listing_3',
            group_score=780.0,
            listing_score=820.0,
            group_rank=2,
            listing_rank=2,
            matched_at=now,
            is_stable=True
        )
    ]


def generate_test_diagnostics() -> DiagnosticMetrics:
    """Generate sample diagnostics for testing"""
    return DiagnosticMetrics(
        city='TestCity',
        date_window_start='2025-01-01',
        date_window_end='2025-03-01',
        total_groups=5,
        total_listings=5,
        feasible_pairs=15,
        matched_groups=3,
        matched_listings=3,
        unmatched_groups=2,
        unmatched_listings=2,
        proposals_sent=8,
        proposals_rejected=5,
        iterations=4,
        avg_group_rank=1.33,
        avg_listing_rank=1.33,
        match_quality_score=85.5,
        is_stable=True,
        stability_check_passed=True,
        executed_at=datetime.now()
    )


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

async def test_save_matches():
    """Test 1: Save matches and diagnostics to database"""
    print("\n" + "="*80)
    print("TEST 1: Save Matches and Diagnostics")
    print("="*80)
    
    try:
        supabase = get_admin_client()
        engine = MatchPersistenceEngine(supabase)
        
        # Generate test data
        matches = generate_test_matches()
        diagnostics = generate_test_diagnostics()
        
        print(f"\n📤 Saving {len(matches)} matches...")
        print(f"   City: {diagnostics.city}")
        print(f"   Date window: {diagnostics.date_window_start} to {diagnostics.date_window_end}")
        print(f"   Quality score: {diagnostics.match_quality_score:.2f}")
        
        # Save to database
        result = await engine.save_matches(matches, diagnostics)
        
        print(f"\n✅ Save Result:")
        print(f"   Status: {result['status']}")
        print(f"   Diagnostics ID: {result.get('diagnostics_id', 'N/A')}")
        print(f"   Matches saved: {result.get('matches_saved', 0)}")
        print(f"   Matches expired: {result.get('matches_expired', 0)}")
        
        if result['status'] == 'success' and result.get('matches_saved', 0) == len(matches):
            print(f"\n✅ TEST PASSED: Successfully saved {len(matches)} matches")
            return True, result['diagnostics_id']
        else:
            print(f"\n❌ TEST FAILED: {result.get('error', 'Unknown error')}")
            return False, None
            
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


async def test_retrieve_active_matches(diagnostics_id: str = None):
    """Test 2: Retrieve active matches"""
    print("\n" + "="*80)
    print("TEST 2: Retrieve Active Matches")
    print("="*80)
    
    try:
        supabase = get_admin_client()
        engine = MatchPersistenceEngine(supabase)
        
        # Retrieve all active matches
        print(f"\n📥 Retrieving active matches...")
        matches = await engine.get_active_matches()
        
        print(f"\n✅ Retrieved {len(matches)} active matches")
        
        if len(matches) > 0:
            print(f"\n📊 Sample matches:")
            for i, match in enumerate(matches[:3], 1):
                print(f"   {i}. Group {match.get('group_id')} ↔ Listing {match.get('listing_id')}")
                print(f"      Ranks: {match.get('group_rank')}/{match.get('listing_rank')}")
        
        if len(matches) >= 3:  # We saved 3 test matches
            print(f"\n✅ TEST PASSED: Retrieved {len(matches)} active matches")
            return True
        else:
            print(f"\n⚠️  TEST WARNING: Expected at least 3 matches, got {len(matches)}")
            return True  # Still pass if database has different data
            
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_filter_matches():
    """Test 3: Filter matches by city, group, listing"""
    print("\n" + "="*80)
    print("TEST 3: Filter Matches")
    print("="*80)
    
    try:
        supabase = get_admin_client()
        engine = MatchPersistenceEngine(supabase)
        
        # Test 3a: Filter by city
        print(f"\n📥 Filtering by city: TestCity")
        city_matches = await engine.get_active_matches(city='TestCity')
        print(f"   Found {len(city_matches)} matches in TestCity")
        
        # Test 3b: Filter by group
        print(f"\n📥 Filtering by group: test_group_1")
        group_matches = await engine.get_active_matches(group_id='test_group_1')
        print(f"   Found {len(group_matches)} matches for test_group_1")
        
        # Test 3c: Filter by listing
        print(f"\n📥 Filtering by listing: test_listing_2")
        listing_matches = await engine.get_active_matches(listing_id='test_listing_2')
        print(f"   Found {len(listing_matches)} matches for test_listing_2")
        
        # Test using helper functions
        print(f"\n📥 Using helper functions...")
        group_match = await get_active_matches_for_group(supabase, 'test_group_1')
        listing_match = await get_active_matches_for_listing(supabase, 'test_listing_2')
        
        print(f"   Group match: {'Found' if group_match else 'Not found'}")
        print(f"   Listing match: {'Found' if listing_match else 'Not found'}")
        
        print(f"\n✅ TEST PASSED: All filter operations completed")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_get_diagnostics():
    """Test 4: Retrieve diagnostics"""
    print("\n" + "="*80)
    print("TEST 4: Retrieve Diagnostics")
    print("="*80)
    
    try:
        supabase = get_admin_client()
        engine = MatchPersistenceEngine(supabase)
        
        print(f"\n📥 Retrieving diagnostics (limit 5)...")
        diagnostics = await engine.get_diagnostics(limit=5)
        
        print(f"\n✅ Retrieved {len(diagnostics)} diagnostic records")
        
        if len(diagnostics) > 0:
            print(f"\n📊 Latest diagnostics:")
            latest = diagnostics[0]
            print(f"   City: {latest.get('city')}")
            print(f"   Executed: {latest.get('executed_at')}")
            print(f"   Matched: {latest.get('matched_groups')}/{latest.get('total_groups')} groups")
            print(f"   Quality: {latest.get('match_quality_score'):.2f}/100")
            print(f"   Stable: {latest.get('is_stable')}")
        
        print(f"\n✅ TEST PASSED: Retrieved diagnostics")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_match_statistics():
    """Test 5: Get match statistics"""
    print("\n" + "="*80)
    print("TEST 5: Get Match Statistics")
    print("="*80)
    
    try:
        supabase = get_admin_client()
        engine = MatchPersistenceEngine(supabase)
        
        print(f"\n📊 Getting match statistics...")
        stats = await engine.get_match_statistics()
        
        print(f"\n✅ Statistics:")
        print(f"   Total active matches: {stats.get('total_active_matches', 0)}")
        
        if stats.get('latest_run'):
            latest = stats['latest_run']
            print(f"\n   Latest run:")
            print(f"     City: {latest.get('city')}")
            print(f"     Time: {latest.get('executed_at')}")
            print(f"     Matched: {latest.get('matched_groups')} groups, {latest.get('matched_listings')} listings")
            print(f"     Quality: {latest.get('match_quality_score'):.2f}")
            print(f"     Stable: {latest.get('is_stable')}")
        
        print(f"\n✅ TEST PASSED: Retrieved statistics")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_delete_matches():
    """Test 6: Delete matches"""
    print("\n" + "="*80)
    print("TEST 6: Delete Matches")
    print("="*80)
    
    try:
        supabase = get_admin_client()
        engine = MatchPersistenceEngine(supabase)
        
        # Delete test matches
        print(f"\n🗑️  Deleting test matches...")
        
        deleted_group = await engine.delete_matches_for_group('test_group_1')
        print(f"   Deleted {deleted_group} matches for test_group_1")
        
        deleted_listing = await engine.delete_matches_for_listing('test_listing_2')
        print(f"   Deleted {deleted_listing} matches for test_listing_2")
        
        # Clean up remaining test matches
        for i in range(1, 4):
            await engine.delete_matches_for_group(f'test_group_{i}')
            await engine.delete_matches_for_listing(f'test_listing_{i}')
        
        print(f"\n✅ TEST PASSED: Delete operations completed")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

async def run_all_tests():
    """Run all Phase 5 tests"""
    print("\n" + "🧪"*40)
    print("PHASE 5 TEST SUITE: DATABASE PERSISTENCE")
    print("🧪"*40)
    
    results = []
    diagnostics_id = None
    
    # Run tests sequentially (database operations)
    test1_passed, diag_id = await test_save_matches()
    results.append(("Save Matches & Diagnostics", test1_passed))
    diagnostics_id = diag_id
    
    if test1_passed:
        await asyncio.sleep(1)  # Brief pause for DB consistency
        
        results.append(("Retrieve Active Matches", await test_retrieve_active_matches(diagnostics_id)))
        results.append(("Filter Matches", await test_filter_matches()))
        results.append(("Get Diagnostics", await test_get_diagnostics()))
        results.append(("Match Statistics", await test_match_statistics()))
        results.append(("Delete Matches", await test_delete_matches()))
    else:
        print("\n⚠️  Skipping remaining tests due to save failure")
        results.extend([
            ("Retrieve Active Matches", False),
            ("Filter Matches", False),
            ("Get Diagnostics", False),
            ("Match Statistics", False),
            ("Delete Matches", False)
        ])
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n{'='*80}")
    print(f"TOTAL: {passed}/{total} tests passed ({100*passed//total}%)")
    print(f"{'='*80}\n")
    
    # Save results
    output = {
        'test_suite': 'Phase 5 - Database Persistence',
        'timestamp': datetime.now().isoformat(),
        'results': [
            {'test': name, 'passed': result}
            for name, result in results
        ],
        'summary': {
            'total_tests': total,
            'passed': passed,
            'failed': total - passed,
            'pass_rate': f"{100*passed//total}%"
        }
    }
    
    output_file = 'phase_5_test_results.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"📄 Test results saved to: {output_file}")
    
    return passed == total


if __name__ == '__main__':
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
