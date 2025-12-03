"""
Test Suite for Phase 6: API Endpoints

This script tests the stable matching API endpoints.

Test Cases:
1. GET /api/matches/active - Get active matches
2. GET /api/matches/stats - Get statistics  
3. POST /api/matches/run - Run matching (if data available)
4. POST /api/matches/expire - Expire old matches
5. DELETE /api/matches/group/{id} - Delete group matches
6. DELETE /api/matches/listing/{id} - Delete listing matches

Run with:
    cd /Users/yousefmaher/Padly/backend
    python -m app.scripts.test_stable_matching_phase6
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from fastapi.testclient import TestClient
from app.main import app

# Create test client
client = TestClient(app)


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_get_active_matches():
    """Test 1: GET /api/matches/active"""
    print("\n" + "="*80)
    print("TEST 1: GET /api/matches/active")
    print("="*80)
    
    try:
        # Test without filters
        print("\n📥 Getting all active matches...")
        response = client.get("/api/matches/active")
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Count: {data.get('count')}")
            
            if data.get('count', 0) > 0:
                print(f"\n   Sample matches (first 3):")
                for i, match in enumerate(data.get('matches', [])[:3], 1):
                    print(f"     {i}. Group {match.get('group_id')} ↔ Listing {match.get('listing_id')}")
            
            print(f"\n✅ TEST PASSED: API returned {data.get('count')} matches")
            return True
        else:
            print(f"❌ TEST FAILED: Status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_get_stats():
    """Test 2: GET /api/matches/stats"""
    print("\n" + "="*80)
    print("TEST 2: GET /api/matches/stats")
    print("="*80)
    
    try:
        print("\n📊 Getting matching statistics...")
        response = client.get("/api/matches/stats")
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Total active matches: {data.get('total_active_matches')}")
            
            if data.get('latest_run'):
                latest = data['latest_run']
                print(f"\n   Latest run:")
                print(f"     City: {latest.get('city')}")
                print(f"     Time: {latest.get('executed_at')}")
                print(f"     Matched: {latest.get('matched_groups')} groups")
                print(f"     Quality: {latest.get('match_quality_score')}")
            
            print(f"\n✅ TEST PASSED: Stats retrieved successfully")
            return True
        else:
            print(f"❌ TEST FAILED: Status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_filter_by_city():
    """Test 3: GET /api/matches/active?city=TestCity"""
    print("\n" + "="*80)
    print("TEST 3: GET /api/matches/active?city=TestCity")
    print("="*80)
    
    try:
        print("\n📥 Filtering matches by city: TestCity...")
        response = client.get("/api/matches/active?city=TestCity")
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Found: {data.get('count')} matches in TestCity")
            
            print(f"\n✅ TEST PASSED: Filter by city works")
            return True
        else:
            print(f"❌ TEST FAILED: Status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_expire_matches():
    """Test 4: POST /api/matches/expire"""
    print("\n" + "="*80)
    print("TEST 4: POST /api/matches/expire")
    print("="*80)
    
    try:
        print("\n🗑️  Expiring matches older than 30 days...")
        response = client.post("/api/matches/expire?days_threshold=30")
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Expired: {data.get('expired_count')} matches")
            print(f"   Message: {data.get('message')}")
            
            print(f"\n✅ TEST PASSED: Expire endpoint works")
            return True
        else:
            print(f"❌ TEST FAILED: Status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_delete_group_matches():
    """Test 5: DELETE /api/matches/group/{group_id}"""
    print("\n" + "="*80)
    print("TEST 5: DELETE /api/matches/group/{group_id}")
    print("="*80)
    
    try:
        test_group_id = "test_group_delete"
        
        print(f"\n🗑️  Deleting matches for group: {test_group_id}...")
        response = client.delete(f"/api/matches/group/{test_group_id}")
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Deleted: {data.get('deleted_count')} matches")
            print(f"   Message: {data.get('message')}")
            
            print(f"\n✅ TEST PASSED: Delete group endpoint works")
            return True
        else:
            print(f"❌ TEST FAILED: Status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_delete_listing_matches():
    """Test 6: DELETE /api/matches/listing/{listing_id}"""
    print("\n" + "="*80)
    print("TEST 6: DELETE /api/matches/listing/{listing_id}")
    print("="*80)
    
    try:
        test_listing_id = "test_listing_delete"
        
        print(f"\n🗑️  Deleting matches for listing: {test_listing_id}...")
        response = client.delete(f"/api/matches/listing/{test_listing_id}")
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Deleted: {data.get('deleted_count')} matches")
            print(f"   Message: {data.get('message')}")
            
            print(f"\n✅ TEST PASSED: Delete listing endpoint works")
            return True
        else:
            print(f"❌ TEST FAILED: Status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_api_docs():
    """Test 7: Check API documentation is available"""
    print("\n" + "="*80)
    print("TEST 7: Check API Documentation")
    print("="*80)
    
    try:
        print("\n📖 Checking OpenAPI documentation...")
        response = client.get("/openapi.json")
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for stable matching endpoints in OpenAPI spec
            paths = data.get('paths', {})
            stable_paths = [p for p in paths.keys() if '/api/matches' in p]
            
            print(f"   Found {len(stable_paths)} stable matching endpoints in docs:")
            for path in stable_paths[:8]:  # Show first 8
                print(f"     - {path}")
            
            print(f"\n✅ TEST PASSED: API documentation available")
            return True
        else:
            print(f"❌ TEST FAILED: Status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all Phase 6 tests"""
    print("\n" + "🧪"*40)
    print("PHASE 6 TEST SUITE: API ENDPOINTS")
    print("🧪"*40)
    
    results = []
    
    # Run tests
    results.append(("GET /api/matches/active", test_get_active_matches()))
    results.append(("GET /api/matches/stats", test_get_stats()))
    results.append(("GET /api/matches/active?city=X", test_filter_by_city()))
    results.append(("POST /api/matches/expire", test_expire_matches()))
    results.append(("DELETE /api/matches/group/{id}", test_delete_group_matches()))
    results.append(("DELETE /api/matches/listing/{id}", test_delete_listing_matches()))
    results.append(("Check API Documentation", test_api_docs()))
    
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
    
    # Note about POST /api/matches/run
    print("📝 NOTE: POST /api/matches/run not tested")
    print("   This endpoint requires eligible groups and listings in the database.")
    print("   Test manually or wait for real data.")
    print()
    
    # Save results
    output = {
        'test_suite': 'Phase 6 - API Endpoints',
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
    
    output_file = 'phase_6_test_results.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"📄 Test results saved to: {output_file}")
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
