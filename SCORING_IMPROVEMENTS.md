# Scoring System Improvements

**Branch:** `neural_net`
**Status:** Proposed
**Last Updated:** 2026-02-10

---

## 1. Current State Analysis

### Hard Constraints (13 total) — ✅ Solid

These act as a binary gate. If any fail, the listing is eliminated entirely.

| # | Constraint | Logic | Verdict |
|---|---|---|---|
| 1 | City match | Exact string match | ✅ Good |
| 2 | State/Province | Match if both specified | ✅ Good |
| 3 | Country | Match (defaults to USA) | ✅ Good |
| 4 | Budget range | Price/person within min–max (+$100 buffer) | ✅ Good |
| 5 | Move-in date | Within ±30 days of target | ✅ Good |
| 6 | Bedrooms | Must meet group requirement | ✅ Good |
| 7 | Lease type | Must match if specified | ✅ Good |
| 8 | Lease duration | Must be compatible | ✅ Good |
| 9 | Furnished | Required → must be furnished | ✅ Good |
| 10 | Utilities included | Required → must include | ✅ Good |
| 11 | Pets allowed | Required → must allow | ✅ Good |
| 12 | Parking | Required → must have | ✅ Good |
| 13 | Air conditioning | Required → must have | ✅ Good |

**Assessment:** Hard constraints are well-implemented. No changes recommended.

---

### Soft Constraints (5 total) — ⚠️ Needs Improvement

These score each feasible group↔listing pair on a scale of 0–100 and determine preference list ordering for Gale-Shapley.

| # | Constraint | Weight | Scoring Logic | Issue |
|---|---|---|---|---|
| 1 | Bathrooms | 20 pts | Meets/exceeds=20, within 0.5=10, else=5 | Overweighted for student housing |
| 2 | Furnished | 20 pts | Match=20, mismatch=10 | Only 10-pt swing — barely differentiates |
| 3 | Utilities included | 20 pts | Match=20, mismatch=10 | Same problem — 10-pt swing is weak |
| 4 | Deposit amount | 20 pts | At/below=20, +$500=10, +$1500=5, else=0 | Good tiers, but underweighted (deposit is huge for students) |
| 5 | House rules | 20 pts | No conflicts=20, 1-2=10, 3+=0 | Good logic, fair weight |

**Total: 100 points across 5 factors.**

---

## 2. Problems Identified

### Problem 1: Missing High-Impact Factors

The soft scoring completely ignores several factors that heavily influence student housing decisions:

| Missing Factor | Impact Level | Why It Matters |
|---|---|---|
| **Location within city** (proximity to campus/work) | 🔴 Critical | A listing 5 min from UTM vs. 45 min away — same city, completely different desirability |
| **Transit accessibility** | 🔴 Critical | Students without cars depend on bus/subway proximity |
| **Neighborhood quality** | 🟡 High | Safety, walkability, nearby amenities (grocery, gym) |
| **Listing completeness/quality** | 🟡 High | Listings with 8 photos and detailed descriptions signal trustworthy landlords |
| **Price efficiency** | 🟡 High | How close to the bottom of the budget range (cheaper = better, all else equal) |
| **Move-in date closeness** | 🟢 Medium | Exact date match > 25 days off (currently binary pass/fail at ±30 days) |
| **Lease duration flexibility** | 🟢 Medium | 4-month sublet for an internship vs. 12-month lease |

### Problem 2: Equal Weights Don't Reflect Reality

Every student housing survey shows the same ranking:

```
1. Price/budget fit        ← already a hard constraint, but within-budget ranking matters
2. Location/commute        ← NOT IN SCORING AT ALL
3. Safety/neighborhood     ← NOT IN SCORING AT ALL
4. House rules/lifestyle   ← in scoring, fairly weighted
5. Amenities (furnished, utilities, etc.) ← in scoring, overweighted
6. Bathrooms               ← in scoring, significantly overweighted
```

Bathrooms (currently 20% of the total score) is one of the **least** important factors for students, yet it carries the same weight as house rules (one of the **most** important).

### Problem 3: Low Score Differentiation

Consider two listings that both pass hard constraints:

| Factor | Listing A | Listing B | Score A | Score B |
|---|---|---|---|---|
| Bathrooms (target: 1) | 1 | 1.5 | 20 | 20 |
| Furnished (wants: yes) | Yes | No | 20 | 10 |
| Utilities (wants: yes) | Yes | Yes | 20 | 20 |
| Deposit (target: $500) | $400 | $600 | 20 | 20 |
| House rules | No conflicts | No conflicts | 20 | 20 |
| **Total** | | | **100** | **90** |

A 10-point difference. But what if Listing A is 45 minutes from campus and Listing B is a 5-minute walk? The current system would rank Listing A higher, which is clearly wrong.

### Problem 4: Furnished/Utilities Scoring Is Redundant

These two factors exist in **both** hard and soft constraints:
- **Hard:** If the user *requires* furnished → unfurnished listings get eliminated
- **Soft:** Furnished match = 20, mismatch = 10

If the user set furnished as a hard requirement, they'll never see unfurnished listings, so the soft score always gives 20/20. If they didn't set it as a hard requirement, the 10-pt swing (20 vs. 10) barely matters. These factors contribute very little actual ranking signal.

---

## 3. Proposed Improvements

### 3.1 Expanded Scoring Categories

Replace the current 5-factor system with a **9-factor system** that captures what actually matters:

```
NEW SCORING SYSTEM (0-100 total)
═══════════════════════════════════════════════════════

TIER 1: HIGH IMPACT (60 pts total)
├── Location Proximity ............. 25 pts  [NEW]
├── Price Efficiency ............... 15 pts  [NEW]
└── House Rules Compatibility ...... 20 pts  [KEPT — same weight]

TIER 2: MEDIUM IMPACT (30 pts total)
├── Deposit Amount ................. 15 pts  [REDUCED from 20]
├── Listing Quality ................ 10 pts  [NEW]
└── Move-in Date Closeness ......... 5 pts   [NEW]

TIER 3: LOW IMPACT (10 pts total)
├── Bathrooms ...................... 4 pts   [REDUCED from 20]
├── Furnished ...................... 3 pts   [REDUCED from 20]
└── Utilities Included ............. 3 pts   [REDUCED from 20]
```

---

### 3.2 New Scoring Functions

#### A. Location Proximity Score (25 pts) — NEW, highest weight

Uses latitude/longitude (already in `listings` table) to calculate distance from user's target.

```python
import math

def calculate_location_proximity_score(group: dict, listing: dict) -> float:
    """
    Score based on distance between listing and user's target location.
    
    Uses Haversine formula for lat/lng distance.
    If user has no target coordinates, falls back to neighborhood match.
    
    Scoring:
        < 1 km:   25 pts  (walking distance)
        1-3 km:   20 pts  (short bike/bus)
        3-5 km:   15 pts  (reasonable commute)
        5-10 km:  10 pts  (moderate commute)
        10-20 km:  5 pts  (long commute)
        > 20 km:   2 pts  (very far)
    """
    user_lat = group.get('target_latitude')
    user_lng = group.get('target_longitude')
    listing_lat = listing.get('latitude')
    listing_lng = listing.get('longitude')
    
    # If coordinates missing, give neutral score
    if not all([user_lat, user_lng, listing_lat, listing_lng]):
        return 12  # Neutral middle score
    
    # Haversine distance in km
    distance_km = haversine(user_lat, user_lng, listing_lat, listing_lng)
    
    if distance_km < 1:
        return 25
    elif distance_km < 3:
        return 20
    elif distance_km < 5:
        return 15
    elif distance_km < 10:
        return 10
    elif distance_km < 20:
        return 5
    else:
        return 2


def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two lat/lng points in kilometers."""
    R = 6371  # Earth's radius in km
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = (math.sin(dlat/2)**2 + 
         math.cos(math.radians(float(lat1))) * 
         math.cos(math.radians(float(lat2))) * 
         math.sin(dlon/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c
```

**Database change needed:**
```sql
-- Add target coordinates to personal_preferences
ALTER TABLE personal_preferences ADD COLUMN target_latitude NUMERIC;
ALTER TABLE personal_preferences ADD COLUMN target_longitude NUMERIC;

-- These could be auto-filled from the user's school/company address
-- or explicitly set by the user on a map picker
```

**Frontend change needed:**
- Add a map picker component to `/preferences` page
- Or auto-geocode the target city + neighborhood text
- Store lat/lng in `personal_preferences`

---

#### B. Price Efficiency Score (15 pts) — NEW

Instead of just "does it fit the budget?" (hard constraint), score **how much of the budget is left over**.

```python
def calculate_price_efficiency_score(group: dict, listing: dict) -> float:
    """
    Score how efficiently the listing uses the group's budget.
    Cheaper listings within budget = higher score.
    
    Formula: score = 15 × (1 - (price - min) / (max - min))
    
    Examples (budget $800-$1200/person):
        $800/person:  15 pts (at minimum — maximum savings)
        $900/person:  11 pts 
        $1000/person:  8 pts (midpoint)
        $1100/person:  4 pts
        $1200/person:  0 pts (at maximum — no savings)
    """
    price = listing.get('price_per_month')
    budget_min = group.get('budget_per_person_min')
    budget_max = group.get('budget_per_person_max')
    
    if not all([price, budget_min, budget_max]):
        return 7  # Neutral
    
    price_per_person = float(price) / 2  # Assuming 2-person groups
    budget_min = float(budget_min)
    budget_max = float(budget_max)
    
    budget_range = budget_max - budget_min
    if budget_range <= 0:
        return 7
    
    # How far from the minimum (cheaper = better)
    position = (price_per_person - budget_min) / budget_range
    position = max(0, min(1, position))  # Clamp to [0, 1]
    
    return round(15 * (1 - position))
```

---

#### C. Listing Quality Score (10 pts) — NEW

Measures how complete and trustworthy a listing appears.

```python
def calculate_listing_quality_score(listing: dict) -> float:
    """
    Score based on listing completeness and trust signals.
    
    Components:
        Photos (0-4 pts):        0=0, 1-2=1, 3-4=2, 5-7=3, 8+=4
        Description length:      < 50 chars=0, 50-200=1, 200+=2
        Has amenities listed:    Yes=1, No=0
        Has house rules:         Yes=1, No=0
        Host is verified:        Yes=2, No=0
    
    Total: 10 pts max
    """
    score = 0
    
    # Photo count (need to query listing_photos table or pass count in)
    photo_count = listing.get('photo_count', 0)
    if photo_count >= 8:
        score += 4
    elif photo_count >= 5:
        score += 3
    elif photo_count >= 3:
        score += 2
    elif photo_count >= 1:
        score += 1
    
    # Description quality
    desc = listing.get('description', '')
    if len(desc) >= 200:
        score += 2
    elif len(desc) >= 50:
        score += 1
    
    # Completeness
    if listing.get('amenities'):
        score += 1
    if listing.get('house_rules'):
        score += 1
    
    # Host verification (need to join with users table)
    if listing.get('host_verified', False):
        score += 2
    
    return score
```

---

#### D. Move-in Date Closeness Score (5 pts) — NEW

Currently, date matching is binary (within ±30 days = pass, outside = fail). This adds a graduated score for closer dates.

```python
def calculate_date_closeness_score(group: dict, listing: dict) -> float:
    """
    Graduated score for how close the available date is to target move-in.
    
    Scoring:
        Exact match:    5 pts
        1-7 days off:   4 pts
        8-14 days off:  3 pts
        15-21 days off: 2 pts
        22-30 days off: 1 pt
    """
    target = parse_date(group.get('target_move_in_date'))
    available = parse_date(listing.get('available_from'))
    
    if not target or not available:
        return 2  # Neutral
    
    days_diff = abs((target - available).days)
    
    if days_diff == 0:
        return 5
    elif days_diff <= 7:
        return 4
    elif days_diff <= 14:
        return 3
    elif days_diff <= 21:
        return 2
    else:
        return 1
```

---

#### E. Improved Bathroom Score (4 pts) — REDUCED

```python
def calculate_bathroom_score(group: dict, listing: dict) -> float:
    """
    Reduced from 20 to 4 pts. Bathrooms matter, but not as much
    as location or price.
    
    Meets/exceeds target: 4 pts
    Within 0.5:           2 pts
    Below target:         1 pt
    """
```

#### F. Improved Furnished Score (3 pts) — REDUCED

```python
def calculate_furnished_score(group: dict, listing: dict) -> float:
    """
    Reduced from 20 to 3 pts.
    If user set furnished as hard constraint, this score is always max.
    If user didn't set it as hard constraint, it's a minor bonus.
    
    Matches preference: 3 pts
    Doesn't match:      1 pt
    """
```

#### G. Improved Utilities Score (3 pts) — REDUCED

```python
def calculate_utilities_score(group: dict, listing: dict) -> float:
    """
    Reduced from 20 to 3 pts. Same logic as furnished.
    
    Matches preference: 3 pts
    Doesn't match:      1 pt
    """
```

---

### 3.3 Updated `calculate_group_score()` Function

```python
def calculate_group_score(group: dict, listing: dict, ai_score: float = None) -> float:
    """
    Calculate how much a group likes a listing (0-100).
    
    Weight Distribution:
        TIER 1 — HIGH IMPACT (60 pts)
          Location proximity:        25 pts
          House rules compatibility: 20 pts
          Price efficiency:          15 pts
        
        TIER 2 — MEDIUM IMPACT (30 pts)
          Deposit amount:            15 pts
          Listing quality:           10 pts
          Move-in date closeness:     5 pts
        
        TIER 3 — LOW IMPACT (10 pts)
          Bathrooms:                  4 pts
          Furnished:                  3 pts
          Utilities:                  3 pts
        
        TOTAL:                      100 pts
    """
    score = 0
    
    # Tier 1: High Impact (60 pts)
    score += calculate_location_proximity_score(group, listing)  # /25
    score += calculate_house_rules_score(group, listing)         # /20
    score += calculate_price_efficiency_score(group, listing)    # /15
    
    # Tier 2: Medium Impact (30 pts)
    score += calculate_deposit_score(group, listing)             # /15
    score += calculate_listing_quality_score(listing)            # /10
    score += calculate_date_closeness_score(group, listing)      # /5
    
    # Tier 3: Low Impact (10 pts)
    score += calculate_bathroom_score(group, listing)            # /4
    score += calculate_furnished_score(group, listing)           # /3
    score += calculate_utilities_score(group, listing)           # /3
    
    # AI Blend (if available)
    if ai_score is not None:
        ai_normalized = ai_score * MAX_SCORE
        ai_weight = get_adaptive_ai_weight(group)
        score = (ai_weight * ai_normalized) + ((1 - ai_weight) * score)
    
    return round(score, 2)
```

---

### 3.4 Before vs. After Comparison

**Scenario:** Sarah is choosing between two listings that both pass hard constraints.

| Factor | Listing A (far, cheap, nice) | Listing B (close, mid-price, basic) |
|---|---|---|
| Distance from campus | 18 km | 2 km |
| Price per person | $820/mo | $1,050/mo |
| Deposit | $400 | $800 |
| Bathrooms | 2 (target: 1) | 1 |
| Furnished | Yes (wants: yes) | No |
| Utilities | Yes (wants: yes) | No |
| House rules | No conflicts | No conflicts |
| Photos | 10 | 3 |
| Description | 300 chars | 80 chars |
| Date match | Exact | 12 days off |

#### Old Scoring (current `scoring.py`):

| Factor | Listing A | Listing B |
|---|---|---|
| Bathrooms | 20 | 20 |
| Furnished | 20 | 10 |
| Utilities | 20 | 10 |
| Deposit | 20 | 10 |
| House rules | 20 | 20 |
| **Total** | **100** | **70** |

**Winner: Listing A (100 vs 70)** — but it's 18 km from campus! ❌

#### New Scoring (proposed):

| Factor | Listing A | Listing B |
|---|---|---|
| **Location proximity** | **5** (18 km = very far) | **20** (2 km = short bike) |
| **Price efficiency** | **14** (near budget min) | **6** (mid-range) |
| House rules | 20 | 20 |
| Deposit | 15 | 10 |
| **Listing quality** | **8** (10 photos, long desc) | **3** (3 photos, short desc) |
| **Date closeness** | **5** (exact) | **3** (12 days off) |
| Bathrooms | 4 | 4 |
| Furnished | 3 | 1 |
| Utilities | 3 | 1 |
| **Total** | **77** | **68** |

**Winner: Listing A (77 vs 68)** — but the gap is much closer, and the factors now show **why**. If Sarah had been swiping mostly on nearby listings, the AI blend would push Listing B ahead — which is the right call. ✅

Now imagine the AI has learned Sarah always swipes right on listings < 3km from campus:

```
AI Score for Listing A: 0.35
AI Score for Listing B: 0.88

With AI blend (100+ swipes, ai_weight = 0.7):
  Listing A: (0.7 × 35) + (0.3 × 77) = 24.5 + 23.1 = 47.6
  Listing B: (0.7 × 88) + (0.3 × 68) = 61.6 + 20.4 = 82.0

Winner: Listing B (82.0 vs 47.6) ✅ — The AI correctly flips the ranking!
```

---

## 4. Database Changes Required

```sql
-- Add target coordinates to personal_preferences (for location proximity scoring)
ALTER TABLE personal_preferences ADD COLUMN target_latitude NUMERIC;
ALTER TABLE personal_preferences ADD COLUMN target_longitude NUMERIC;
ALTER TABLE personal_preferences ADD COLUMN target_state_province TEXT;

-- Add photo count cache to listings (avoid joins during scoring)
ALTER TABLE listings ADD COLUMN photo_count INTEGER DEFAULT 0;

-- Add host verification flag cache (avoid joins during scoring)
ALTER TABLE listings ADD COLUMN host_verified BOOLEAN DEFAULT false;

-- Trigger to keep photo_count in sync
CREATE OR REPLACE FUNCTION update_listing_photo_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE listings 
    SET photo_count = (
        SELECT COUNT(*) FROM listing_photos WHERE listing_id = COALESCE(NEW.listing_id, OLD.listing_id)
    )
    WHERE id = COALESCE(NEW.listing_id, OLD.listing_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_listing_photo_count
AFTER INSERT OR DELETE ON listing_photos
FOR EACH ROW EXECUTE FUNCTION update_listing_photo_count();
```

---

## 5. Frontend Changes Required

### Preferences Page (`/preferences`)

Add to the Housing Preferences form:

1. **Map Picker Component** — Let users pin their target location (campus, office)
   - Stores `target_latitude` and `target_longitude`
   - Use Mapbox GL or Google Maps embed
   - Auto-suggest from school/company name

2. **Priority Slider (optional, future)** — Let users weight what matters most
   - "What matters more to you: Location or Price?"
   - Adjusts tier weights dynamically

---

## 6. Implementation Priority

| Priority | Change | Effort | Impact |
|---|---|---|---|
| 🔴 P0 | Add Location Proximity Score | Medium (need lat/lng + map picker) | **Huge** — biggest gap in current scoring |
| 🔴 P0 | Rebalance existing weights | Small (just change constants) | **High** — better rankings immediately |
| 🟡 P1 | Add Price Efficiency Score | Small (pure calculation) | **High** — students care about savings |
| 🟡 P1 | Add Date Closeness Score | Small (pure calculation) | **Medium** — graduated > binary |
| 🟢 P2 | Add Listing Quality Score | Medium (need photo count, joins) | **Medium** — trust signals matter |
| 🟢 P2 | Map Picker UI component | Medium (frontend component) | **High UX** — visual location selection |

---

## 7. Files to Modify

| File | Change |
|---|---|
| `backend/app/services/stable_matching/scoring.py` | Rewrite `calculate_group_score()`, add new scoring functions, update weight constants |
| `backend/app/services/stable_matching/feasible_pairs.py` | No changes (hard constraints stay the same) |
| `backend/app/services/data_parser.py` | Add `photo_count` and `host_verified` to `parse_listing()` |
| `backend/app/models.py` | Add `target_latitude`, `target_longitude` to `PersonalPreferencesBase` |
| `backend/app/routes/preferences.py` | Handle new lat/lng fields in serialization |
| `frontend/src/app/preferences/page.jsx` | Add map picker component |
| `backend/migrations/006_scoring_improvements.sql` | New migration for schema changes |

---

*This document should be implemented before or in parallel with Phase 2 of the ML Roadmap, so the improved rule-based scoring serves as a stronger baseline and fallback.*
