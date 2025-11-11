# 🎯 Stable Matching Algorithm Implementation - TODO List

**Algorithm Type:** Deferred Acceptance (Gale-Shapley)  
**Orientation:** Groups-proposing (renter-friendly)  
**Scope:** 2-person groups → entire-unit listings  
**Date:** November 11, 2025

---

## 📋 Phase 0: Database Schema & Setup

### 0.1 Database Changes
- [ ] Add `accepts_groups` boolean flag to `listings` table (optional, default true)
- [ ] Add `max_occupancy` integer to `listings` table (optional)
- [ ] Create `stable_matches` table with fields:
  - [ ] `id` (uuid, primary key)
  - [ ] `group_id` (uuid, foreign key to roommate_groups)
  - [ ] `listing_id` (uuid, foreign key to listings)
  - [ ] `match_round_id` (uuid, for tracking batch runs)
  - [ ] `orientation` (text, e.g., "groups-proposing")
  - [ ] `city` (text)
  - [ ] `match_window_start` (date)
  - [ ] `match_window_end` (date)
  - [ ] `group_rank_of_listing` (integer, what rank was this listing for the group)
  - [ ] `listing_rank_of_group` (integer, what rank was this group for the listing)
  - [ ] `group_score` (numeric, S_g(l) score)
  - [ ] `listing_score` (numeric, S_l(g) score)
  - [ ] `explanation_reasons` (jsonb, array of reason strings)
  - [ ] `created_at` (timestamp)
  - [ ] `expires_at` (timestamp, optional)
  - [ ] `status` (text: 'active', 'accepted', 'rejected', 'expired')

### 0.2 Indexes
- [ ] Index on `stable_matches(group_id, status)`
- [ ] Index on `stable_matches(listing_id, status)`
- [ ] Index on `stable_matches(match_round_id)`
- [ ] Index on `listings(city, status)`
- [ ] Index on `roommate_groups(target_city, status, target_group_size)`

### 0.3 Match Diagnostics Table
- [ ] Create `match_diagnostics` table:
  - [ ] `match_round_id` (uuid)
  - [ ] `city` (text)
  - [ ] `window_start` (date)
  - [ ] `window_end` (date)
  - [ ] `total_groups` (integer)
  - [ ] `total_listings` (integer)
  - [ ] `matched_groups` (integer)
  - [ ] `matched_listings` (integer)
  - [ ] `match_rate_pct` (numeric)
  - [ ] `median_group_rank` (integer)
  - [ ] `top_3_rate_pct` (numeric)
  - [ ] `unmatched_reasons` (jsonb, breakdown by reason)
  - [ ] `avg_verification_rate` (numeric)
  - [ ] `algorithm_version` (text)
  - [ ] `run_at` (timestamp)

---

## 📋 Phase 1: Data Filtering & Eligibility

### 1.1 Listing Eligibility Filter
- [ ] Create function `is_listing_pair_eligible(listing: Dict) -> bool`
  - [ ] Check `property_type != 'private_room'` (or == 'entire_place')
  - [ ] Check `number_of_bedrooms >= 2`
  - [ ] Check `status NOT IN ('draft', 'archived', 'inactive')`
  - [ ] Check `accepts_groups != false` (when field exists)
  - [ ] Validate has valid city, price, coordinates
- [ ] Create function `get_eligible_listings(city: str) -> List[Dict]`
  - [ ] Fetch from Supabase with filters
  - [ ] Apply eligibility checks
  - [ ] Deduplicate (same address + host + price → keep newest)
  - [ ] Return parsed, eligible listings

### 1.2 Group Eligibility Filter
- [ ] Create function `is_group_eligible(group: Dict) -> bool`
  - [ ] Check `target_group_size == 2` (strict)
  - [ ] Check `status == 'active'`
  - [ ] Check has valid `target_city`, `budget_per_person_min`, `budget_per_person_max`
  - [ ] Check has valid `target_move_in_date`
  - [ ] Validate budget_min <= budget_max
- [ ] Create function `get_eligible_groups(city: str) -> List[Dict]`
  - [ ] Fetch from Supabase with filters
  - [ ] Include group_members data
  - [ ] Apply eligibility checks
  - [ ] Return parsed, eligible groups

### 1.3 Date Window Partitioning
- [ ] Create function `get_move_in_windows(groups: List[Dict]) -> List[DateWindow]`
  - [ ] Group by city
  - [ ] For each city, create windows around target dates (±60 days)
  - [ ] Merge overlapping windows
  - [ ] Return list of (city, start_date, end_date, groups_in_window)

---

## 📋 Phase 2: Build Feasible Pairs (Hard Constraints)

### 2.1 Location Matching
- [ ] Create function `location_matches(group: Dict, listing: Dict) -> bool`
  - [ ] Check `group.target_city == listing.city` (case-insensitive, normalized)
  - [ ] Check `group.target_country == listing.country` (or both USA)
  - [ ] Optional: Check `target_state_province == state_province`

### 2.2 Date Matching
- [ ] Create function `date_matches(group: Dict, listing: Dict, delta_days: int = 30) -> bool`
  - [ ] Get `g_date = group.target_move_in_date`
  - [ ] Get listing window: `[available_from, available_to or +infinity]`
  - [ ] Check: `available_from - delta <= g_date <= (available_to or +infinity) + delta`

### 2.3 Price Matching
- [ ] Create function `price_matches(group: Dict, listing: Dict) -> bool`
  - [ ] Calculate `per_person_price = listing.price_per_month / 2`
  - [ ] Check: `budget_per_person_min <= per_person_price <= budget_per_person_max`

### 2.4 Hard Attributes Matching
- [ ] Create function `hard_attributes_match(group: Dict, listing: Dict) -> bool`
  - [ ] If `group.target_furnished == true`, require `listing.furnished == true`
  - [ ] If `group.target_utilities_included == true`, require `listing.utilities_included == true`
  - [ ] Check strict amenities (pets_allowed, parking, air_conditioning)
  - [ ] Return true only if all hard requirements met

### 2.5 Feasible Pairs Builder
- [ ] Create function `build_feasible_pairs(groups: List, listings: List) -> List[Tuple[group_id, listing_id]]`
  - [ ] For each (group, listing) combination:
    - [ ] Check location_matches()
    - [ ] Check date_matches()
    - [ ] Check price_matches()
    - [ ] Check hard_attributes_match()
  - [ ] Only return pairs that pass ALL checks
  - [ ] Store rejection reasons for diagnostics

---

## 📋 Phase 3: Two-Sided Scoring

### 3.1 Group → Listing Score (S_g(l))
- [ ] Create function `calculate_group_score(group: Dict, listing: Dict) -> float`
  - [ ] **Price fit score** (0-100 points)
    - [ ] Calculate distance from per_person_price to budget midpoint
    - [ ] Closer to midpoint = higher score
  - [ ] **Date fit score** (0-100 points)
    - [ ] Calculate |g_date - available_from|
    - [ ] Bonus if within ±7 days
    - [ ] Smaller distance = higher score
  - [ ] **Amenities fit score** (0-100 points)
    - [ ] Weight: laundry (20), AC (15), parking (15), dishwasher (10), wifi (20), furnished (20)
    - [ ] Match group preferences to listing amenities
  - [ ] **Listing quality score** (0-100 points)
    - [ ] Newer created_at (timestamp score)
    - [ ] Photo completeness (future: count photos)
    - [ ] Host verification (future)
  - [ ] **Total score:** Weighted sum with configurable weights
  - [ ] Return normalized score (0-1000)

### 3.2 Listing → Group Score (S_l(g))
- [ ] Create function `calculate_listing_score(listing: Dict, group: Dict) -> float`
  - [ ] **Verification trust score** (0-100 points)
    - [ ] Fetch group members from `group_members` table
    - [ ] Join with `users` table to get `verification_status`
    - [ ] Calculate: verified_count / total_members
  - [ ] **Group readiness score** (0-100 points)
    - [ ] Check: len(group_members) == target_group_size
    - [ ] Check: status == 'active'
    - [ ] Full points if both true
  - [ ] **Date alignment score** (0-100 points)
    - [ ] Same calculation as group → listing date fit
  - [ ] **House rules fit score** (0-100 points, future)
    - [ ] Match common rules (quiet hours, smoking, guests)
  - [ ] **Total score:** Weighted sum with configurable weights
  - [ ] Return normalized score (0-1000)

### 3.3 Ranking & Tie-Breaking
- [ ] Create function `rank_listings_for_group(group: Dict, feasible_listings: List) -> List[Tuple[listing_id, rank, score]]`
  - [ ] Score all feasible listings for this group
  - [ ] Sort by score DESC
  - [ ] Tie-break: newer listing, then lower price, then UUID
  - [ ] Return ordered list with ranks (1, 2, 3, ...)

- [ ] Create function `rank_groups_for_listing(listing: Dict, feasible_groups: List) -> List[Tuple[group_id, rank, score]]`
  - [ ] Score all feasible groups for this listing
  - [ ] Sort by score DESC
  - [ ] Tie-break: higher verified share, then earlier target_date, then UUID
  - [ ] Return ordered list with ranks (1, 2, 3, ...)

### 3.4 Build Preference Lists
- [ ] Create function `build_preference_lists(feasible_pairs, groups, listings) -> Tuple[Dict, Dict]`
  - [ ] For each group: build ranked preference list of listings
  - [ ] For each listing: build ranked preference list of groups
  - [ ] Return: (group_preferences, listing_preferences)

---

## 📋 Phase 4: Deferred Acceptance Algorithm

### 4.1 Core DA Implementation
- [ ] Create function `run_deferred_acceptance(group_prefs: Dict, listing_prefs: Dict) -> Dict[group_id, listing_id]`
  - [ ] Initialize:
    - [ ] `free_groups = set(all_group_ids)`
    - [ ] `group_next_proposal = {group_id: 0 for each group}`  # index in preference list
    - [ ] `listing_held_proposal = {}` # listing_id -> (group_id, rank)
  - [ ] **Main loop** (while free_groups is not empty):
    - [ ] Pick a free group `g`
    - [ ] Get next listing `l` from g's preference list (at index group_next_proposal[g])
    - [ ] If no more listings in g's list: mark g as permanently unmatched, remove from free_groups
    - [ ] Else:
      - [ ] Increment `group_next_proposal[g]`
      - [ ] **If listing `l` has no held proposal yet:**
        - [ ] `listing_held_proposal[l] = (g, rank_of_g_for_l)`
        - [ ] Remove g from free_groups
      - [ ] **Else (listing `l` already holding a proposal from group `g_old`):**
        - [ ] Compare ranks: `rank_of_g_for_l` vs `rank_of_g_old_for_l`
        - [ ] If g is preferred (lower rank number):
          - [ ] Reject g_old: add g_old back to free_groups
          - [ ] Accept g: `listing_held_proposal[l] = (g, rank_of_g_for_l)`, remove g from free_groups
        - [ ] Else:
          - [ ] Reject g: stays in free_groups (will propose to next listing)
  - [ ] **Return:** final matches from listing_held_proposal

### 4.2 Stability Verification (Testing)
- [ ] Create function `verify_stability(matches: Dict, group_prefs: Dict, listing_prefs: Dict) -> bool`
  - [ ] For each unmatched (group, listing) pair:
    - [ ] Check if group prefers listing over its match
    - [ ] Check if listing prefers group over its match
    - [ ] If both true: return False (blocking pair exists)
  - [ ] If no blocking pairs found: return True (stable)

---

## 📋 Phase 5: Output & Persistence

### 5.1 Match Explanation Generator
- [ ] Create function `generate_match_explanations(group: Dict, listing: Dict, scores: Dict) -> List[str]`
  - [ ] Price explanation: "Price per person $X fits your range: $A–$B"
  - [ ] Date explanation: "Move-in is N days from your target"
  - [ ] Amenities explanation: "Laundry + AC + parking match your preferences"
  - [ ] Verification explanation: "2/2 group members verified"
  - [ ] Return top 3-4 most relevant reasons

### 5.2 Unmatched Reasons Generator
- [ ] Create function `generate_unmatched_reasons(group: Dict, all_listings: List) -> Dict`
  - [ ] Track why group couldn't match:
    - [ ] No feasible pairs (count by: location, date, price, attributes)
    - [ ] Feasible but not preferred by listings (rejected by all)
    - [ ] Top 5 near-misses (listings that almost matched)
  - [ ] Return structured breakdown

### 5.3 Save Matches to Database
- [ ] Create function `save_matches_to_db(matches: Dict, match_round_id: str, metadata: Dict)`
  - [ ] For each (group_id, listing_id) in matches:
    - [ ] Get group and listing scores
    - [ ] Get ranks
    - [ ] Generate explanations
    - [ ] Insert into `stable_matches` table
  - [ ] Set status = 'active'
  - [ ] Store match_round_id for tracking

### 5.4 Save Diagnostics
- [ ] Create function `save_diagnostics(match_round_id: str, city: str, window: DateWindow, results: Dict)`
  - [ ] Calculate metrics:
    - [ ] Match rate: matched_groups / total_groups
    - [ ] Median rank of matched listings for groups
    - [ ] Top-3 rate: % of groups that got top-3 choice
    - [ ] Unmatched reasons breakdown
    - [ ] Average verification rate of matched groups
  - [ ] Insert into `match_diagnostics` table

---

## 📋 Phase 6: API Endpoints

### 6.1 Admin/Batch Endpoints
- [ ] `POST /api/matching/run-batch`
  - [ ] Body: `{ "city": "San Francisco", "force_rerun": false }`
  - [ ] Run matching for specified city
  - [ ] Return match_round_id and summary stats

- [ ] `POST /api/matching/run-all-cities`
  - [ ] Iterate through all cities with active groups
  - [ ] Run batch matching for each
  - [ ] Return summary for all cities

### 6.2 Group-Facing Endpoints
- [ ] `GET /api/matches/groups/{group_id}/stable-matches`
  - [ ] Return active stable matches for this group
  - [ ] Include explanations and match details
  - [ ] Return unmatched reasons if no matches

- [ ] `POST /api/matches/groups/{group_id}/find-matches`
  - [ ] On-demand matching for specific group
  - [ ] Run against current listings
  - [ ] Return top 10 matches with explanations

- [ ] `GET /api/matches/groups/{group_id}/diagnostics`
  - [ ] Show why group was/wasn't matched
  - [ ] Show near-misses
  - [ ] Show what they could change to get more matches

### 6.3 Listing-Facing Endpoints
- [ ] `GET /api/matches/listings/{listing_id}/stable-matches`
  - [ ] Return groups matched to this listing
  - [ ] Include group verification details

- [ ] `POST /api/matches/listings/{listing_id}/veto-group`
  - [ ] Allow host to veto a specific group
  - [ ] Trigger re-matching

### 6.4 Analytics Endpoints
- [ ] `GET /api/matching/diagnostics/{match_round_id}`
  - [ ] Return full diagnostics for a match round

- [ ] `GET /api/matching/city-stats/{city}`
  - [ ] Return latest matching stats for city
  - [ ] Match rates, trends, reasons

---

## 📋 Phase 7: Triggers & Automation

### 7.1 Re-matching Triggers
- [ ] Create webhook/trigger for listing changes:
  - [ ] Monitor: `price_per_month`, `available_from`, `available_to`, `furnished`, `utilities_included`, `amenities`, `status`
  - [ ] On change: Mark affected city for re-match
  
- [ ] Create webhook/trigger for group changes:
  - [ ] Monitor: `budget_per_person_*`, `target_move_in_date`, group_members, `status`
  - [ ] On change: Mark affected city for re-match

### 7.2 Scheduled Matching
- [ ] Create cron job/scheduled task:
  - [ ] Run daily at off-peak hours
  - [ ] Check cities marked for re-match
  - [ ] Run batch matching
  - [ ] Notify affected groups of new matches

### 7.3 Match Expiration
- [ ] Create function to expire old matches:
  - [ ] After 7 days, mark matches as 'expired' if not accepted
  - [ ] Notify groups
  - [ ] Trigger re-matching

---

## 📋 Phase 8: Edge Cases & Validation

### 8.1 Input Validation
- [ ] Validate budget: min <= max, both not null
- [ ] Validate dates: target_move_in_date not in past
- [ ] Validate city: normalize case, handle aliases (SF, San Francisco)
- [ ] Validate group_size: must be exactly 2 for this algorithm
- [ ] Validate listing: number_of_bedrooms >= 2

### 8.2 Edge Case Handlers
- [ ] Handle `available_to = null`: treat as open-ended
- [ ] Handle missing amenities: treat as false
- [ ] Handle zero feasible pairs: provide actionable feedback
- [ ] Handle all groups rejected: provide near-miss analysis
- [ ] Handle duplicate matches: deduplicate, keep latest

### 8.3 Data Quality Checks
- [ ] Flag outlier prices (e.g., < $100 or > $50,000)
- [ ] Flag invalid coordinates (lat/lon out of bounds)
- [ ] Flag stale listings (created_at > 1 year ago)
- [ ] Flag incomplete data (missing required fields)

---

## 📋 Phase 9: Testing & Validation

### 9.1 Unit Tests
- [ ] Test eligibility filters (listings, groups)
- [ ] Test hard constraint matching (location, date, price, attributes)
- [ ] Test scoring functions (group → listing, listing → group)
- [ ] Test ranking with tie-breaks
- [ ] Test DA algorithm with small examples
- [ ] Test stability verification

### 9.2 Integration Tests
- [ ] Test full matching pipeline with mock data
- [ ] Test with real database (12 groups, 123 listings)
- [ ] Test API endpoints
- [ ] Test triggers and re-matching

### 9.3 Algorithm Validation
- [ ] Verify stability of all matches
- [ ] Verify deterministic results (same input → same output)
- [ ] Compare match quality metrics across runs
- [ ] Test with edge cases (0 matches, 100% matches)

### 9.4 Performance Tests
- [ ] Test with 100 groups, 500 listings
- [ ] Test with 1000 groups, 5000 listings
- [ ] Measure time complexity
- [ ] Identify bottlenecks

---

## 📋 Phase 10: UI/UX Integration

### 10.1 Group Match Display
- [ ] Show "Stable Match ✅" badge
- [ ] Display match explanations (2-3 reasons)
- [ ] Show match rank ("Your #2 choice")
- [ ] Show listing details
- [ ] "Accept" / "Reject" buttons

### 10.2 Unmatched Feedback
- [ ] Show why no matches found
- [ ] Show top 5 near-misses
- [ ] Suggest adjustments (budget, date flexibility)
- [ ] "Find more" button for on-demand search

### 10.3 Diagnostics Dashboard (Admin)
- [ ] City-level match rates
- [ ] Trending metrics
- [ ] Unmatched reasons breakdown
- [ ] Algorithm performance metrics
- [ ] Re-run controls

---

## 📋 Phase 11: Configuration & Tuning

### 11.1 Configurable Parameters
- [ ] Create config file/table for:
  - [ ] `date_window_delta` (default: 30 days)
  - [ ] `match_expiration_days` (default: 7)
  - [ ] Scoring weights for each factor
  - [ ] Hard constraint toggles
  - [ ] City aliases mapping

### 11.2 A/B Testing Setup
- [ ] Track match acceptance rates
- [ ] Track user engagement with matches
- [ ] Compare different scoring weights
- [ ] Compare different orientations (groups-propose vs listings-propose)

---

## 📋 Phase 12: Documentation

### 12.1 Technical Docs
- [ ] Algorithm explanation with examples
- [ ] API documentation
- [ ] Database schema documentation
- [ ] Scoring formula documentation

### 12.2 User Docs
- [ ] How stable matching works (user-friendly)
- [ ] Why you got matched with listing X
- [ ] How to improve match quality
- [ ] FAQ

---

## ✅ Acceptance Criteria (v1 Launch)

- [ ] Every matched pair passes ALL hard constraints
- [ ] Every match is labeled "Stable match ✅"
- [ ] Every unmatched group has explanations + top 5 near-misses
- [ ] Metrics dashboard shows:
  - [ ] Match rate by city
  - [ ] Average/median group rank
  - [ ] Reason breakdown for unmatched
  - [ ] Verification distribution
- [ ] Algorithm is deterministic (same input → same output)
- [ ] Stability is verified for all match rounds
- [ ] API response time < 2 seconds for batch matching (100 groups)
- [ ] Full test coverage (>80%)

---

## 🚀 Implementation Order (Recommended)

1. **Phase 1-2**: Data filtering & feasible pairs (foundation)
2. **Phase 3**: Scoring system (can tune weights later)
3. **Phase 4**: DA algorithm (core logic)
4. **Phase 5**: Persistence & explanations
5. **Phase 8**: Edge cases & validation
6. **Phase 9**: Testing (parallel with above)
7. **Phase 6**: API endpoints
8. **Phase 7**: Triggers & automation
9. **Phase 10-12**: UI/UX & docs

---

**Estimated Complexity:** ~2-3 weeks for v1 (with testing)  
**Current Scale:** 12 groups × 123 listings = trivial (instant)  
**Future Scale:** Should handle 1000s of groups per city efficiently
