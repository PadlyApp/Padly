# Dataset Requirements for Padly ML

**Branch:** `neural_net`
**Last Updated:** 2026-02-10

---

## Overview

Padly's ML system requires **three datasets** to function:

| Dataset | Used By | Purpose |
|---|---|---|
| **Dataset A:** User–Listing Interactions | Two-Tower Model | Learn what listings each user likes |
| **Dataset B:** User Profiles + Preferences | Both Models | Describe who each user is |
| **Dataset C:** Listing Data | Two-Tower Model | Describe what each listing is |

Additionally, the Siamese Network (roommate matching) uses:

| Dataset | Used By | Purpose |
|---|---|---|
| **Dataset D:** Roommate Group Pairs | Siamese Network | Learn which users are compatible roommates |

---

## Dataset A: User–Listing Interactions (Swipe Data)

This is the **core training dataset**. Every row represents one user looking at one listing and making a decision.

### Schema

| Column | Type | Description | Example |
|---|---|---|---|
| `interaction_id` | UUID | Unique ID for this interaction | `a1b2c3d4-...` |
| `user_id` | UUID | Who performed the action | `user_sarah_01` |
| `listing_id` | UUID | Which listing they acted on | `listing_2br_utm_03` |
| `action` | STRING | What they did | `like`, `pass`, `save`, `view` |
| `position_in_feed` | INTEGER | Where the listing appeared in their feed (1 = top) | `3` |
| `time_spent_seconds` | FLOAT | How long they looked at the listing | `12.5` |
| `session_id` | UUID | Groups interactions from the same browsing session | `sess_xyz_789` |
| `created_at` | TIMESTAMP | When the interaction happened | `2026-02-10 15:30:00` |

### Example Rows

```
interaction_id  | user_id  | listing_id | action | position | time_spent | created_at
────────────────┼──────────┼────────────┼────────┼──────────┼────────────┼───────────────────
i-001           | sarah    | listing-03 | like   | 1        | 18.2       | 2026-02-10 10:00
i-002           | sarah    | listing-07 | pass   | 2        | 3.1        | 2026-02-10 10:01
i-003           | sarah    | listing-05 | like   | 3        | 22.7       | 2026-02-10 10:01
i-004           | sarah    | listing-01 | pass   | 4        | 1.8        | 2026-02-10 10:02
i-005           | sarah    | listing-04 | save   | 5        | 45.3       | 2026-02-10 10:03
i-006           | mike     | listing-03 | like   | 1        | 15.0       | 2026-02-10 11:00
i-007           | mike     | listing-02 | like   | 2        | 8.4        | 2026-02-10 11:01
i-008           | mike     | listing-05 | pass   | 3        | 2.0        | 2026-02-10 11:01
i-009           | priya    | listing-01 | like   | 1        | 30.1       | 2026-02-10 12:00
i-010           | priya    | listing-03 | pass   | 2        | 4.5        | 2026-02-10 12:01
```

### How It Becomes Training Data

Each row gets converted into a training example for the Two-Tower model:

```
For the model, we only care about: (user_id, listing_id, label)

Label rules:
    action = "like"  →  label = 1   (positive — user wants this)
    action = "save"  →  label = 1   (positive — user wants this)
    action = "pass"  →  label = 0   (negative — user doesn't want this)
    action = "view"  →  ignored     (ambiguous — they saw it but didn't decide)
```

So the training set becomes:

```
user_id  | listing_id | label
─────────┼────────────┼──────
sarah    | listing-03 | 1
sarah    | listing-07 | 0
sarah    | listing-05 | 1
sarah    | listing-01 | 0
sarah    | listing-04 | 1       ← "save" counts as positive
mike     | listing-03 | 1
mike     | listing-02 | 1
mike     | listing-05 | 0
priya    | listing-01 | 1
priya    | listing-03 | 0
```

### Negative Sampling

Users typically only swipe on a small fraction of all listings. For listings they **never saw**, we assume a weak negative (they probably wouldn't like most random listings).

For each positive (like), we sample **3 random unseen listings** as implicit negatives:

```
Original positive:
    sarah | listing-03 | 1

Generated negatives (random listings Sarah never saw):
    sarah | listing-12 | 0
    sarah | listing-19 | 0
    sarah | listing-08 | 0
```

This gives the model a balanced mix of "yes" and "no" examples to learn from.

### Volume Requirements

| Stage | Minimum Interactions | Users | Listings | Quality |
|---|---|---|---|---|
| **Can't train yet** | < 200 | < 10 | < 20 | Use heuristic scoring only |
| **First trainable model** | 500–1,000 | 30+ | 50+ | Basic personalization, noisy |
| **Decent model** | 5,000–10,000 | 100+ | 200+ | Good personalization |
| **Strong model** | 50,000+ | 500+ | 500+ | Netflix-level recommendations |

---

## Dataset B: User Profiles + Preferences

This dataset describes **who each user is**. The Two-Tower model reads this to build the user feature vector (the 480 numbers that go into the User Tower).

### Schema

Two tables joined together:

**Table: `users`**

| Column | Type | Description | Example |
|---|---|---|---|
| `id` | UUID | User ID | `user_sarah_01` |
| `email` | STRING | Email address | `sarah@utoronto.ca` |
| `full_name` | STRING | Full name | `Sarah Chen` |
| `bio` | TEXT | Free-text bio | `"Grad student at UTM, quiet, tidy..."` |
| `role` | ENUM | User type | `renter` |
| `company_name` | STRING | Current company (if intern) | `null` |
| `school_name` | STRING | Current school | `University of Toronto` |
| `role_title` | STRING | Position | `Graduate Student` |
| `verification_status` | ENUM | Trust level | `email_verified` |
| `created_at` | TIMESTAMP | Account creation | `2026-01-15` |

**Table: `personal_preferences`**

| Column | Type | Description | Example |
|---|---|---|---|
| `user_id` | UUID | Foreign key to users | `user_sarah_01` |
| `target_city` | STRING | Where they want to live | `Toronto` |
| `target_state_province` | STRING | State/province | `Ontario` |
| `budget_min` | FLOAT | Minimum budget per person | `800.00` |
| `budget_max` | FLOAT | Maximum budget per person | `1200.00` |
| `move_in_date` | DATE | Target move-in date | `2026-05-01` |
| `target_furnished` | BOOLEAN | Wants furnished? | `true` |
| `target_utilities_included` | BOOLEAN | Wants utilities included? | `true` |
| `target_deposit_amount` | FLOAT | Max acceptable deposit | `500.00` |
| `target_lease_type` | ENUM | Lease preference | `fixed_term` |
| `target_lease_duration_months` | INTEGER | Desired lease length | `12` |
| `target_house_rules` | TEXT | Lifestyle preferences | `"No smoking, quiet after 10pm"` |
| `lifestyle_preferences` | JSON | Structured lifestyle data | `{"cleanliness": "very_clean", "noise_level": "quiet", ...}` |

### Example Row (Joined)

```json
{
    "id": "user_sarah_01",
    "full_name": "Sarah Chen",
    "bio": "Grad student at UTM. Quiet, tidy, early sleeper. Looking for a clean place near campus.",
    "school_name": "University of Toronto",
    "role": "renter",
    "verification_status": "email_verified",
    "preferences": {
        "target_city": "Toronto",
        "budget_min": 800,
        "budget_max": 1200,
        "move_in_date": "2026-05-01",
        "target_furnished": true,
        "target_utilities_included": true,
        "target_deposit_amount": 500,
        "lifestyle_preferences": {
            "cleanliness": "very_clean",
            "noise_level": "quiet",
            "smoking": "no_smoking",
            "pets": "no_pets",
            "guests_frequency": "occasionally"
        }
    }
}
```

### How It Becomes the 480-Number Vector

| Source Field | Encoding Method | # Numbers |
|---|---|---|
| `budget_min` | Normalize to 0–1 range | 1 |
| `budget_max` | Normalize to 0–1 range | 1 |
| `move_in_date` | Cyclical: sin(month) + cos(month) | 2 |
| `target_furnished` | Binary (0 or 1) | 1 |
| `target_utilities_included` | Binary | 1 |
| `target_deposit_amount` | Normalize to 0–1 | 1 |
| `cleanliness` | One-hot [messy, moderate, clean, very_clean] | 4 |
| `noise_level` | One-hot [loud, moderate, quiet] | 3 |
| `smoking` | One-hot [smoking_ok, outdoor_only, no_smoking] | 3 |
| `pets` | One-hot [pets_ok, no_pets] | 2 |
| `guests_frequency` | One-hot [frequently, occasionally, rarely] | 3 |
| `verification_status` | One-hot [unverified, email_verified, admin_verified] | 3 |
| `role` | One-hot [renter, host, admin] | 3 |
| `bio` | Sentence-transformer → vector | 384 |
| `swipe_history` | Average embedding of liked listings | 64 |
| **TOTAL** | | **~476** |

---

## Dataset C: Listing Data

This dataset describes **each available listing**. The Two-Tower model reads this to build the listing feature vector (the 923 numbers that go into the Item Tower).

### Schema

**Table: `listings`**

| Column | Type | Description | Example |
|---|---|---|---|
| `id` | UUID | Listing ID | `listing-2br-utm-03` |
| `host_user_id` | UUID | Who posted it | `host_john_01` |
| `status` | ENUM | Active/inactive/draft | `active` |
| `title` | TEXT | Listing title | `"Modern 2BR near UTM campus"` |
| `description` | TEXT | Full description | `"Beautiful modern apartment..."` |
| `property_type` | ENUM | Entire place / room / shared | `entire_place` |
| `lease_type` | ENUM | Fixed / open-ended | `fixed_term` |
| `lease_duration_months` | INTEGER | Lease length | `12` |
| `number_of_bedrooms` | INTEGER | Bedrooms | `2` |
| `number_of_bathrooms` | FLOAT | Bathrooms | `1.0` |
| `area_sqft` | INTEGER | Area in sqft | `780` |
| `furnished` | BOOLEAN | Is it furnished? | `true` |
| `price_per_month` | FLOAT | Total monthly rent | `2100.00` |
| `utilities_included` | BOOLEAN | Are utilities included? | `false` |
| `deposit_amount` | FLOAT | Security deposit | `500.00` |
| `city` | STRING | City | `Toronto` |
| `state_province` | STRING | State/province | `Ontario` |
| `latitude` | FLOAT | GPS latitude | `43.5489` |
| `longitude` | FLOAT | GPS longitude | `-79.6625` |
| `available_from` | DATE | Available starting | `2026-05-01` |
| `available_to` | DATE | Available until | `2027-04-30` |
| `amenities` | JSON | Available amenities | `{"gym": true, "ac": true, ...}` |
| `house_rules` | TEXT | Rules | `"No smoking, no parties"` |

**Table: `listing_photos`**

| Column | Type | Description | Example |
|---|---|---|---|
| `id` | UUID | Photo ID | `photo-001` |
| `listing_id` | UUID | Which listing | `listing-2br-utm-03` |
| `photo_url` | TEXT | URL to image | `https://storage.../room1.jpg` |
| `sort_order` | INTEGER | Display order | `1` |

### Example Row

```json
{
    "id": "listing-2br-utm-03",
    "title": "Modern 2BR near UTM campus",
    "description": "Beautiful modern apartment, 5 min walk from UTM. Newly renovated kitchen, hardwood floors, lots of natural light. Gym and AC in building. Perfect for students.",
    "property_type": "entire_place",
    "lease_type": "fixed_term",
    "lease_duration_months": 12,
    "number_of_bedrooms": 2,
    "number_of_bathrooms": 1.0,
    "area_sqft": 780,
    "furnished": true,
    "price_per_month": 2100.00,
    "utilities_included": false,
    "deposit_amount": 500.00,
    "city": "Toronto",
    "latitude": 43.5489,
    "longitude": -79.6625,
    "available_from": "2026-05-01",
    "amenities": {
        "gym": true,
        "ac": true,
        "laundry_in_building": true,
        "laundry_in_unit": false,
        "dishwasher": false,
        "parking": false,
        "balcony": true,
        "pool": false,
        "elevator": true,
        "wheelchair_accessible": false,
        "storage": false,
        "bike_storage": true,
        "security_system": false,
        "concierge": false,
        "rooftop": false
    },
    "house_rules": "No smoking, no parties after 10pm, no pets",
    "photos": [
        {"url": "https://storage.../living_room.jpg", "sort_order": 1},
        {"url": "https://storage.../kitchen.jpg", "sort_order": 2},
        {"url": "https://storage.../bedroom1.jpg", "sort_order": 3}
    ]
}
```

### How It Becomes the 923-Number Vector

| Source Field | Encoding Method | # Numbers |
|---|---|---|
| `price_per_month` | Normalize to 0–1 | 1 |
| `number_of_bedrooms` | Raw integer | 1 |
| `number_of_bathrooms` | Raw float | 1 |
| `area_sqft` | Normalize to 0–1 | 1 |
| `furnished` | Binary | 1 |
| `utilities_included` | Binary | 1 |
| `deposit_amount` | Normalize to 0–1 | 1 |
| `lease_duration_months` | Normalize to 0–1 | 1 |
| `latitude` | Normalize to 0–1 | 1 |
| `longitude` | Normalize to 0–1 | 1 |
| `property_type` | One-hot [entire, private_room, shared_room] | 3 |
| `lease_type` | One-hot [fixed, open_ended] | 2 |
| `amenities` | Multi-hot (15 amenity flags) | 15 |
| `title + description + house_rules` | Sentence-transformer → vector | 384 |
| `photos` | CLIP model → average vector | 512 |
| **TOTAL** | | **~927** |

---

## Dataset D: Roommate Group Pairs (for Siamese Network)

This dataset describes **which users have lived well together** (positive pairs) and which haven't (negative pairs). It's used to train the Siamese Network for roommate matching.

### Schema

This isn't a new table — it's derived from the existing `group_members` table.

**Source table: `group_members`**

| Column | Type | Description | Example |
|---|---|---|---|
| `group_id` | UUID | Which group | `group-alpha-01` |
| `user_id` | UUID | Which user | `user_sarah_01` |
| `status` | ENUM | Membership status | `accepted`, `pending`, `rejected` |
| `is_creator` | BOOLEAN | Did they create the group? | `true` |
| `joined_at` | TIMESTAMP | When they joined | `2026-01-20` |

### How Pairs Are Extracted

**Positive pairs** — users in the same group who were both accepted:

```sql
SELECT gm1.user_id AS user_a, gm2.user_id AS user_b, 1 AS label
FROM group_members gm1
JOIN group_members gm2 ON gm1.group_id = gm2.group_id
WHERE gm1.user_id < gm2.user_id        -- avoid duplicate pairs
  AND gm1.status = 'accepted'
  AND gm2.status = 'accepted';
```

```
Group "Alpha House" has 3 accepted members: Sarah, Mike, Priya

Positive pairs generated:
    (sarah, mike)  → label = 1    "compatible roommates"
    (sarah, priya) → label = 1    "compatible roommates"
    (mike, priya)  → label = 1    "compatible roommates"
```

**Hard negative pairs** — users who were rejected from or left a group:

```sql
-- User was rejected from a group → incompatible with that group's members
SELECT gm1.user_id AS user_a, gm2.user_id AS user_b, 0 AS label
FROM group_members gm1
JOIN group_members gm2 ON gm1.group_id = gm2.group_id
WHERE gm1.status = 'rejected'
  AND gm2.status = 'accepted';
```

```
Alex applied to "Alpha House" but was rejected:

Hard negative pairs generated:
    (alex, sarah) → label = 0    "incompatible"
    (alex, mike)  → label = 0    "incompatible"
    (alex, priya) → label = 0    "incompatible"
```

**Random negative pairs** — users from completely different groups:

```
Sarah is in "Alpha House", Jordan is in "Beta Spot"

Random negative:
    (sarah, jordan) → label = 0    "unknown, assumed incompatible"
```

### Example Training Set

```
user_a   | user_b   | label | source
─────────┼──────────┼───────┼──────────────────
sarah    | mike     | 1     | same group (accepted)
sarah    | priya    | 1     | same group (accepted)
mike     | priya    | 1     | same group (accepted)
alex     | sarah    | 0     | rejected from sarah's group
alex     | mike     | 0     | rejected from sarah's group
sarah    | jordan   | 0     | random (different groups)
mike     | jordan   | 0     | random (different groups)
priya    | taylor   | 0     | random (different groups)
```

### Volume Requirements

| Stage | Minimum Pairs | Groups | Quality |
|---|---|---|---|
| **Can't train yet** | < 30 pairs | < 5 groups | Use rule-based compatibility only |
| **First trainable model** | 100–300 pairs | 15–30 groups | Basic compatibility detection |
| **Decent model** | 1,000+ pairs | 100+ groups | Good roommate predictions |

---

## Dataset E: Listing Categories & Onboarding Interactions (Cold-Start Solution)

The biggest challenge with the Two-Tower model is **cold start**: a brand-new user has zero swipe history, so the model has nothing to learn from. We solve this with **categorized onboarding**.

### The Idea

1. Every listing gets labeled into one of **5 categories**
2. When a new user signs up, they're shown **5 curated listings** — one from each category
3. They swipe (like/pass) on each one
4. Those 5 swipes immediately seed their preference profile, giving the model a starting signal

### The 5 Listing Categories

Each listing is assigned **exactly one** category based on its dominant characteristic:

| # | Category | Label | Description | Example Listing |
|---|---|---|---|---|
| 1 | **Budget-Friendly** | `budget` | Low price, basic amenities, farther from campus. Appeals to price-sensitive users. | "$650/mo shared room in Mississauga, unfurnished, bus access" |
| 2 | **Premium & Modern** | `premium` | High price, renovated, full amenities (gym, AC, laundry in-unit). Appeals to comfort-seekers. | "$1,400/mo modern studio downtown, gym, concierge, furnished" |
| 3 | **Campus-Close** | `campus` | Walking distance to university/college, student-oriented. Appeals to convenience-seekers. | "$950/mo 2BR, 5 min from UTM, student building, all-inclusive" |
| 4 | **Spacious & Family-Style** | `spacious` | Large area, multiple bedrooms, quiet neighborhood. Appeals to groups or those wanting space. | "$1,100/mo 4BR house in Etobicoke, backyard, parking, quiet street" |
| 5 | **Social & Downtown** | `social` | Urban location, nightlife/restaurants nearby, transit hub. Appeals to social/active users. | "$1,050/mo 1BR near Yonge & Dundas, walk to everything, vibrant area" |

### How Listings Get Categorized

**Option A: Rule-Based Labeling (Simple, Phase 1)**

```python
def categorize_listing(listing: dict) -> str:
    """
    Assign a listing to one of 5 categories based on its features.
    
    Priority order (first match wins):
        1. Budget:    price_per_person < 700
        2. Premium:   price_per_person > 1200 AND amenity_count >= 5
        3. Campus:    distance_to_nearest_campus < 2 km
        4. Social:    downtown_score > 0.7 (based on lat/lng)
        5. Spacious:  bedrooms >= 3 OR area_sqft > 1000
        
    Default: assigned to least-populated category (for balance)
    """
    price_pp = listing['price_per_month'] / max(listing['number_of_bedrooms'], 1)
    
    if price_pp < 700:
        return 'budget'
    elif price_pp > 1200 and count_amenities(listing) >= 5:
        return 'premium'
    elif distance_to_campus(listing) < 2.0:
        return 'campus'
    elif downtown_score(listing) > 0.7:
        return 'social'
    elif listing['number_of_bedrooms'] >= 3 or (listing.get('area_sqft') or 0) > 1000:
        return 'spacious'
    else:
        return least_populated_category()
```

**Option B: Clustering (ML-Based, Phase 3+)**

Use K-Means clustering on listing embeddings to discover natural groupings:

```python
from sklearn.cluster import KMeans

# Use listing embeddings from Item Tower
embeddings = get_all_listing_embeddings()  # (N, 64)
kmeans = KMeans(n_clusters=5, random_state=42)
labels = kmeans.fit_predict(embeddings)

# Manually inspect clusters and assign human-readable names
# Cluster 0 → "budget", Cluster 1 → "premium", etc.
```

### Database Changes

```sql
-- Add category label to listings
ALTER TABLE listings ADD COLUMN category VARCHAR(20) 
    CHECK (category IN ('budget', 'premium', 'campus', 'spacious', 'social'));

-- Index for efficient category queries
CREATE INDEX idx_listings_category ON listings(category);

-- Onboarding tracking: has the user completed the 5-swipe onboarding?
ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT false;
```

### The Onboarding Flow

When a new user signs up and hasn't completed onboarding (`onboarding_completed = false`):

```
STEP 1: Backend selects 5 representative listings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SELECT * FROM listings
WHERE status = 'active'
  AND city = {user's target city}
  AND category = 'budget'          -- 1 from each category
ORDER BY listing_quality_score DESC
LIMIT 1;

-- Repeat for 'premium', 'campus', 'spacious', 'social'
-- Pick the "best representative" from each category (highest quality score)


STEP 2: Frontend shows 5 cards with context
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────────────────────────────────────────────────────┐
│                                                      │
│    "Help us learn what you're looking for!"          │
│    "Swipe on 5 listings to personalize your feed"    │
│                                                      │
│    ┌──────────────────────────────────────────────┐  │
│    │                                              │  │
│    │  📸 [Listing photo]                          │  │
│    │                                              │  │
│    │  🏷️ BUDGET-FRIENDLY                          │  │
│    │  Shared room in Mississauga                  │  │
│    │  $650/mo · 1 bed · Unfurnished               │  │
│    │                                              │  │
│    │       ✕ NOT MY STYLE      ❤️ I LIKE THIS     │  │
│    │                                              │  │
│    └──────────────────────────────────────────────┘  │
│                                                      │
│    Card 1 of 5                    ● ○ ○ ○ ○         │
│                                                      │
└──────────────────────────────────────────────────────┘

User sees:
  Card 1: Budget listing        → swipe → logged
  Card 2: Premium listing       → swipe → logged
  Card 3: Campus-close listing  → swipe → logged
  Card 4: Spacious listing      → swipe → logged
  Card 5: Social/downtown       → swipe → logged


STEP 3: Backend processes the 5 swipes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

After 5 swipes, we know (for example):
  ✅ Liked: campus, social        → Sarah prefers close + urban
  ❌ Passed: budget, premium, spacious → She doesn't want cheap, fancy, or big

This immediately tells us:
  - Weight "location proximity" heavily
  - She's mid-budget (not cheap, not luxury)
  - She prefers smaller, central places

SET onboarding_completed = true for this user


STEP 4: First real feed is already personalized
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Even with only 5 swipes, the heuristic scorer can now:
  - Boost listings in the "campus" and "social" categories
  - Deprioritize "budget" and "spacious" listings
  - The AI model also has 5 data points to start with
    (not enough to train alone, but contributes to the global model)
```

### Example: What 5 Swipes Tell Us

| User | Budget | Premium | Campus | Spacious | Social | Inferred Preference |
|---|---|---|---|---|---|---|
| **Sarah** | ❌ pass | ❌ pass | ✅ like | ❌ pass | ✅ like | Close to campus + urban vibe |
| **Mike** | ✅ like | ❌ pass | ✅ like | ❌ pass | ❌ pass | Price-conscious + near school |
| **Priya** | ❌ pass | ✅ like | ❌ pass | ❌ pass | ✅ like | Comfort + social lifestyle |
| **Alex** | ❌ pass | ❌ pass | ❌ pass | ✅ like | ❌ pass | Wants space + quiet |

Just 5 swipes per user, but the system already has a clear picture of what each person values.

### How It Feeds Into the Two-Tower Model

The 5 onboarding swipes are stored in `user_interactions` with a special flag:

```sql
-- Onboarding interactions get marked so we can track them
INSERT INTO user_interactions (user_id, listing_id, action, position_in_feed, session_id)
VALUES (
    'sarah',
    'campus-listing-01',
    'like',
    1,                          -- position 1 of 5
    'onboarding-session-xyz'    -- special session ID for onboarding
);
```

These 5 interactions are **treated exactly the same as regular swipes** for training. The model doesn't know they came from onboarding — it just sees `(sarah, campus-listing-01, like)` and learns from it.

But because each listing represents a **distinct category**, those 5 swipes are maximally informative:
- Regular swipes on random listings might all be similar (e.g., 5 budget listings)
- Onboarding swipes **cover the full spectrum** of listing types
- This gives the model the widest possible signal from the fewest interactions

### Volume: How Many Listings Per Category?

For onboarding to work, you need **at least 1 high-quality listing per category per city**. Ideally 3–5 per category so the system can rotate and not show the same onboarding listings to every user.

| City | Budget | Premium | Campus | Spacious | Social | Total Needed |
|---|---|---|---|---|---|---|
| Toronto | 3–5 | 3–5 | 3–5 | 3–5 | 3–5 | 15–25 |
| Vancouver | 3–5 | 3–5 | 3–5 | 3–5 | 3–5 | 15–25 |
| Per city | | | | | | **15–25 listings** |

---

## How All 5 Datasets Connect

```
┌──────────────────────────────────────────────────────────────────┐
│                        TRAINING TIME                             │
│                                                                  │
│  Dataset A                    Dataset B          Dataset C       │
│  (Interactions)               (Users)            (Listings)      │
│  ┌─────────────────┐          ┌──────┐           ┌──────┐       │
│  │sarah | lst-03 |1│──refers──│sarah │──features──│lst-03│       │
│  │sarah | lst-07 |0│    to    │mike  │    from    │lst-07│       │
│  │mike  | lst-03 |1│         │priya │           │lst-05│       │
│  └─────────────────┘          └──────┘           └──────┘       │
│          │                       │                   │           │
│          │         ┌─────────────┘                   │           │
│          │         │                                 │           │
│          ▼         ▼                                 ▼           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   TWO-TOWER MODEL                        │    │
│  │                                                          │    │
│  │  For each (user, listing, label) in Dataset A:           │    │
│  │    1. Look up user features from Dataset B → 480 numbers │    │
│  │    2. Look up listing features from Dataset C → 923 nums │    │
│  │    3. Forward pass → predicted score (0-1)               │    │
│  │    4. Compare prediction vs actual label                 │    │
│  │    5. Backpropagate to adjust weights                    │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│                                                                  │
│  Dataset D              Dataset B                                │
│  (Roommate Pairs)       (Users — both sides)                     │
│  ┌──────────────────┐   ┌──────┐                                │
│  │sarah | mike  | 1 │───│sarah │                                │
│  │alex  | sarah | 0 │   │mike  │                                │
│  └──────────────────┘   │alex  │                                │
│          │              └──────┘                                 │
│          │                 │                                     │
│          ▼                 ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   SIAMESE NETWORK                        │    │
│  │                                                          │    │
│  │  For each (user_a, user_b, label) in Dataset D:          │    │
│  │    1. Look up user_a features from Dataset B → 480 nums  │    │
│  │    2. Look up user_b features from Dataset B → 480 nums  │    │
│  │    3. Pass BOTH through the SAME network                 │    │
│  │    4. Calculate distance between output embeddings       │    │
│  │    5. Small distance should = label 1 (compatible)       │    │
│  │    6. Backpropagate to adjust weights                    │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────┐
│                        INFERENCE TIME                            │
│                                                                  │
│  Sarah opens /discover                                           │
│       │                                                          │
│       ▼                                                          │
│  1. Fetch Sarah's profile from Dataset B → build 480-dim vector  │
│  2. Pass through trained User Tower → 64-dim embedding           │
│  3. For each feasible listing:                                   │
│       Fetch listing from Dataset C → build 923-dim vector        │
│       Pass through trained Item Tower → 64-dim embedding         │
│       Dot product with Sarah's embedding → score (0-1)           │
│  4. Blend AI score with rule-based score                         │
│  5. Sort listings by blended score → swipe stack                 │
│       │                                                          │
│       ▼                                                          │
│  Sarah swipes → new row added to Dataset A                       │
│  (The cycle continues)                                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Summary Table

| Dataset | What It Contains | Where It Lives | Exists Today? | Size Needed |
|---|---|---|---|---|
| **A: Interactions** | User swipes (like/pass) on listings | `user_interactions` table | ❌ No — needs Phase 0 + Phase 1 | 500+ rows to start training |
| **B: Users** | Profiles + preferences | `users` + `personal_preferences` tables | ✅ Yes | As many users as possible |
| **C: Listings** | Listing details + photos | `listings` + `listing_photos` tables | ✅ Yes | As many listings as possible |
| **D: Roommate Pairs** | Which users grouped together | Derived from `group_members` table | ✅ Yes (partial) | 100+ pairs to start training |
| **E: Listing Categories** | 5-category labels on listings + onboarding swipes | `listings.category` column + `user_interactions` | ❌ No — needs categorization script + onboarding UI | 15–25 categorized listings per city |
