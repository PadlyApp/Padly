# 🎯 Stable Matching Algorithm Implementation - TODO List

**Algorithm Type:** Deferred Acceptance (Gale-Shapley)  
**Orientation:** Groups-proposing (renter-friendly)  
**Scope:** 2-person groups → entire-unit listings  
**Date:** November 11, 2025

---

## 📋 Phase 0: Database Schema & Setup ✅ **COMPLETE**

**Status**: Fully implemented and tested  
**Documentation**: `PHASE_0_1_COMPLETE.md`  
**Schema File**: `app/schemas/stable_matching_schema.sql`

### 0.1 Database Changes
- [x] Add `accepts_groups` boolean flag to `listings` table (optional, default true)
- [x] Add `max_occupancy` integer to `listings` table (optional)
- [x] Create `stable_matches` table with fields:
  - [x] `id` (uuid, primary key)
  - [x] `group_id` (uuid, foreign key to roommate_groups)
  - [x] `listing_id` (uuid, foreign key to listings)
  - [x] `match_round_id` (uuid, for tracking batch runs)
  - [x] `orientation` (text, e.g., "groups-proposing")
  - [x] `city` (text)
  - [x] `match_window_start` (date)
  - [x] `match_window_end` (date)
  - [x] `group_rank_of_listing` (integer, what rank was this listing for the group)
  - [x] `listing_rank_of_group` (integer, what rank was this group for the listing)
  - [x] `group_score` (numeric, S_g(l) score)
  - [x] `listing_score` (numeric, S_l(g) score)
  - [x] `explanation_reasons` (jsonb, array of reason strings)
  - [x] `created_at` (timestamp)
  - [x] `expires_at` (timestamp, optional)
  - [x] `status` (text: 'active', 'accepted', 'rejected', 'expired')

### 0.2 Indexes
- [x] Index on `stable_matches(group_id, status)`
- [x] Index on `stable_matches(listing_id, status)`
- [x] Index on `stable_matches(match_round_id)`
- [x] Index on `listings(city, status)`
- [x] Index on `roommate_groups(target_city, status, target_group_size)`

### 0.3 Match Diagnostics Table
- [x] Create `match_diagnostics` table:
  - [x] `match_round_id` (uuid)
  - [x] `city` (text)
  - [x] `window_start` (date)
  - [x] `window_end` (date)
  - [x] `total_groups` (integer)
  - [x] `total_listings` (integer)
  - [x] `matched_groups` (integer)
  - [x] `matched_listings` (integer)
  - [x] `match_rate_pct` (numeric)
  - [x] `median_group_rank` (integer)
  - [x] `top_3_rate_pct` (numeric)
  - [x] `unmatched_reasons` (jsonb, breakdown by reason)
  - [x] `avg_verification_rate` (numeric)
  - [x] `algorithm_version` (text)
  - [x] `run_at` (timestamp)

---

## 📋 Phase 1: Data Filtering & Eligibility ✅ **COMPLETE**

**Status**: Fully implemented and tested  
**Documentation**: `PHASE_0_1_COMPLETE.md`  
**Test Results**: `phase_0_1_test_results.json`  
**Code**: `app/services/stable_matching/filters.py` (480+ lines)

### 1.1 Listing Eligibility Filter
- [x] Create function `is_listing_pair_eligible(listing: Dict) -> bool`
  - [x] Check `property_type != 'private_room'` (or == 'entire_place')
  - [x] Check `number_of_bedrooms >= 2`
  - [x] Check `status NOT IN ('draft', 'archived', 'inactive')`
  - [x] Check `accepts_groups != false` (when field exists)
  - [x] Validate has valid city, price, coordinates
- [x] Create function `get_eligible_listings(city: str) -> List[Dict]`
  - [x] Fetch from Supabase with filters
  - [x] Apply eligibility checks
  - [x] Deduplicate (same address + host + price → keep newest)
  - [x] Return parsed, eligible listings

### 1.2 Group Eligibility Filter
- [x] Create function `is_group_eligible(group: Dict) -> bool`
  - [x] Check `target_group_size == 2` (strict)
  - [x] Check `status == 'active'`
  - [x] Check has valid `target_city`, `budget_per_person_min`, `budget_per_person_max`
  - [x] Check has valid `target_move_in_date`
  - [x] Validate budget_min <= budget_max
- [x] Create function `get_eligible_groups(city: str) -> List[Dict]`
  - [x] Fetch from Supabase with filters
  - [x] Include group_members data
  - [x] Apply eligibility checks
  - [x] Return parsed, eligible groups

### 1.3 Date Window Partitioning
- [x] Create function `get_move_in_windows(groups: List[Dict]) -> List[DateWindow]`
  - [x] Group by city
  - [x] For each city, create windows around target dates (±60 days)
  - [x] Merge overlapping windows
  - [x] Return list of (city, start_date, end_date, groups_in_window)

---

## 📋 Phase 2: Build Feasible Pairs (Hard Constraints) ✅ **COMPLETE**

**Status**: Fully implemented and tested  
**Documentation**: `PHASE_2_COMPLETE.md`  
**Test Results**: `phase_2_test_results.json`  
**Code**: `app/services/stable_matching/feasible_pairs.py` (390+ lines)

### 2.1 Location Matching
- [x] Create function `location_matches(group: Dict, listing: Dict) -> bool`
  - [x] Check `group.target_city == listing.city` (case-insensitive, normalized)
  - [x] Check `group.target_country == listing.country` (or both USA)
  - [x] Optional: Check `target_state_province == state_province`

### 2.2 Date Matching
- [x] Create function `date_matches(group: Dict, listing: Dict, delta_days: int = 30) -> bool`
  - [x] Get `g_date = group.target_move_in_date`
  - [x] Get listing window: `[available_from, available_to or +infinity]`
  - [x] Check: `available_from - delta <= g_date <= (available_to or +infinity) + delta`

### 2.3 Price Matching
- [x] Create function `price_matches(group: Dict, listing: Dict) -> bool`
  - [x] Calculate `per_person_price = listing.price_per_month / 2`
  - [x] Check: `budget_per_person_min <= per_person_price <= budget_per_person_max`

### 2.4 Hard Attributes Matching
- [x] Create function `hard_attributes_match(group: Dict, listing: Dict) -> bool`
  - [x] If `group.target_furnished == true`, require `listing.furnished == true`
  - [x] If `group.target_utilities_included == true`, require `listing.utilities_included == true`
  - [x] Check strict amenities (pets_allowed, parking, air_conditioning)
  - [x] Return true only if all hard requirements met

### 2.5 Feasible Pairs Builder
- [x] Create function `build_feasible_pairs(groups: List, listings: List) -> List[Tuple[group_id, listing_id]]`
  - [x] For each (group, listing) combination:
    - [x] Check location_matches()
    - [x] Check date_matches()
    - [x] Check price_matches()
    - [x] Check hard_attributes_match()
  - [x] Only return pairs that pass ALL checks
  - [x] Store rejection reasons for diagnostics

---

## 📋 Phase 3: Two-Sided Scoring ✅ **COMPLETE**

**Status**: Fully implemented and tested  
**Documentation**: `PHASE_3_COMPLETE.md`  
**Test Results**: `phase_3_test_results.json`  
**Code**: `app/services/stable_matching/scoring.py` (650+ lines)

### 3.1 Group → Listing Score (S_g(l))
- [x] Create function `calculate_group_score(group: Dict, listing: Dict) -> float`
  - [x] **Price fit score** (0-100 points)
    - [x] Calculate distance from per_person_price to budget midpoint
    - [x] Closer to midpoint = higher score
  - [x] **Date fit score** (0-100 points)
    - [x] Calculate |g_date - available_from|
    - [x] Bonus if within ±7 days
    - [x] Smaller distance = higher score
  - [x] **Amenities fit score** (0-100 points)
    - [x] Weight: laundry (20), AC (15), parking (15), dishwasher (10), wifi (20), furnished (20)
    - [x] Match group preferences to listing amenities
  - [x] **Listing quality score** (0-100 points)
    - [x] Newer created_at (timestamp score)
    - [x] Photo completeness (future: count photos)
    - [x] Host verification (future)
  - [x] **Total score:** Weighted sum with configurable weights
  - [x] Return normalized score (0-1000)

### 3.2 Listing → Group Score (S_l(g))
- [x] Create function `calculate_listing_score(listing: Dict, group: Dict) -> float`
  - [x] **Verification trust score** (0-100 points)
    - [x] Fetch group members from `group_members` table
    - [x] Join with `users` table to get `verification_status`
    - [x] Calculate: verified_count / total_members
  - [x] **Group readiness score** (0-100 points)
    - [x] Check: len(group_members) == target_group_size
    - [x] Check: status == 'active'
    - [x] Full points if both true
  - [x] **Date alignment score** (0-100 points)
    - [x] Same calculation as group → listing date fit
  - [x] **House rules fit score** (0-100 points, future)
    - [x] Match common rules (quiet hours, smoking, guests)
  - [x] **Total score:** Weighted sum with configurable weights
  - [x] Return normalized score (0-1000)

### 3.3 Ranking & Tie-Breaking
- [x] Create function `rank_listings_for_group(group: Dict, feasible_listings: List) -> List[Tuple[listing_id, rank, score]]`
  - [x] Score all feasible listings for this group
  - [x] Sort by score DESC
  - [x] Tie-break: newer listing, then lower price, then UUID
  - [x] Return ordered list with ranks (1, 2, 3, ...)

- [x] Create function `rank_groups_for_listing(listing: Dict, feasible_groups: List) -> List[Tuple[group_id, rank, score]]`
  - [x] Score all feasible groups for this listing
  - [x] Sort by score DESC
  - [x] Tie-break: higher verified share, then earlier target_date, then UUID
  - [x] Return ordered list with ranks (1, 2, 3, ...)

### 3.4 Build Preference Lists
- [x] Create function `build_preference_lists(feasible_pairs, groups, listings) -> Tuple[Dict, Dict]`
  - [x] For each group: build ranked preference list of listings
  - [x] For each listing: build ranked preference list of groups
  - [x] Return: (group_preferences, listing_preferences)

---

## 📋 Phase 4: Deferred Acceptance Algorithm ✅ **COMPLETE**

**Status**: Fully implemented and tested  
**Test Results**: `phase_4_test_results.json` (5/5 tests passing, 100%)  
**Code**: `app/services/stable_matching/deferred_acceptance.py` (520+ lines)

### 4.1 Core DA Implementation
- [x] Create class `DeferredAcceptanceEngine`
  - [x] Initialize with preference lists from Phase 3
  - [x] Track state: free_groups, current_matches, proposal_index per group
- [x] Implement main loop:
  - [x] While free groups exist:
    - [x] Pick a free group
    - [x] Get next listing on group's preference list
    - [x] Group proposes to listing
    - [x] Listing compares with current match (if any)
    - [x] Listing accepts best, rejects others
    - [x] Rejected groups become free again
- [x] Implement termination: when no free group wants to propose

### 4.2 Stability Verification
- [x] Create function `verify_stability(matches, preference_lists) -> bool`
  - [x] For each (group, listing) pair not matched:
    - [x] Check if group prefers this listing over current match
    - [x] Check if listing prefers this group over current match
    - [x] If both true → blocking pair found → return False
  - [x] If no blocking pairs → return True

### 4.3 Match Result Generation
- [x] Create function `generate_match_results(final_matches) -> List[MatchResult]`
  - [x] For each match, create MatchResult with:
    - [x] group_id, listing_id
    - [x] group_score, listing_score (from preference lists)
    - [x] group_rank, listing_rank (position in preference lists)
    - [x] matched_at timestamp
    - [x] is_stable flag

### 4.4 Diagnostic Metrics
- [x] Create function `generate_diagnostics() -> DiagnosticMetrics`
  - [x] Calculate: matched_groups, unmatched_groups
  - [x] Calculate: matched_listings, unmatched_listings
  - [x] Track: proposals_sent, proposals_rejected
  - [x] Calculate: avg_group_rank, avg_listing_rank
  - [x] Calculate: match_quality_score
  - [x] Store city, date_window, timestamp

---

## 📋 Phase 5: Database Persistence ✅ **COMPLETE**

**Status**: Implementation complete (schema needs DB application)  
**Documentation**: `PHASE_5_COMPLETE.md`  
**Code**: `app/services/stable_matching/persistence.py` (450+ lines)  
**Schema**: `app/schemas/stable_matching_schema.sql` (updated)

### 5.1 Save Matches to Database
- [x] Create function `save_matches(matches, diagnostics, supabase_client)`
  - [x] Save diagnostics to match_diagnostics table
  - [x] Save each match to stable_matches table
  - [x] Use batch inserts for performance (100 at a time)
  - [x] Handle transaction rollback on failure
- [x] Return: saved_count, diagnostics_id

### 5.2 Retrieve Matches
- [x] Create function `get_active_matches(city, group_id, listing_id)`
  - [x] Query stable_matches table
  - [x] Filter by status = 'active'
  - [x] Filter by city, group, or listing if provided
  - [x] Order by group_rank (best matches first)
- [x] Create function `get_match_for_group(group_id)`
  - [x] Return single match for a group
- [x] Create function `get_match_for_listing(listing_id)`
  - [x] Return single match for a listing

### 5.3 Match Management
- [x] Create function `expire_old_matches(days_threshold=30)`
  - [x] Update status to 'expired' for old matches
  - [x] Return count of expired matches
- [x] Create function `delete_matches_for_group(group_id)`
  - [x] Use case: group dissolved or preferences changed
- [x] Create function `delete_matches_for_listing(listing_id)`
  - [x] Use case: listing removed or became unavailable

**Note**: Schema must be applied via Supabase Dashboard before testing. See `PHASE_5_COMPLETE.md` for instructions.

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
