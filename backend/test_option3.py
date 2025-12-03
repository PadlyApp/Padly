#!/usr/bin/env python3
"""Test Option 3: Hybrid Re-matching with Confirmation"""

import asyncio
from app.dependencies.supabase import get_admin_client
from app.services.stable_matching.persistence import MatchPersistenceEngine
from app.routes.stable_matching import run_matching, RunMatchingRequest


async def full_test():
    client = get_admin_client()
    engine = MatchPersistenceEngine(client)
    
    print("=" * 60)
    print("FULL TEST: Option 3 - Hybrid Re-matching with Confirmation")
    print("=" * 60)
    print()
    
    # Step 1: Check current state
    print("STEP 1: Current state")
    confirmed, group_ids, listing_ids = await engine.get_confirmed_matches("Oakland")
    print(f"  Confirmed matches: {len(confirmed)}")
    
    active_response = client.table("stable_matches").select("id").eq("status", "active").execute()
    print(f"  Total active matches: {len(active_response.data) if active_response.data else 0}")
    print()
    
    # Step 2: Run matching
    print("STEP 2: Run matching (should preserve confirmed)")
    request = RunMatchingRequest(city="Oakland", date_flexibility_days=30)
    response = await run_matching(request)
    print(f"  {response.message}")
    print(f"  New matches created: {len(response.matches)}")
    print()
    
    # Step 3: Verify confirmed match still exists
    print("STEP 3: Verify confirmed match preserved")
    confirmed_after, _, _ = await engine.get_confirmed_matches("Oakland")
    
    if confirmed_after:
        print(f"  ✅ {len(confirmed_after)} confirmed match(es) preserved")
        for m in confirmed_after:
            gid = m["group_id"][:8]
            lid = m["listing_id"][:8]
            print(f"     - {gid}... ↔ {lid}...")
    else:
        print("  ❌ No confirmed matches found (may have been deleted)")
    print()
    
    # Step 4: Summary
    print("STEP 4: Summary")
    final_active = client.table("stable_matches").select("id").eq("status", "active").execute()
    print(f"  Total active matches now: {len(final_active.data) if final_active.data else 0}")
    print(f"  Confirmed (preserved): {len(confirmed_after)}")
    print(f"  New (unconfirmed): {len(response.matches)}")
    print()
    
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(full_test())
