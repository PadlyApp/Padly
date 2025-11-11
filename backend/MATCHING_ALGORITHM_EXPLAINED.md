# 🎯 Matching Algorithm - How It Works

## Current Implementation (v1 - Random Matching)

The matching algorithm currently uses **random scoring** as a placeholder while the real preference-based algorithm is being developed.

---

## 📊 High-Level Flow

```
┌─────────────────┐
│  User Requests  │
│     Matches     │
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────────────────────┐
│  API Endpoint                                   │
│  GET /api/matches/{user_id}/v2?limit=20        │
└────────┬────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────┐
│  Data Parser Service                            │
│  • Fetches listings from Supabase              │
│  • Parses to JSON-ready format                 │
│  • Serializes types (Decimal → float, etc.)    │
└────────┬────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────┐
│  Matching Algorithm                             │
│  • Filters active listings                     │
│  • Calculates match scores                     │
│  • Sorts by score (highest first)              │
└────────┬────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────┐
│  Response                                       │
│  {                                              │
│    "user_id": "...",                            │
│    "total_matches": 20,                         │
│    "matches": [                                 │
│      {                                          │
│        "id": "...",                             │
│        "title": "Cozy Studio...",               │
│        "price_per_month": 2200.0,               │
│        "match_score": 95,  ← Random score       │
│        ...all listing fields...                 │
│      }                                          │
│    ],                                           │
│    "algorithm_version": "random_v1"             │
│  }                                              │
└─────────────────────────────────────────────────┘
```

---

## 🔄 Step-by-Step Process

### 1. **User Makes Request**
```http
GET /api/matches/USER_ID/v2?limit=20
```

### 2. **Fetch User Data** (Optional)
- Fetches user's `personal_preferences` from database
- Used for future preference-based matching
- Currently not utilized in scoring

### 3. **Fetch Listings**
```python
listings = await fetch_and_parse_listings(status_filter="active")
```
- Gets all active listings from Supabase
- Parses to clean JSON format
- Converts problematic types

### 4. **Calculate Match Scores**
```python
def calculate_random_match_score(listing, user_preferences=None):
    # Uses listing ID as seed for consistency
    listing_id = listing.get('id', '')
    hash_value = sum(ord(c) for c in str(listing_id))
    score = 70 + (hash_value % 30)  # Score: 70-99
    return score
```

**Current Logic:**
- Creates a hash from listing ID
- Generates score between 70-99
- **Deterministic**: Same listing always gets same score
- **Ignores preferences** (placeholder)

### 5. **Add Scores to Listings**
```python
for listing in listings:
    listing_with_score = listing.copy()
    listing_with_score['match_score'] = calculate_random_match_score(listing)
    matches.append(listing_with_score)
```

### 6. **Sort by Score**
```python
matches.sort(key=lambda x: x['match_score'], reverse=True)
```
- Highest scores first
- Returns top `limit` results (default: 20)

### 7. **Return Response**
```json
{
  "user_id": "abc-123",
  "total_matches": 20,
  "matches": [
    {
      "id": "listing-uuid",
      "title": "Cozy Studio in Downtown SF",
      "price_per_month": 2200.0,
      "match_score": 95,
      "city": "San Francisco",
      ...all other listing fields...
    }
  ],
  "generated_at": "2025-11-11T12:00:00",
  "algorithm_version": "random_v1"
}
```

---

## 🏘️ Group Matching

Similar process for roommate groups:

```python
# GET /api/matches/{user_id}/groups
```

**Additional Filters:**
- Only groups with available spots (`current_size < target_group_size`)
- Active groups only
- Same random scoring (for now)

---

## 🎯 Future Implementation (Planned)

The TODO section in the code outlines the real matching algorithm:

### **1. Hard Constraints** (Must Match - Pass/Fail)
```python
if user_wants_pets and not listing.amenities.pets_allowed:
    score = 0  # Disqualify
```

Constraints:
- ✅ Lease type compatibility
- ✅ Move-in date within range
- ✅ Bedroom/bathroom requirements
- ✅ Pet policy
- ✅ Smoking policy
- ✅ Parking availability
- ✅ Accessibility needs

### **2. Soft Preferences** (Weighted Scoring)
```python
score += calculate_amenity_match(user.preferences, listing.amenities) * WEIGHT_AMENITIES
score += calculate_budget_fit(user.budget, listing.price) * WEIGHT_BUDGET
score += calculate_location_fit(user.neighborhoods, listing.location) * WEIGHT_LOCATION
```

Preferences:
- 🎯 Amenities match (wifi, laundry, gym, etc.)
- 💰 Budget fit (how close to user's ideal)
- 📍 Location preference (neighborhood match)
- 🛋️ Furnished preference
- 🚗 Parking preference

### **3. Roommate Compatibility** (For Group Matching)
```python
score += calculate_age_compatibility() * WEIGHT_AGE
score += calculate_lifestyle_match() * WEIGHT_LIFESTYLE
```

Compatibility:
- 👥 Age range compatibility
- 🎵 Lifestyle preferences
- 🐕 Pet compatibility
- 🍽️ Dietary preferences
- 🧹 Cleanliness expectations

### **4. Final Score Calculation**
```python
final_score = (
    (hard_constraints_met ? 1 : 0) * 100 +
    soft_preferences_score * PREFERENCE_WEIGHT +
    roommate_compatibility_score * COMPATIBILITY_WEIGHT
)
```

Score range: 0-100
- **0-69**: Poor match
- **70-79**: Fair match
- **80-89**: Good match
- **90-100**: Excellent match

---

## 📍 Available Endpoints

### **Listing Matches**
```bash
# Get matches for a user (current method)
GET /api/matches/{user_id}

# Get matches for a user (v2 - uses data parser)
GET /api/matches/{user_id}/v2?limit=20
```

### **Group Matches**
```bash
# Get roommate group matches
GET /api/matches/{user_id}/groups?limit=20
```

### **Data Export** (for testing/debugging)
```bash
# Get all parsed listings
GET /api/matches/data/listings

# Get all parsed groups
GET /api/matches/data/groups

# Get everything
GET /api/matches/data/all
```

---

## 🧪 Testing the Algorithm

### **Test Script**
```bash
cd backend
source venv/bin/activate
python -m app.scripts.test_data_parser
```

This will:
- Fetch data from Supabase
- Show sample matches
- Save JSON files for inspection

### **Example Usage**
See: `backend/app/scripts/example_usage.py`

---

## 🔧 Key Files

| File | Purpose |
|------|---------|
| `app/services/matching_algorithm.py` | Core matching logic |
| `app/services/data_parser.py` | Fetch & parse data from Supabase |
| `app/routes/matches.py` | API endpoints |
| `app/services/supabase_client.py` | Database communication |

---

## 🚀 Next Steps to Implement Real Matching

1. **Define preference weights** (which factors matter most?)
2. **Implement hard constraint filtering**
3. **Build scoring functions** for each factor
4. **Test with real user data**
5. **Tune weights** based on feedback
6. **Add machine learning** (optional - learn from user swipes/favorites)

---

## 💡 Example: How Real Matching Would Work

**User Profile:**
```json
{
  "budget_max": 2500,
  "move_in_date": "2025-06-01",
  "preferred_neighborhoods": ["Mission District", "SOMA"],
  "lifestyle_preferences": {
    "housing": {
      "furnished_required": true,
      "pets_allowed": true,
      "laundry_in_unit": true
    }
  }
}
```

**Listing:**
```json
{
  "price_per_month": 2200,
  "available_from": "2025-05-15",
  "city": "San Francisco",
  "neighborhood": "Mission District",
  "furnished": true,
  "amenities": {
    "pets_allowed": true,
    "laundry": "in_unit"
  }
}
```

**Scoring:**
```python
# Hard Constraints
✅ Within budget (2200 < 2500)
✅ Move-in dates compatible
✅ Pets allowed

# Soft Preferences
+20 pts: Preferred neighborhood (Mission District)
+15 pts: Furnished (required)
+10 pts: In-unit laundry
+5 pts:  Price is 300 below budget

# Final Score
Hard constraints: PASS
Soft score: 50/50
Final: 95/100 ⭐⭐⭐⭐⭐ Excellent Match!
```

---

## 📊 Current Database Stats

- **123 Listings** available
- **12 Roommate Groups** active
- **44 Users** registered
- **20 Group Members** total

---

**Algorithm Version**: `random_v1` (placeholder)  
**Status**: ⚠️ Development - Real matching coming soon!  
**Last Updated**: November 11, 2025
