"""
Test Suite for Phase 4: Deferred Acceptance Algorithm

This script tests the core matching algorithm with both synthetic
and real data from the Supabase database.

Test Cases:
1. Simple 2x2 matching (2 groups, 2 listings)
2. Unbalanced matching (more groups than listings)
3. Unbalanced matching (more listings than groups)
4. Stability verification
5. Real data matching (if feasible pairs exist)

Run with:
    cd /Users/yousefmaher/Padly/backend
    python -m app.scripts.test_stable_matching_phase4
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
    run_deferred_acceptance,
    DeferredAcceptanceEngine,
    MatchResult,
    DiagnosticMetrics
)


# ============================================================================
# TEST DATA GENERATORS
# ============================================================================

def generate_simple_preference_lists() -> Dict:
    """
    Generate a simple 2x2 test case:
    - 2 groups (G1, G2)
    - 2 listings (L1, L2)
    
    Preferences:
    - G1: L1 (900) > L2 (700)
    - G2: L2 (850) > L1 (600)
    - L1: G1 (800) > G2 (650)
    - L2: G2 (900) > G1 (750)
    
    Expected stable matching: (G1, L1), (G2, L2)
    """
    return {
        'group_preferences': {
            'G1': [
                ('L1', 900.0, 1),  # (listing_id, score, rank)
                ('L2', 700.0, 2)
            ],
            'G2': [
                ('L2', 850.0, 1),
                ('L1', 600.0, 2)
            ]
        },
        'listing_preferences': {
            'L1': [
                ('G1', 800.0, 1),  # (group_id, score, rank)
                ('G2', 650.0, 2)
            ],
            'L2': [
                ('G2', 900.0, 1),
                ('G1', 750.0, 2)
            ]
        },
        'metadata': {
            'city': 'TestCity',
            'date_window_start': '2025-01-01',
            'date_window_end': '2025-03-01',
            'groups': ['G1', 'G2'],
            'listings': ['L1', 'L2'],
            'feasible_pairs': 4
        }
    }


def generate_unbalanced_groups() -> Dict:
    """
    Generate 3 groups competing for 2 listings
    
    Groups: G1, G2, G3
    Listings: L1, L2
    
    Preferences:
    - G1: L1 (950) > L2 (800)
    - G2: L1 (900) > L2 (750)
    - G3: L2 (850) > L1 (700)
    - L1: G1 (900) > G2 (850) > G3 (600)
    - L2: G3 (900) > G1 (800) > G2 (700)
    
    Expected: (G1, L1), (G3, L2), G2 unmatched
    """
    return {
        'group_preferences': {
            'G1': [('L1', 950.0, 1), ('L2', 800.0, 2)],
            'G2': [('L1', 900.0, 1), ('L2', 750.0, 2)],
            'G3': [('L2', 850.0, 1), ('L1', 700.0, 2)]
        },
        'listing_preferences': {
            'L1': [('G1', 900.0, 1), ('G2', 850.0, 2), ('G3', 600.0, 3)],
            'L2': [('G3', 900.0, 1), ('G1', 800.0, 2), ('G2', 700.0, 3)]
        },
        'metadata': {
            'city': 'TestCity',
            'date_window_start': '2025-01-01',
            'date_window_end': '2025-03-01',
            'groups': ['G1', 'G2', 'G3'],
            'listings': ['L1', 'L2'],
            'feasible_pairs': 6
        }
    }


def generate_unbalanced_listings() -> Dict:
    """
    Generate 2 groups competing for 3 listings
    
    Groups: G1, G2
    Listings: L1, L2, L3
    
    Expected: 2 matches, 1 listing unmatched
    """
    return {
        'group_preferences': {
            'G1': [('L1', 950.0, 1), ('L2', 850.0, 2), ('L3', 750.0, 3)],
            'G2': [('L2', 900.0, 1), ('L3', 800.0, 2), ('L1', 700.0, 3)]
        },
        'listing_preferences': {
            'L1': [('G1', 900.0, 1), ('G2', 750.0, 2)],
            'L2': [('G2', 850.0, 1), ('G1', 800.0, 2)],
            'L3': [('G1', 700.0, 1), ('G2', 650.0, 2)]
        },
        'metadata': {
            'city': 'TestCity',
            'date_window_start': '2025-01-01',
            'date_window_end': '2025-03-01',
            'groups': ['G1', 'G2'],
            'listings': ['L1', 'L2', 'L3'],
            'feasible_pairs': 6
        }
    }


def generate_blocking_pair_test() -> Dict:
    """
    Generate a case where naive matching would create blocking pair
    
    Groups: G1, G2
    Listings: L1, L2
    
    Naive pairing: (G1, L1), (G2, L2)
    But this is unstable because G2 and L1 prefer each other!
    
    Preferences:
    - G1: L1 (900) > L2 (800)
    - G2: L1 (950) > L2 (850)  # G2 REALLY wants L1
    - L1: G2 (900) > G1 (850)  # L1 prefers G2 over G1
    - L2: G1 (800) > G2 (750)
    
    Correct stable matching: (G2, L1), (G1, L2)
    """
    return {
        'group_preferences': {
            'G1': [('L1', 900.0, 1), ('L2', 800.0, 2)],
            'G2': [('L1', 950.0, 1), ('L2', 850.0, 2)]
        },
        'listing_preferences': {
            'L1': [('G2', 900.0, 1), ('G1', 850.0, 2)],
            'L2': [('G1', 800.0, 1), ('G2', 750.0, 2)]
        },
        'metadata': {
            'city': 'TestCity',
            'date_window_start': '2025-01-01',
            'date_window_end': '2025-03-01',
            'groups': ['G1', 'G2'],
            'listings': ['L1', 'L2'],
            'feasible_pairs': 4
        }
    }


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_simple_matching():
    """Test 1: Simple 2x2 balanced matching"""
    print("\n" + "="*80)
    print("TEST 1: Simple 2x2 Balanced Matching")
    print("="*80)
    
    prefs = generate_simple_preference_lists()
    
    print("\n📋 Input Preferences:")
    print(f"  Groups: {prefs['metadata']['groups']}")
    print(f"  Listings: {prefs['metadata']['listings']}")
    print(f"  Feasible pairs: {prefs['metadata']['feasible_pairs']}")
    
    matches, diagnostics = run_deferred_acceptance(prefs)
    
    print(f"\n✅ Matching Results:")
    print(f"  Matches created: {len(matches)}")
    print(f"  Iterations: {diagnostics.iterations}")
    print(f"  Proposals sent: {diagnostics.proposals_sent}")
    print(f"  Proposals rejected: {diagnostics.proposals_rejected}")
    print(f"  Stable: {diagnostics.is_stable}")
    print(f"  Quality score: {diagnostics.match_quality_score:.2f}/100")
    
    print(f"\n📊 Match Details:")
    for match in matches:
        print(f"  {match.group_id} ↔ {match.listing_id}")
        print(f"    Group score: {match.group_score:.1f} (rank {match.group_rank})")
        print(f"    Listing score: {match.listing_score:.1f} (rank {match.listing_rank})")
    
    # Verify expected outcome
    expected = {('G1', 'L1'), ('G2', 'L2')}
    actual = {(m.group_id, m.listing_id) for m in matches}
    
    if actual == expected:
        print(f"\n✅ TEST PASSED: Got expected stable matching!")
        return True
    else:
        print(f"\n❌ TEST FAILED: Expected {expected}, got {actual}")
        return False


def test_unbalanced_groups():
    """Test 2: More groups than listings (3 groups, 2 listings)"""
    print("\n" + "="*80)
    print("TEST 2: Unbalanced - More Groups (3 groups, 2 listings)")
    print("="*80)
    
    prefs = generate_unbalanced_groups()
    
    print("\n📋 Input:")
    print(f"  Groups: {len(prefs['group_preferences'])} (G1, G2, G3)")
    print(f"  Listings: {len(prefs['listing_preferences'])} (L1, L2)")
    
    matches, diagnostics = run_deferred_acceptance(prefs)
    
    print(f"\n✅ Results:")
    print(f"  Matched: {len(matches)}")
    print(f"  Unmatched groups: {diagnostics.unmatched_groups}")
    print(f"  Iterations: {diagnostics.iterations}")
    print(f"  Stable: {diagnostics.is_stable}")
    
    for match in matches:
        print(f"  {match.group_id} ↔ {match.listing_id} (ranks: {match.group_rank}, {match.listing_rank})")
    
    # Verify: should have exactly 2 matches
    if len(matches) == 2 and diagnostics.is_stable:
        print(f"\n✅ TEST PASSED: 2 stable matches with 1 unmatched group")
        return True
    else:
        print(f"\n❌ TEST FAILED")
        return False


def test_unbalanced_listings():
    """Test 3: More listings than groups (2 groups, 3 listings)"""
    print("\n" + "="*80)
    print("TEST 3: Unbalanced - More Listings (2 groups, 3 listings)")
    print("="*80)
    
    prefs = generate_unbalanced_listings()
    
    print("\n📋 Input:")
    print(f"  Groups: {len(prefs['group_preferences'])} (G1, G2)")
    print(f"  Listings: {len(prefs['listing_preferences'])} (L1, L2, L3)")
    
    matches, diagnostics = run_deferred_acceptance(prefs)
    
    print(f"\n✅ Results:")
    print(f"  Matched: {len(matches)}")
    print(f"  Unmatched listings: {diagnostics.unmatched_listings}")
    print(f"  Iterations: {diagnostics.iterations}")
    print(f"  Stable: {diagnostics.is_stable}")
    
    for match in matches:
        print(f"  {match.group_id} ↔ {match.listing_id} (ranks: {match.group_rank}, {match.listing_rank})")
    
    # Verify: should have exactly 2 matches
    if len(matches) == 2 and diagnostics.is_stable:
        print(f"\n✅ TEST PASSED: 2 stable matches with 1 unmatched listing")
        return True
    else:
        print(f"\n❌ TEST FAILED")
        return False


def test_blocking_pair_avoidance():
    """Test 4: Verify algorithm avoids blocking pairs"""
    print("\n" + "="*80)
    print("TEST 4: Blocking Pair Avoidance")
    print("="*80)
    
    prefs = generate_blocking_pair_test()
    
    print("\n📋 Scenario:")
    print("  G1 prefers: L1 > L2")
    print("  G2 prefers: L1 > L2  (G2 really wants L1!)")
    print("  L1 prefers: G2 > G1  (L1 prefers G2!)")
    print("  L2 prefers: G1 > G2")
    print("\n  ⚠️  Naive matching (G1,L1), (G2,L2) would be UNSTABLE")
    print("      because G2 and L1 both prefer each other!")
    
    matches, diagnostics = run_deferred_acceptance(prefs)
    
    print(f"\n✅ Algorithm Result:")
    for match in matches:
        print(f"  {match.group_id} ↔ {match.listing_id}")
    
    print(f"\n  Stable: {diagnostics.is_stable}")
    print(f"  Iterations: {diagnostics.iterations}")
    
    # Expected stable matching: (G2, L1), (G1, L2)
    expected = {('G2', 'L1'), ('G1', 'L2')}
    actual = {(m.group_id, m.listing_id) for m in matches}
    
    if actual == expected and diagnostics.is_stable:
        print(f"\n✅ TEST PASSED: Algorithm correctly found stable matching!")
        print(f"   (G2, L1) and (G1, L2) - no blocking pairs!")
        return True
    else:
        print(f"\n❌ TEST FAILED: Expected {expected}, got {actual}")
        return False


def test_empty_preferences():
    """Test 5: Handle empty preference lists gracefully"""
    print("\n" + "="*80)
    print("TEST 5: Empty Preference Lists")
    print("="*80)
    
    prefs = {
        'group_preferences': {},
        'listing_preferences': {},
        'metadata': {
            'city': 'TestCity',
            'date_window_start': '2025-01-01',
            'date_window_end': '2025-03-01',
            'groups': [],
            'listings': [],
            'feasible_pairs': 0
        }
    }
    
    matches, diagnostics = run_deferred_acceptance(prefs)
    
    print(f"\n✅ Results:")
    print(f"  Matches: {len(matches)}")
    print(f"  Stable: {diagnostics.is_stable}")
    
    if len(matches) == 0 and diagnostics.is_stable:
        print(f"\n✅ TEST PASSED: Handled empty input correctly")
        return True
    else:
        print(f"\n❌ TEST FAILED")
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all Phase 4 tests"""
    print("\n" + "🧪"*40)
    print("PHASE 4 TEST SUITE: DEFERRED ACCEPTANCE ALGORITHM")
    print("🧪"*40)
    
    results = []
    
    # Run tests
    results.append(("Simple 2x2 Matching", test_simple_matching()))
    results.append(("Unbalanced Groups (3v2)", test_unbalanced_groups()))
    results.append(("Unbalanced Listings (2v3)", test_unbalanced_listings()))
    results.append(("Blocking Pair Avoidance", test_blocking_pair_avoidance()))
    results.append(("Empty Preferences", test_empty_preferences()))
    
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
        'test_suite': 'Phase 4 - Deferred Acceptance Algorithm',
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
    
    output_file = 'phase_4_test_results.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"📄 Test results saved to: {output_file}")
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
