# 🔄 Dynamic Group Matching - Flexible Size & Auto Re-matching

## Overview
Groups can have **any number of members** (not limited to 2). When a new member joins, the group automatically gets **re-matched** with listings that fit the new group size and updated preferences.

---

## 🎯 **Key Principles**

1. **No Hard Size Limit**: Groups can be 1, 2, 3, 4... any size
2. **Optional Size Target**: Creator can set `target_group_size` (e.g., "looking for 2 more people"), but it's not required
3. **Dynamic Matching**: Every time group composition changes → automatic re-match
4. **Aggregate Preferences**: Group preferences = weighted average of all members' preferences
5. **Size-Based Filtering**: Only match with listings that have enough bedrooms for current group size

---

## 📊 **Updated Data Model**

### **Changes to `roommate_groups` Table**

```sql
ALTER TABLE roommate_groups 
ALTER COLUMN target_group_size DROP NOT NULL;  -- Make optional

-- target_group_size can now be:
-- NULL = "open-ended, no limit" 
-- 2, 3, 4, etc. = "looking for this many total people"

-- Add new field for tracking actual size
ALTER TABLE roommate_groups 
ADD COLUMN current_member_count INTEGER DEFAULT 1;

-- Add trigger to auto-update current_member_count when members change
CREATE OR REPLACE FUNCTION update_group_member_count()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'INSERT' AND NEW.status = 'accepted' THEN
    UPDATE roommate_groups 
    SET current_member_count = current_member_count + 1
    WHERE id = NEW.group_id;
  ELSIF TG_OP = 'DELETE' OR (TG_OP = 'UPDATE' AND OLD.status = 'accepted' AND NEW.status != 'accepted') THEN
    UPDATE roommate_groups 
    SET current_member_count = current_member_count - 1
    WHERE id = OLD.group_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER group_member_count_trigger
AFTER INSERT OR UPDATE OR DELETE ON group_members
FOR EACH ROW EXECUTE FUNCTION update_group_member_count();
```

### **Changes to `listings` Table**

```sql
-- Ensure bedrooms is required (needed for size matching)
ALTER TABLE listings 
ALTER COLUMN number_of_bedrooms SET NOT NULL;

-- Add computed field for max group size a listing can accommodate
-- Typically: max_group_size = number_of_bedrooms + 1 (couples can share)
-- Or simpler: max_group_size = number_of_bedrooms
```

---

## 🧮 **Updated Matching Algorithm**

### **Phase 1: Eligibility Filtering (Updated)**

```python
def is_group_eligible_for_matching(group: Dict) -> bool:
    """
    Check if group is eligible for matching.
    
    Changed from stable matching v1:
    - No longer require target_group_size == 2
    - Accept groups of ANY size >= 1
    """
    
    # Basic checks
    if group.get('status') != 'active':
        return False
    
    if not group.get('target_city'):
        return False
    
    # Must have at least 1 accepted member
    current_size = group.get('current_member_count', 0)
    if current_size < 1:
        return False
    
    # Must have valid budget
    budget_min = group.get('budget_per_person_min')
    budget_max = group.get('budget_per_person_max')
    if not budget_min or not budget_max or budget_min > budget_max:
        return False
    
    return True


def is_listing_eligible_for_group(listing: Dict, group: Dict) -> bool:
    """
    Check if a listing can accommodate this group size.
    
    Key change: Match on actual group size, not target
    """
    
    # Listing must be active
    if listing.get('status') != 'active':
        return False
    
    # Must have enough bedrooms for group
    listing_bedrooms = listing.get('number_of_bedrooms', 0)
    group_size = group.get('current_member_count', 0)
    
    # Rule: Need at least as many bedrooms as people
    # (Can adjust: maybe bedroom_count >= ceil(group_size / 2) if couples share)
    if listing_bedrooms < group_size:
        return False
    
    # Property type rules based on size:
    if group_size == 1:
        # Solo person can take private room OR entire place
        if listing.get('property_type') not in ['private_room', 'entire_place']:
            return False
    else:
        # Groups (2+) need entire place
        if listing.get('property_type') != 'entire_place':
            return False
    
    return True
```

### **Phase 2: Aggregate Group Preferences**

When a group has multiple members, we need to aggregate their preferences:

```python
def calculate_aggregate_group_preferences(group_id: str) -> Dict:
    """
    Calculate aggregate preferences for a group based on all members.
    
    Returns aggregated preferences that represent the group as a whole.
    Used for scoring listing compatibility.
    """
    
    # Get all accepted members
    members = get_group_members(group_id, status='accepted')
    
    if len(members) == 0:
        return {}
    
    # Collect each member's preferences
    all_member_prefs = []
    for member in members:
        prefs = get_user_preferences(member.user_id)
        if prefs:
            all_member_prefs.append(prefs)
    
    # If we have no preference data, fall back to group-level targets
    if not all_member_prefs:
        group = get_group(group_id)
        return {
            'budget_per_person_min': group.get('budget_per_person_min'),
            'budget_per_person_max': group.get('budget_per_person_max'),
            'target_city': group.get('target_city'),
            'target_move_in_date': group.get('target_move_in_date'),
            'lifestyle_preferences': {}
        }
    
    # Aggregate preferences
    aggregated = {}
    
    # 1. Budget: Use the OVERLAP of all members' budgets
    #    (The range that works for ALL members)
    all_budget_mins = [p.get('budget_min', 0) for p in all_member_prefs if p.get('budget_min')]
    all_budget_maxs = [p.get('budget_max', float('inf')) for p in all_member_prefs if p.get('budget_max')]
    
    if all_budget_mins and all_budget_maxs:
        # Group's min = highest individual min (most restrictive)
        # Group's max = lowest individual max (most restrictive)
        aggregated['budget_per_person_min'] = max(all_budget_mins)
        aggregated['budget_per_person_max'] = min(all_budget_maxs)
    
    # 2. Move-in Date: Use median date (or most common)
    all_dates = [p.get('move_in_date') for p in all_member_prefs if p.get('move_in_date')]
    if all_dates:
        # Sort dates and take median
        sorted_dates = sorted(all_dates)
        median_index = len(sorted_dates) // 2
        aggregated['target_move_in_date'] = sorted_dates[median_index]
    
    # 3. City: Should be same for all (enforced by group creation)
    aggregated['target_city'] = all_member_prefs[0].get('target_city')
    
    # 4. Lifestyle Preferences: Take MOST RESTRICTIVE
    #    (If anyone wants "no smoking", group needs "no smoking")
    aggregated['lifestyle_preferences'] = aggregate_lifestyle_preferences(all_member_prefs)
    
    # 5. Bedrooms: At least as many as group size
    aggregated['target_bedrooms'] = len(members)  # Minimum
    
    # 6. Bathrooms: Scale with group size
    #    1-2 people: 1 bath OK
    #    3-4 people: 1.5+ baths preferred
    #    5+ people: 2+ baths preferred
    if len(members) <= 2:
        aggregated['target_bathrooms'] = 1.0
    elif len(members) <= 4:
        aggregated['target_bathrooms'] = 1.5
    else:
        aggregated['target_bathrooms'] = 2.0
    
    return aggregated


def aggregate_lifestyle_preferences(all_prefs: List[Dict]) -> Dict:
    """
    Aggregate lifestyle preferences - use MOST RESTRICTIVE.
    
    Logic:
    - If anyone wants "no_smoking", group requires "no_smoking"
    - If anyone wants "quiet", group requires "quiet"
    - If anyone wants "no_pets", group requires "no_pets"
    """
    
    lifestyle_lists = [p.get('lifestyle_preferences', {}) for p in all_prefs]
    
    if not lifestyle_lists:
        return {}
    
    aggregated = {}
    
    # Cleanliness: Take highest standard
    cleanliness_order = ['messy', 'moderate', 'clean', 'very_clean']
    all_cleanliness = [lp.get('cleanliness') for lp in lifestyle_lists if lp.get('cleanliness')]
    if all_cleanliness:
        # Most restrictive = very_clean > clean > moderate > messy
        aggregated['cleanliness'] = max(all_cleanliness, key=lambda x: cleanliness_order.index(x))
    
    # Noise level: Take quietest
    noise_order = ['loud', 'moderate', 'quiet']
    all_noise = [lp.get('noise_level') for lp in lifestyle_lists if lp.get('noise_level')]
    if all_noise:
        aggregated['noise_level'] = max(all_noise, key=lambda x: noise_order.index(x))
    
    # Smoking: If anyone says no_smoking, group is no_smoking
    all_smoking = [lp.get('smoking') for lp in lifestyle_lists if lp.get('smoking')]
    if 'no_smoking' in all_smoking:
        aggregated['smoking'] = 'no_smoking'
    elif 'outdoor_only' in all_smoking:
        aggregated['smoking'] = 'outdoor_only'
    elif all_smoking:
        aggregated['smoking'] = all_smoking[0]
    
    # Pets: If anyone says no_pets, group is no_pets
    all_pets = [lp.get('pets') for lp in lifestyle_lists if lp.get('pets')]
    if 'no_pets' in all_pets:
        aggregated['pets'] = 'no_pets'
    elif all_pets:
        aggregated['pets'] = 'pets_ok'
    
    # Guests: Take most restrictive
    guests_order = ['frequently', 'occasionally', 'rarely']
    all_guests = [lp.get('guests_frequency') for lp in lifestyle_lists if lp.get('guests_frequency')]
    if all_guests:
        aggregated['guests_frequency'] = max(all_guests, key=lambda x: guests_order.index(x))
    
    return aggregated
```

### **Phase 3: Updated Scoring**

```python
def calculate_group_score(group: Dict, listing: Dict) -> float:
    """
    Calculate how much a group likes a listing.
    
    Updated to use aggregate preferences and scale with group size.
    """
    
    # Get aggregate preferences for the group
    group_prefs = calculate_aggregate_group_preferences(group['id'])
    group_size = group.get('current_member_count', 1)
    
    score = 0
    
    # 1. Budget Fit (25 points)
    # Total price = price_per_month
    # Per person = price_per_month / group_size
    per_person_price = listing['price_per_month'] / group_size
    
    budget_min = group_prefs.get('budget_per_person_min', 0)
    budget_max = group_prefs.get('budget_per_person_max', float('inf'))
    budget_mid = (budget_min + budget_max) / 2
    
    price_diff = abs(per_person_price - budget_mid)
    
    if price_diff <= 100:
        score += 25
    elif price_diff <= 300:
        score += 20
    elif price_diff <= 500:
        score += 15
    else:
        score += 10
    
    # 2. Bedrooms Match (20 points)
    # Listing should have enough bedrooms for group
    listing_bedrooms = listing.get('number_of_bedrooms', 0)
    
    if listing_bedrooms == group_size:
        score += 20  # Perfect: one bedroom per person
    elif listing_bedrooms == group_size + 1:
        score += 18  # Extra bedroom (bonus!)
    elif listing_bedrooms >= group_size:
        score += 15  # More than enough
    else:
        score += 5   # Not enough (shouldn't happen if filtered correctly)
    
    # 3. Bathrooms Match (15 points)
    target_bathrooms = group_prefs.get('target_bathrooms', 1.0)
    listing_bathrooms = listing.get('number_of_bathrooms', 1.0)
    
    if listing_bathrooms >= target_bathrooms:
        score += 15
    elif listing_bathrooms >= target_bathrooms - 0.5:
        score += 10
    else:
        score += 5
    
    # 4. Other amenities... (same as before, 40 points total)
    # Furnished (10), Utilities (10), Deposit (10), House Rules (10)
    
    return min(score, 100)


def calculate_listing_score(listing: Dict, group: Dict) -> float:
    """
    Calculate how much a listing likes a group.
    
    Updated to prefer larger groups (more rent revenue).
    """
    
    group_size = group.get('current_member_count', 1)
    group_prefs = calculate_aggregate_group_preferences(group['id'])
    
    score = 0
    
    # 1. Total Budget Score (40 points)
    # Listings prefer groups that can pay more TOTAL
    total_budget_max = group_prefs.get('budget_per_person_max', 0) * group_size
    listing_price = listing.get('price_per_month', 0)
    
    budget_ratio = total_budget_max / listing_price if listing_price > 0 else 0
    
    if budget_ratio >= 1.5:
        score += 40
    elif budget_ratio >= 1.3:
        score += 35
    elif budget_ratio >= 1.15:
        score += 30
    elif budget_ratio >= 1.05:
        score += 25
    elif budget_ratio >= 1.0:
        score += 20
    else:
        score += 10
    
    # 2. Group Size Efficiency (20 points)
    # Listings prefer groups that utilize bedrooms efficiently
    listing_bedrooms = listing.get('number_of_bedrooms', 1)
    utilization = group_size / listing_bedrooms
    
    if utilization == 1.0:
        score += 20  # Perfect fit
    elif utilization >= 0.8:
        score += 15  # Good fit
    elif utilization >= 0.6:
        score += 10
    else:
        score += 5
    
    # 3. Verification Score (20 points)
    # Check verification rate of group members
    verification_rate = get_group_verification_rate(group['id'])
    score += verification_rate * 20
    
    # 4. Other factors (20 points)
    # Date alignment, preferences match, etc.
    
    return min(score, 100)
```

---

## 🔄 **Automatic Re-Matching Trigger**

### **When Does Re-Matching Happen?**

Re-matching is triggered when:
1. **New member joins** (status changes to 'accepted')
2. **Member leaves** (status changes from 'accepted' to anything else)
3. **Group preferences updated** (budget, move-in date, etc.)

### **Implementation**

**Option 1: Database Trigger (Recommended)**

```sql
-- Create a function to mark group for re-matching
CREATE OR REPLACE FUNCTION mark_group_for_rematching()
RETURNS TRIGGER AS $$
BEGIN
  -- When group composition or preferences change, trigger re-match
  
  IF TG_TABLE_NAME = 'group_members' THEN
    -- Member added or removed
    IF (TG_OP = 'INSERT' AND NEW.status = 'accepted') OR 
       (TG_OP = 'UPDATE' AND OLD.status != 'accepted' AND NEW.status = 'accepted') OR
       (TG_OP = 'UPDATE' AND OLD.status = 'accepted' AND NEW.status != 'accepted') OR
       (TG_OP = 'DELETE' AND OLD.status = 'accepted') THEN
      
      -- Call matching API (via pg_notify or queue)
      PERFORM pg_notify('group_needs_rematching', NEW.group_id::text);
    END IF;
    
  ELSIF TG_TABLE_NAME = 'roommate_groups' THEN
    -- Group preferences changed
    IF TG_OP = 'UPDATE' AND (
       OLD.budget_per_person_min != NEW.budget_per_person_min OR
       OLD.budget_per_person_max != NEW.budget_per_person_max OR
       OLD.target_move_in_date != NEW.target_move_in_date OR
       OLD.target_city != NEW.target_city
    ) THEN
      PERFORM pg_notify('group_needs_rematching', NEW.id::text);
    END IF;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach triggers
CREATE TRIGGER group_member_change_rematching
AFTER INSERT OR UPDATE OR DELETE ON group_members
FOR EACH ROW EXECUTE FUNCTION mark_group_for_rematching();

CREATE TRIGGER group_preferences_change_rematching
AFTER UPDATE ON roommate_groups
FOR EACH ROW EXECUTE FUNCTION mark_group_for_rematching();
```

**Option 2: Application-Level (Alternative)**

```python
# In groups.py route handlers

@router.post("/{group_id}/members/{user_id}/approve")
async def approve_member(group_id: str, user_id: str, token: str):
    """Approve a user to join the group"""
    
    # ... existing approval logic ...
    
    # After successful approval:
    # 1. Update group_members status to 'accepted'
    # 2. Trigger re-matching
    from app.services.stable_matching_service import trigger_group_rematching
    
    await trigger_group_rematching(group_id)
    
    return {"status": "success", "message": "Member approved and group re-matched"}


# In stable_matching_service.py

async def trigger_group_rematching(group_id: str):
    """
    Re-run stable matching for a specific group.
    
    Steps:
    1. Delete old matches for this group
    2. Get updated group data (new size, aggregate preferences)
    3. Find eligible listings for new group size
    4. Run matching algorithm
    5. Save new matches
    """
    
    from app.services.stable_matching.persistence import delete_matches_for_group
    from app.services.stable_matching import (
        get_eligible_listings,
        build_feasible_pairs,
        build_preference_lists,
        run_deferred_acceptance,
        save_matching_results
    )
    
    # 1. Clear old matches
    await delete_matches_for_group(group_id)
    
    # 2. Get current group data
    group = await get_group_with_members(group_id)
    
    if not is_group_eligible_for_matching(group):
        return {"status": "skipped", "reason": "Group not eligible"}
    
    # 3. Get eligible listings for this group's city and size
    city = group['target_city']
    group_size = group['current_member_count']
    
    listings = await get_eligible_listings(
        city=city,
        min_bedrooms=group_size
    )
    
    # 4. Build feasible pairs (just for this group)
    feasible_pairs = []
    for listing in listings:
        if is_listing_eligible_for_group(listing, group):
            # Check hard constraints
            if location_matches(group, listing) and \
               date_matches(group, listing) and \
               price_matches(group, listing):
                feasible_pairs.append((group['id'], listing['id']))
    
    if not feasible_pairs:
        return {"status": "no_matches", "reason": "No feasible listings found"}
    
    # 5. Build preference lists (just for this group)
    group_preferences, listing_preferences = build_preference_lists(
        feasible_pairs,
        [group],
        listings
    )
    
    # 6. Run matching (simplified - single group)
    matches = run_deferred_acceptance(
        group_preferences,
        listing_preferences
    )
    
    # 7. Save results
    await save_matching_results(matches, group_id=group_id)
    
    return {
        "status": "success",
        "group_id": group_id,
        "matches_found": len(matches),
        "results": matches
    }
```

---

## 📱 **API Changes**

### **1. Create Group (Updated)**

```http
POST /api/roommate-groups

Body:
{
  "group_name": "SF Housing Group",
  "description": "Looking for housing in SF",
  "target_city": "San Francisco",
  "budget_per_person_min": 1200,
  "budget_per_person_max": 1800,
  "target_move_in_date": "2025-12-01",
  "target_group_size": null,  // ← NULL = open-ended, no limit
  "target_bedrooms": 2,        // Will update as group grows
  "target_bathrooms": 1.5
}

Response:
{
  "status": "success",
  "data": {
    "id": "group-uuid",
    "current_member_count": 1,  // Creator is first member
    "target_group_size": null,
    "is_open": true,            // Accepting new members
    "matches": []               // Initially empty, will match solo creator
  }
}

Triggers:
- Group created with 1 member
- Auto-matches with listings suitable for 1 person
  (private rooms, studios, etc.)
```

### **2. Approve Member (Updated)**

```http
POST /api/roommate-groups/{group_id}/members/{user_id}/approve

Response:
{
  "status": "success",
  "message": "Member approved",
  "group": {
    "id": "group-uuid",
    "current_member_count": 2,  // ← Updated!
    "target_group_size": 3,
    "is_open": true
  },
  "rematching": {
    "status": "triggered",
    "new_matches_found": 5,
    "message": "Group re-matched with 2-person listings"
  }
}

Triggers:
- Member count: 1 → 2
- Old matches (1-person) deleted
- New matches (2-person) calculated
- Group preferences re-aggregated
```

### **3. Get Group Matches (Updated)**

```http
GET /api/roommate-groups/{group_id}/matches

Response:
{
  "status": "success",
  "group_info": {
    "id": "group-uuid",
    "group_name": "SF Housing Group",
    "current_member_count": 2,
    "target_group_size": 3,
    "members": [
      {"id": "user-1", "name": "Alice", "joined_at": "..."},
      {"id": "user-2", "name": "Bob", "joined_at": "..."}
    ],
    "aggregate_preferences": {
      "budget_per_person_min": 1200,
      "budget_per_person_max": 1600,  // Narrowed from overlap
      "target_bedrooms": 2,
      "lifestyle_preferences": {
        "cleanliness": "very_clean",  // Most restrictive
        "smoking": "no_smoking"       // Most restrictive
      }
    }
  },
  "count": 5,
  "matches": [
    {
      "listing_id": "listing-A",
      "title": "2BR Apartment in Mission",
      "price_per_month": 3200,
      "price_per_person": 1600,  // ← 3200 / 2
      "bedrooms": 2,              // ← Perfect for 2 people
      "group_rank": 1,
      "group_score": 92,
      "listing_rank": 3,
      "listing_score": 85,
      "matched_at": "2025-11-30T17:30:00Z",
      "match_reason": "Calculated for 2-person group"
    }
  ]
}
```

---

## 🎯 **User Journey Example**

### **Scenario: Group Grows from 1 → 2 → 3**

```
DAY 1: Alice creates group (solo)
├─ Creates group with budget $1200-$1800
├─ current_member_count = 1
├─ System matches with 1-person listings:
│  • Studios ($1200-1800/month)
│  • Private rooms ($800-1500/month)
│  • 1BR apartments
└─ Alice sees 20 matches for solo living

DAY 3: Alice invites Bob → Bob accepts
├─ Bob joins group
├─ current_member_count = 2
├─ Trigger: Auto re-matching
├─ System aggregates preferences:
│  • Alice: $1200-1800, clean, quiet
│  • Bob: $1400-1600, very_clean, no_smoking
│  • Aggregate: $1400-1600, very_clean, quiet, no_smoking
├─ System deletes 1-person matches
├─ System calculates 2-person matches:
│  • 2BR apartments ($2800-3200/month = $1400-1600/person)
│  • Must have 2 bedrooms minimum
└─ Group sees 15 matches for 2-person living

DAY 7: Alice invites Charlie → Charlie accepts
├─ Charlie joins group
├─ current_member_count = 3
├─ Trigger: Auto re-matching again
├─ System re-aggregates:
│  • Alice: $1200-1800
│  • Bob: $1400-1600
│  • Charlie: $1300-1700
│  • New aggregate: $1400-1600 (overlap of all three)
├─ System deletes 2-person matches
├─ System calculates 3-person matches:
│  • 3BR apartments ($4200-4800/month = $1400-1600/person)
│  • Must have 3 bedrooms minimum
└─ Group sees 8 matches for 3-person living

SUMMARY:
• Each time group grows → automatic re-match
• Preferences become more restrictive (overlap)
• Listings scale to match group size
• Group always sees relevant matches for CURRENT size
```

---

## 💡 **Benefits of This Approach**

1. **Flexible**: No hard limit on group size
2. **Dynamic**: Matches update automatically as group evolves
3. **Realistic**: Preferences aggregate naturally
4. **Scalable**: Works for solo, pairs, or large groups
5. **Fair**: Both small and large groups can find housing
6. **Transparent**: Users understand why matches change

---

## ⚠️ **Edge Cases to Handle**

### **1. Group shrinks (member leaves)**
```python
# When member count decreases (3 → 2):
# - Re-aggregate preferences (may become LESS restrictive)
# - Re-match with smaller listings (2BR instead of 3BR)
# - Potentially MORE matches available
```

### **2. Group reaches target_group_size**
```python
# When current_member_count == target_group_size:
# - Mark group as "complete" (is_open = false)
# - Stop accepting new join requests
# - Continue matching (final composition)
```

### **3. Conflicting preferences**
```python
# When member budgets don't overlap:
# Alice: $1200-1500
# Bob: $1800-2200
# Overlap: NONE!

# Solution: Use UNION instead of overlap for budget
# Or notify group creator of conflict
```

### **4. Performance with large groups**
```python
# For groups of 5+ people:
# - Aggregate calculation becomes complex
# - Consider caching aggregated preferences
# - Update only when member joins/leaves
```

---

## 🚀 **Implementation Priority**

### **Phase 1: Core Changes** (Start Here)
1. ✅ Make `target_group_size` nullable in database
2. ✅ Add `current_member_count` field + trigger
3. ✅ Update eligibility filters (remove size=2 restriction)
4. ✅ Implement aggregate preferences function

### **Phase 2: Re-Matching Logic**
5. ✅ Create `trigger_group_rematching()` function
6. ✅ Hook into member approval flow
7. ✅ Test with various group sizes (1, 2, 3, 4, 5)

### **Phase 3: Optimization**
8. ⏳ Cache aggregate preferences
9. ⏳ Batch re-matching (if many groups change at once)
10. ⏳ Add analytics on group size distribution

---

Want me to start implementing these changes? I can:
1. Update the database schema
2. Modify the matching algorithm
3. Add the re-matching triggers
4. Test with different group sizes

Let me know what you'd like to tackle first! 🎯
