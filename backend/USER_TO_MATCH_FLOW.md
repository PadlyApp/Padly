# 🔄 Padly User Journey: From Individual → Group → Matched Listing

This document outlines the complete end-to-end flow from user signup to getting matched with a housing listing.

---

## 📍 **Current State: What's Implemented & What's Not**

### ✅ **Fully Implemented**
- User account creation & authentication
- Group creation & member management
- Listings CRUD operations
- Stable matching algorithm (groups → listings)
- Match viewing & management

### ⚠️ **Partially Implemented**
- Individual user browsing listings (basic/random matching)
- User preferences storage

### ❌ **Not Implemented**
- User-to-user matching (finding roommates)
- Automated group formation
- User recommendations for group formation
- Notification system for matches
- Match acceptance workflow

---

## 🚶 **Journey 1: Individual User → Manual Group Formation → Matched Listing**

This is the **currently available** flow in your system.

### **Phase 1: User Onboarding** ✅
```
1. User Signs Up
   POST /api/auth/signup
   {
     "email": "alice@example.com",
     "full_name": "Alice Johnson",
     "role": "renter",
     "company_name": "Google",
     "role_title": "Software Engineer"
   }
   
   Creates record in: users table
   ├─ id: uuid (auto-generated)
   ├─ email, full_name, company_name, role_title
   ├─ verification_status: "unverified"
   └─ created_at: timestamp

2. User Optionally Verifies
   POST /api/auth/verify-company-email
   {
     "email": "alice@google.com"
   }
   
   Updates: users.verification_status → "email_verified"

3. User Sets Preferences (Optional)
   PUT /api/preferences/{user_id}
   {
     "target_city": "San Francisco",
     "budget_min": 1200,
     "budget_max": 1800,
     "move_in_date": "2025-12-01",
     "lifestyle_preferences": {
       "cleanliness": "very_clean",
       "noise_level": "quiet",
       "pets": "no_pets"
     }
   }
   
   Creates/Updates: personal_preferences table
```

### **Phase 2: Finding a Roommate** ⚠️ (Manual/External Process)
```
Current State: NOT AUTOMATED IN SYSTEM

What happens now:
┌─────────────────────────────────────────┐
│ Users find roommates OUTSIDE the app:  │
│ - Through friends/colleagues            │
│ - Company Slack channels                │
│ - School Facebook groups                │
│ - Reddit, Discord, etc.                 │
└─────────────────────────────────────────┘

What COULD happen (not implemented):
┌──────────────────────────────────────────────┐
│ POST /api/roommate-posts (Create post)      │
│ GET  /api/roommate-posts (Browse posts)     │
│ GET  /api/matches/users/{user_id}           │
│      (Find compatible users)                 │
│                                              │
│ Tables: roommate_posts                       │
│ Algorithm: User-to-user matching (MISSING)  │
└──────────────────────────────────────────────┘
```

### **Phase 3: Group Creation** ✅
```
User #1 (Creator) creates a group:

POST /api/roommate-groups
{
  "creator_user_id": "alice-uuid",
  "group_name": "Alice & Bob - SF Housing",
  "description": "Two Google engineers looking for housing",
  "target_city": "San Francisco",
  "budget_per_person_min": 1200,
  "budget_per_person_max": 1800,
  "target_move_in_date": "2025-12-01",
  "target_group_size": 2,
  "target_bedrooms": 2,
  "target_bathrooms": 1.5,
  "target_furnished": true,
  "target_utilities_included": false,
  "target_deposit_amount": 3000,
  "status": "active"
}

Creates records:
├─ roommate_groups table
│  └─ All target preferences stored
└─ group_members table
   └─ (alice-uuid, group-id, is_creator=true, status='accepted')
```

### **Phase 4: Inviting Roommate to Group** ✅
```
Option A: Invite by Email
POST /api/roommate-groups/{group_id}/invite
{
  "user_email": "bob@google.com",
  "message": "Let's find a place together!"
}

Creates: group_members entry with status='pending'

Option B: Self-Request to Join
POST /api/roommate-groups/{group_id}/request-join
(Bob requests to join Alice's group)

Creates: group_members entry with status='pending'

Then Bob accepts:
POST /api/roommate-groups/{group_id}/join

Updates: group_members.status → 'accepted'
```

### **Phase 5: Stable Matching Algorithm Runs** ✅
```
Trigger: Manual API call or scheduled job

POST /api/stable-matches/run
{
  "city": "San Francisco",
  "date_flexibility_days": 30
}

ALGORITHM EXECUTION:
┌──────────────────────────────────────────────────────┐
│ Step 1: Fetch Eligible Groups                       │
│ ───────────────────────────────────────────────────  │
│ FROM: roommate_groups                               │
│ WHERE:                                              │
│   - target_city = "San Francisco"                   │
│   - target_group_size = 2                           │
│   - status = 'active'                               │
│   - Valid budget range                              │
│   - Valid move-in date                              │
│                                                      │
│ JOINS: group_members → users (for verification)     │
│ Result: List of eligible 2-person groups            │
└──────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────┐
│ Step 2: Fetch Eligible Listings                     │
│ ───────────────────────────────────────────────────  │
│ FROM: listings                                       │
│ WHERE:                                              │
│   - city = "San Francisco"                          │
│   - property_type = 'entire_place'                  │
│   - number_of_bedrooms >= 2                         │
│   - status = 'active'                               │
│   - accepts_groups = true                           │
│                                                      │
│ Result: List of eligible entire-unit listings       │
└──────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────┐
│ Step 3: Build Feasible Pairs (Hard Constraints)     │
│ ───────────────────────────────────────────────────  │
│ For each (group, listing) combination:              │
│                                                      │
│ ✓ Location Match:                                   │
│   group.target_city == listing.city                 │
│                                                      │
│ ✓ Date Match:                                       │
│   |group.target_move_in_date - listing.available_   │
│    from| <= 30 days                                 │
│                                                      │
│ ✓ Price Match:                                      │
│   budget_min*2 <= price_per_month <= budget_max*2   │
│                                                      │
│ ✓ Attribute Match:                                  │
│   If group wants furnished → listing must be        │
│   If group wants utilities → listing must include   │
│                                                      │
│ Result: List of (group_id, listing_id) pairs        │
│         that pass ALL hard constraints              │
└──────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────┐
│ Step 4: Calculate Compatibility Scores              │
│ ───────────────────────────────────────────────────  │
│ For each feasible pair:                             │
│                                                      │
│ GROUP → LISTING SCORE (0-100):                      │
│   • Bathrooms match         (20 pts)                │
│   • Furnished preference    (20 pts)                │
│   • Utilities preference    (20 pts)                │
│   • Deposit within range    (20 pts)                │
│   • House rules compatible  (20 pts)                │
│                                                      │
│ LISTING → GROUP SCORE (0-100):                      │
│   • Budget affordability    (40 pts)                │
│     Higher budget = better score                    │
│   • Deposit willingness     (30 pts)                │
│   • Preference match        (30 pts)                │
│                                                      │
│ Result: Each pair has 2 scores                      │
└──────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────┐
│ Step 5: Build Preference Lists (Rankings)           │
│ ───────────────────────────────────────────────────  │
│ For each group:                                      │
│   Rank all feasible listings by group_score DESC    │
│   Example: Alice & Bob's preferences:               │
│     1. Listing A (score: 95)                        │
│     2. Listing B (score: 88)                        │
│     3. Listing C (score: 75)                        │
│                                                      │
│ For each listing:                                    │
│   Rank all feasible groups by listing_score DESC    │
│   Example: Listing A's preferences:                 │
│     1. Group X (score: 92)                          │
│     2. Alice & Bob (score: 85)                      │
│     3. Group Z (score: 70)                          │
└──────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────┐
│ Step 6: Deferred Acceptance Algorithm               │
│ ───────────────────────────────────────────────────  │
│ GROUPS PROPOSE (Groups-proposing orientation)       │
│                                                      │
│ Round 1:                                             │
│   Each free group proposes to top choice listing    │
│   Listings tentatively accept best proposal         │
│   Other groups rejected → become free again         │
│                                                      │
│ Round 2:                                             │
│   Rejected groups propose to next choice            │
│   Listings compare new proposal vs current match    │
│   Keep better one, reject the other                 │
│                                                      │
│ ... continues until ...                             │
│   No free group wants to propose anymore            │
│                                                      │
│ RESULT: Stable matching                             │
│   - No "blocking pairs" exist                       │
│   - Group-optimal (best for renters)                │
└──────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────┐
│ Step 7: Save Results to Database                    │
│ ───────────────────────────────────────────────────  │
│ INSERT INTO match_diagnostics:                       │
│   - city, date window, counts, statistics           │
│   - match_quality_score, avg_ranks                  │
│                                                      │
│ INSERT INTO stable_matches (for each match):        │
│   - group_id, listing_id                            │
│   - group_score, listing_score                      │
│   - group_rank (e.g., 1 = top choice)               │
│   - listing_rank                                    │
│   - status: 'active'                                │
│   - matched_at: timestamp                           │
│   - is_stable: true                                 │
└──────────────────────────────────────────────────────┘
```

### **Phase 6: Groups View Their Matches** ✅
```
GET /api/roommate-groups/{group_id}/matches

Returns:
{
  "status": "success",
  "count": 3,
  "matches": [
    {
      "id": "match-uuid-1",
      "listing_id": "listing-A-uuid",
      "group_rank": 1,          ← "Your #1 choice!"
      "listing_rank": 2,         ← "Their #2 choice"
      "group_score": 95,
      "listing_score": 85,
      "matched_at": "2025-11-30T...",
      "status": "active",
      "listing_details": {
        "title": "Spacious 2BR in Mission",
        "price_per_month": 3400,
        "address": "...",
        "photos": [...]
      }
    },
    {
      "listing_id": "listing-B-uuid",
      "group_rank": 2,          ← "Your #2 choice"
      "group_score": 88,
      ...
    }
  ]
}
```

### **Phase 7: Match Acceptance** ❌ (Not Implemented)
```
What SHOULD happen (future):

1. Group reviews matches
2. Group accepts specific listing:
   POST /api/stable-matches/{match_id}/accept

3. Listing host gets notification
4. Host reviews group details (verification, profiles)
5. Host accepts or rejects:
   POST /api/stable-matches/{match_id}/host-response
   { "decision": "accepted" }

6. If both accept → status changes to 'accepted'
7. Both parties get contact info to proceed
8. Other matches for this group/listing are rejected

Current State:
- Matches are viewable
- No acceptance workflow
- Manual follow-up outside platform
```

---

## 🏃 **Journey 2: Individual User → Browse Listings (Current)**

For users who don't form groups or want to browse individually:

```
GET /api/matches/{user_id}
Uses: app/services/matching_algorithm.py
Algorithm: Random scoring (placeholder)

Returns:
{
  "user_id": "alice-uuid",
  "total_matches": 20,
  "algorithm_version": "random_v1",
  "matches": [
    {
      "id": "listing-1",
      "title": "Cozy Studio in SOMA",
      "match_score": 87,  ← Random/deterministic based on hash
      ...
    }
  ]
}

⚠️ This is primitive - should use preference-based scoring!
```

---

## 🔮 **Journey 3: Automated Group Formation (Future Vision)**

What COULD be implemented:

```
Step 1: User creates roommate post
POST /api/roommate-posts
{
  "title": "Google SWE looking for clean, quiet roommate",
  "target_city": "San Francisco",
  "budget_min": 1200,
  "budget_max": 1800,
  "move_in_date": "2025-12-01",
  "lifestyle_preferences": {...}
}

Step 2: System finds compatible users
GET /api/matches/roommates/{user_id}
Algorithm: User-to-user compatibility scoring
  - Budget alignment
  - Move-in date proximity
  - Lifestyle compatibility
  - Company/school match bonus
  - Verification trust score

Step 3: Users connect & form group
- Message each other in-app
- Decide to team up
- One creates group, invites the other

Step 4: Proceed to stable matching (as above)

This creates the full pipeline:
User → Find Roommate → Form Group → Match Listing
```

---

## 📊 **Data Flow Summary**

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER SIGNUP                             │
│                         users table                             │
│                personal_preferences table                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  ROOMMATE FINDING (Manual)                      │
│                  ❌ No system support                           │
│                  (Could use roommate_posts)                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     GROUP FORMATION                             │
│                  roommate_groups table                          │
│                  group_members table                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   STABLE MATCHING RUNS                          │
│           (Manual trigger or scheduled job)                     │
│                                                                 │
│  Inputs: roommate_groups, listings                             │
│  Algorithm: Gale-Shapley Deferred Acceptance                   │
│  Outputs: stable_matches, match_diagnostics                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    VIEW MATCHES                                 │
│          GET /api/roommate-groups/{id}/matches                  │
│                                                                 │
│  Groups see their ranked matches with scores                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   MATCH ACCEPTANCE                              │
│                   ❌ Not implemented                            │
│    (Manual follow-up outside platform)                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔑 **Key Takeaways**

### **What Works**:
1. ✅ Users can create accounts & verify
2. ✅ Users can manually form groups (with friends they find outside)
3. ✅ Groups can specify detailed housing preferences
4. ✅ Stable matching algorithm finds optimal group-listing pairs
5. ✅ Groups can view their matches with rankings

### **What's Missing**:
1. ❌ User-to-user matching (finding compatible roommates)
2. ❌ Automated group formation suggestions
3. ❌ Match acceptance workflow (both sides confirming)
4. ❌ Notifications for new matches
5. ❌ Better individual user → listing matching

### **The Gap**:
The biggest gap is **roommate discovery**. Users need to find compatible roommates BEFORE using your platform's group matching. This happens externally (Slack, Reddit, friends), which defeats the purpose of a centralized platform.

**Recommendation**: Implement user-to-user matching to create a complete end-to-end flow.

---

**Last Updated**: 2025-11-30
