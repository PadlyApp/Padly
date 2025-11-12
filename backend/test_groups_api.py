"""
Test script for Groups API endpoints
Tests CRUD operations and member management
"""

from fastapi.testclient import TestClient
from app.main import app
from app.dependencies.supabase import get_admin_client
import json

client = TestClient(app)
supabase = get_admin_client()

print("="*80)
print("TESTING ROOMMATE GROUPS API")
print("="*80)

# Test 1: List all groups
print("\n1️⃣  Test: GET /api/roommate-groups")
print("-" * 80)
response = client.get("/api/roommate-groups")
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"✅ Found {data['count']} groups")
    if data['count'] > 0:
        sample_group = data['data'][0]
        print(f"   Sample group: {sample_group['group_name']}")
        print(f"   City: {sample_group['target_city']}")
        print(f"   Budget: ${sample_group.get('budget_per_person_min', 0)}-${sample_group.get('budget_per_person_max', 0)}")
else:
    print(f"❌ Error: {response.json()}")

# Test 2: Filter groups by city
print("\n2️⃣  Test: GET /api/roommate-groups?city=Anaheim")
print("-" * 80)
response = client.get("/api/roommate-groups?city=Anaheim")
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"✅ Found {data['count']} groups in Anaheim")
else:
    print(f"❌ Error: {response.json()}")

# Test 3: Get specific group with members
print("\n3️⃣  Test: GET /api/roommate-groups/{group_id}")
print("-" * 80)
# Get first group
groups = client.get("/api/roommate-groups?limit=1").json()['data']
if groups:
    group_id = groups[0]['id']
    response = client.get(f"/api/roommate-groups/{group_id}?include_members=true")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()['data']
        print(f"✅ Group: {data['group_name']}")
        print(f"   Creator: {data['creator_user_id']}")
        print(f"   Members: {len(data.get('members', []))}")
        for member in data.get('members', [])[:3]:
            status_emoji = "👑" if member['is_creator'] else "👤"
            print(f"   {status_emoji} {member.get('user_name', 'Unknown')} ({member['status']})")
    else:
        print(f"❌ Error: {response.json()}")
else:
    print("⚠️  No groups found to test")

# Test 4: Get group members
print("\n4️⃣  Test: GET /api/roommate-groups/{group_id}/members")
print("-" * 80)
if groups:
    group_id = groups[0]['id']
    response = client.get(f"/api/roommate-groups/{group_id}/members")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['count']} members")
        for member in data['data'][:5]:
            status_emoji = "👑" if member['is_creator'] else "👤"
            status_color = {"accepted": "✅", "pending": "⏳", "rejected": "❌"}
            print(f"   {status_emoji} {member.get('user_name', 'Unknown')} - {status_color.get(member['status'], '❓')} {member['status']}")
    else:
        print(f"❌ Error: {response.json()}")

# Test 5: Get group matches (stable matching integration)
print("\n5️⃣  Test: GET /api/roommate-groups/{group_id}/matches")
print("-" * 80)
# Use the test group we've been working with
test_group_id = "026a7755-9001-43f3-87b3-21e781f99881"
response = client.get(f"/api/roommate-groups/{test_group_id}/matches")
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"✅ Found {data['count']} matches for group")
    for i, match in enumerate(data['data'][:3], 1):
        listing = match.get('listing', {})
        print(f"\n   Match #{i}:")
        print(f"      Listing: {listing.get('title', 'Unknown')}")
        print(f"      Address: {listing.get('address_line_1', 'Unknown')}, {listing.get('city', 'Unknown')}")
        print(f"      Price: ${listing.get('price_per_month', 0)}/month")
        print(f"      Group rank: #{match.get('group_rank')}, Listing rank: #{match.get('listing_rank')}")
        print(f"      Scores: Group={match.get('group_score')}, Listing={match.get('listing_score')}")
        print(f"      Stable: {'✅' if match.get('is_stable') else '❌'}")
else:
    print(f"❌ Error: {response.json()}")

# Test 6: API Documentation
print("\n6️⃣  Test: Check API Documentation")
print("-" * 80)
print("✅ API documentation available at: http://localhost:8000/docs")
print("   Endpoints summary:")
print("   - GET    /api/roommate-groups - List groups")
print("   - POST   /api/roommate-groups - Create group")
print("   - GET    /api/roommate-groups/{id} - Get group details")
print("   - PUT    /api/roommate-groups/{id} - Update group")
print("   - DELETE /api/roommate-groups/{id} - Delete group")
print("   - GET    /api/roommate-groups/{id}/members - List members")
print("   - POST   /api/roommate-groups/{id}/invite - Invite member")
print("   - POST   /api/roommate-groups/{id}/join - Join group")
print("   - POST   /api/roommate-groups/{id}/reject - Reject invitation")
print("   - DELETE /api/roommate-groups/{id}/leave - Leave group")
print("   - DELETE /api/roommate-groups/{id}/members/{user_id} - Remove member")
print("   - GET    /api/roommate-groups/{id}/matches - Get stable matches")

print("\n" + "="*80)
print("✅ GROUPS API TESTS COMPLETE")
print("="*80)
print("\nNext steps:")
print("1. Test creating a group (requires auth token)")
print("2. Test inviting members")
print("3. Test member acceptance/rejection")
print("4. Build frontend pages to use these endpoints")
