# The Two-Tower Model — Explained

**Purpose:** This document explains how the Two-Tower Neural Network works in Padly, what it outputs, and how it determines the order of listings a user sees.

**Last updated:** 2026-03-09 — reflects the actual trained model, not a planned future state.

---

## 1. What Problem Does It Solve?

When a user opens the app, they see a list of listings. The question is:

> **In what order should we show those listings?**

A bad order means the user scrolls past 20 listings before finding something they like. A good order means the first few listings are things they'd love.

**The Two-Tower model decides this order.**

---

## 2. Why "Two Towers"?

Because there are **two completely different types of things** being compared:

| Tower | What It Represents | Input Data |
|---|---|---|
| **User Tower** | A person looking for housing | Budget, lifestyle, preferences, past liked listings |
| **Item Tower** | A listing being offered | Price, location, bedrooms, amenities |

Each tower compresses its input into a **64-dimensional vector** (an embedding). Then we compare those embeddings.

> **User Tower** translates "who Sarah is" into a point in 64-dimensional space.
> **Item Tower** translates "what this listing is" into a point in the same 64-dimensional space.
> If the two points are **close together**, it's a good match.

---

## 3. Architecture — What's Actually Built

```
                USER TOWER                              ITEM TOWER
        ┌──────────────────────┐              ┌──────────────────────┐
        │                      │              │                      │
        │  Raw User Features   │              │  Raw Listing Features│
        │  (50 numbers)        │              │  (38 numbers)        │
        │                      │              │                      │
        │  • Budget min/max    │              │  • Price             │
        │  • Desired beds/baths│              │  • Beds / Baths      │
        │  • Has cats/dogs     │              │  • Sqft              │
        │  • Wants furnished   │              │  • Furnished         │
        │  • Location (lat/lon)│              │  • Lat / Long        │
        │  • Household size    │              │  • Cats/Dogs allowed │
        │  • Avg liked price   │              │  • Smoking allowed   │
        │  • Avg liked beds    │              │  • Wheelchair access │
        │  • Avg liked sqft    │              │  • EV charging       │
        │  • Liked type dist.  │              │  • Property type     │
        │  • Type preferences  │              │  • Laundry / Parking │
        │                      │              │                      │
        │         │            │              │         │            │
        │  ┌──────┴──────┐     │              │  ┌──────┴──────┐     │
        │  │   50 → 256   │     │              │  │   38 → 256   │     │
        │  │   ReLU       │     │              │  │   ReLU       │     │
        │  │   Dropout 0.2│     │              │  │   Dropout 0.2│     │
        │  ├──────────────┤     │              │  ├──────────────┤     │
        │  │   256 → 128  │     │              │  │   256 → 128  │     │
        │  │   ReLU       │     │              │  │   ReLU       │     │
        │  ├──────────────┤     │              │  ├──────────────┤     │
        │  │   128 → 64   │     │              │  │   128 → 64   │     │
        │  │   L2 Norm    │     │              │  │   L2 Norm    │     │
        │  └──────┬──────┘     │              │  └──────┬──────┘     │
        │         │            │              │         │            │
        │    u = [64 dims]     │              │    v = [64 dims]     │
        │  User Embedding      │              │  Item Embedding      │
        └─────────┼────────────┘              └─────────┼────────────┘
                  │                                     │
                  └───────────────┐   ┌─────────────────┘
                                  │   │
                                  ▼   ▼
                            ┌────────────┐
                            │ Dot Product │
                            │  u · v      │
                            └──────┬─────┘
                                   │
                                   ▼
                            ┌────────────┐
                            │  Sigmoid    │
                            │  σ(u · v)   │
                            └──────┬─────┘
                                   │
                                   ▼
                              ┌─────────┐
                              │  0.83   │  ← "83% match"
                              └─────────┘
```

### Parameter count

Each Dense layer has `(input × output) + output` parameters (weights + biases):

**User Tower (input = 50):**
| Layer | Calculation | Params |
|---|---|---|
| Dense(256) | (50 × 256) + 256 | 13,056 |
| Dense(128) | (256 × 128) + 128 | 32,896 |
| Dense(64) | (128 × 64) + 64 | 8,256 |
| **Total** | | **54,208** |

**Item Tower (input = 38):**
| Layer | Calculation | Params |
|---|---|---|
| Dense(256) | (38 × 256) + 256 | 9,984 |
| Dense(128) | (256 × 128) + 128 | 32,896 |
| Dense(64) | (128 × 64) + 64 | 8,256 |
| **Total** | | **51,136** |

**Output layer:** `Dense(1, use_bias=False)` → 1 param

**Grand total: 105,345 parameters (411.50 KB)**

The two towers differ only in their first layer because user input is 50-dimensional vs listing input is 38-dimensional. Everything after that is identical.

---

## 4. What Goes Into Each Tower

### User Tower (50 features)

**Profile features (33):**
```
age, household_size, income, credit_score,
budget_min, budget_max,
desired_beds, desired_baths, desired_sqft_min,
has_cats, has_dogs, is_smoker,
needs_wheelchair, has_ev, wants_furnished,
pref_lat, pref_lon, max_distance_km,
laundry_pref, parking_pref, move_urgency,
type_pref_apartment, type_pref_house, type_pref_condo ... (12 type flags)
```

**Averaged liked listing features (17) — behavioral signal:**
```
liked_mean_price       ← average price of listings this user liked
liked_mean_beds        ← average beds
liked_mean_sqfeet      ← average sqft
liked_type_apartment   ← what fraction of liked listings were apartments
liked_type_house       ← what fraction were houses
... (one per listing type)
```

The liked listing features are the key behavioral signal. Instead of guessing what a user wants from their profile alone, we look at what they actually interacted with. A user who keeps liking $900 studio apartments tells the model something their stated budget alone might not.

**Why no text embeddings or photo embeddings?**
Those features (bio text, listing descriptions, photos) are planned for a future version once the app has real users. The current model is trained on structured data only.

### Item Tower (38 features)

**Numeric (12):**
```
price, sqfeet, beds, baths,
cats_allowed, dogs_allowed, smoking_allowed,
wheelchair_access, electric_vehicle_charge, comes_furnished,
lat, long
```

**One-hot encoded categoricals (26):**
```
type_*      → 12 columns (apartment, house, condo, etc.)
laundry_*   → 6 columns (w/d in unit, hookups, etc.)
parking_*   → 8 columns (garage, street, etc.)
```

**No category labels.** The 6 listing categories (Budget Compact, Spacious Family, etc.) were used only to simulate realistic training data. The model itself never sees them — it learns preference patterns from raw features on its own.

---

## 5. Full Numerical Example

### Meet Sarah

Sarah is a UTM grad student looking for housing:

```
Budget:              $800 – $1,200/month
Desired beds:        2
Wants furnished:     Yes → 1
Has cats:            Yes → 1
Location:            UTM area (lat: 43.549, lon: -79.663)
Max distance:        20 km
Household size:      2
```

**Liked listing averages (from her past interactions):**
```
liked_mean_price:    $1,050    ← she tends to like ~$1,050 listings
liked_mean_beds:     2.0       ← consistently likes 2-bed places
liked_mean_sqfeet:   820       ← prefers ~820 sqft
liked_type_apartment: 0.80     ← 80% of her liked listings are apartments
liked_type_house:    0.20      ← 20% are houses
```

**Concatenated into a 50-dimensional input vector** (after z-scoring continuous features):
```
[-0.4, 2.0, -0.3, 0.7, -0.8, 0.2, 2.0, 0.5, 0.6,
  1,   1,   0,   0,   0,   1,  43.5, -79.7,  20.0,
  0,   0,   1,   1,   0,   0,   0,   0,   0,   0,
  0,   0,   0,   0,   0,
  -0.3, 0.8, -0.1, 0.80, 0.20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

Total: 50 numbers
```

### The Listing

```
"Modern 2BR near UTM campus"
─────────────────────────────
Price:          $2,100/mo ($1,050/person)
Beds:           2
Baths:          1
Sqft:           780
Furnished:      Yes → 1
Cats allowed:   Yes → 1
Dogs allowed:   No  → 0
Smoking:        No  → 0
Wheelchair:     No  → 0
EV charging:    No  → 0
Lat/Long:       43.551, -79.661
Type:           apartment → type_apartment = 1, all others = 0
Laundry:        w/d in unit → laundry_w/d in unit = 1, all others = 0
Parking:        off-street → parking_off-street parking = 1, others = 0
```

**Concatenated into a 38-dimensional input vector** (after z-scoring price, sqft, beds, baths):
```
[-0.1, 0.4, 0.3, -0.2, 1, 0, 0, 0, 0, 1, 43.5, -79.7,
  1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,   ← type one-hot
  0, 0, 0, 0, 0, 1,                       ← laundry one-hot
  0, 0, 0, 0, 0, 1, 0, 0]                 ← parking one-hot

Total: 38 numbers
```

### What Happens Inside the Towers

**User Tower** processes Sarah's 50 numbers:

```
Layer 1:  50 inputs  → 256 neurons → ReLU → Dropout(0.2)
Layer 2:  256 inputs → 128 neurons → ReLU
Layer 3:  128 inputs → 64 neurons  → L2 Normalize

Output: u = [0.82, -0.31, 0.47, 0.15, -0.63, ..., 0.38]  (64 numbers, unit length)
```

**Item Tower** processes the listing's 38 numbers:

```
Layer 1:  38 inputs  → 256 neurons → ReLU → Dropout(0.2)
Layer 2:  256 inputs → 128 neurons → ReLU
Layer 3:  128 inputs → 64 neurons  → L2 Normalize

Output: v = [0.74, -0.22, 0.59, -0.08, -0.55, ..., 0.29]  (64 numbers, unit length)
```

### The Dot Product

Both embeddings are L2-normalized (unit length), so the dot product is equivalent to cosine similarity — it measures how closely the two vectors are aligned:

```
u = [0.82, -0.31,  0.47,  0.15, -0.63, ..., 0.38]
v = [0.74, -0.22,  0.59, -0.08, -0.55, ..., 0.29]
     ────   ────   ────   ────   ────        ────
    0.607 + 0.068 + 0.277 - 0.012 + 0.347 + ... + 0.110

dot(u, v) = 1.89
```

### Sigmoid → Match Score

The dot product is passed through a single learned weight (Dense(1, use_bias=False)) then sigmoid:

```
σ(1.89 × w) = 1 / (1 + e^(-1.89 × w))
             ≈ 0.87
```

### ✅ The Output

```
┌─────────────────────────────────────────────────┐
│  Model output for Sarah × this listing:  0.87   │
│                                                  │
│  Displayed to frontend as: "87% match"           │
└─────────────────────────────────────────────────┘
```

**That single number is the only output.** The model doesn't say *why* — it learned from training data that users with Sarah's profile tend to match with listings like this.

---

## 6. Loss Function — Binary Cross-Entropy

The model is trained with **Binary Cross-Entropy (BCE)**:

```
Loss = -[y × log(ŷ) + (1 - y) × log(1 - ŷ)]

Where:
  y  = true label (1 if good match, 0 if not)
  ŷ  = model's predicted probability
```

BCE was chosen over softmax because:
- The problem is binary (match or no match) — BCE is the natural fit
- The output is a direct probability between 0 and 1, ready to display without post-processing
- Softmax with 2 classes is redundant for a binary problem

### Training results (10 epochs, 300k pairs)

| Epoch | Train Acc | Val Acc |
|---|---|---|
| 1 | 73.19% | 81.02% |
| 5 | 86.87% | 88.58% |
| 10 | 90.05% | **91.47%** |

Val accuracy consistently higher than train accuracy — no overfitting.

---

## 7. Scoring All Listings

Sarah's user embedding is computed **once**. Then we score every listing that passed hard constraints by running each through the item tower and taking the dot product:

```
Sarah's Embedding (computed once):
u = [0.82, -0.31, 0.47, 0.15, -0.63, ..., 0.38]

Listing #1: "Basement 1BR on Dundas"        → 0.34
Listing #2: "Shared room near Erindale"     → 0.52
Listing #3: "Modern 2BR near UTM campus"    → 0.87  ← our example
Listing #4: "Renovated studio, downtown"    → 0.71
Listing #5: "Cozy 2BR, 15 min from UTM"    → 0.79
Listing #6: "Large 3BR, Mississauga"        → 0.45
Listing #7: "Bright 2BR, en-suite laundry" → 0.83
Listing #8: "Furnished 1BR near Square One" → 0.61
```

Sort by score descending → this is the order shown to Sarah.

---

## 8. The API Endpoint

The model is exposed to the frontend via a single endpoint:

```
POST /api/recommendations
```

**Request (frontend sends):**
```json
{
  "budget_max": 1200,
  "desired_beds": 2,
  "has_cats": 1,
  "pref_lat": 43.549,
  "pref_lon": -79.663,
  "top_n": 20
}
```

**Response (frontend gets back):**
```json
{
  "status": "success",
  "count": 8,
  "recommendations": [
    {
      "listing_id": "abc123",
      "match_score": 0.87,
      "match_percent": "87%",
      "title": "Modern 2BR near UTM campus",
      "price_per_month": 2100,
      "number_of_bedrooms": 2,
      "city": "Mississauga"
    },
    ...
  ]
}
```

The `match_percent` field is ready to render directly. The backend handles all filtering, encoding, and scoring — frontend just sends preferences and displays results.

Interactive docs available at `/docs` on the backend server.

---

## 9. The Full Pipeline — End to End

```
STEP 1: HARD CONSTRAINT FILTER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All active listings in DB
        │
        ▼
    recommender.py checks:
    Budget? Cats? Dogs? Smoking? Wheelchair?
        │
        ▼
    Eligible listings survive


STEP 2: AI SCORING (Two-Tower Model)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Sarah's features ──► User Tower ──► u = [64 dims]
                                             │
    For each eligible listing:               │
        Listing features ──► Item Tower ──► v = [64 dims]
                                             │
                                      dot(u, v) → sigmoid
                                             │
                                     Match Score (0-1)


STEP 3: RANK → RETURN
━━━━━━━━━━━━━━━━━━━━━
    Sort listings by match score (highest first)
        │
        ▼
    Return top N with match_score + match_percent


STEP 4: SWIPE → FUTURE TRAINING DATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Each save/like is logged
        │
        ▼
    When enough real data accumulates → fine-tune model
        │
        ▼
    Recommendations get more personalized over time
```

---

## 10. Key Takeaways

1. **The model outputs a single float (0–1)** representing match probability, displayed as "X% match" in the UI.

2. **The two towers are separate networks** because users and listings have different feature structures, but both map into the same 64-dimensional embedding space.

3. **The dot product measures alignment** — if a user's embedding and a listing's embedding point in the same direction (cosine similarity ≈ 1), it's a strong match.

4. **The liked listing averages are the key behavioral signal.** Rather than just using profile data, the model also knows what listings a user has actually interacted with.

5. **Categorization is not a model feature.** The 6 listing categories (Budget Compact, Spacious Family, etc.) were only used to generate realistic synthetic training data. The model learns preference patterns from raw features on its own.

6. **Cold start for new users:** A new user with no interaction history gets zeros for the liked listing features. The model falls back to their profile features only. The fix is an onboarding swipe session (10-15 listings at signup) to seed the behavioral signal.

7. **The model is currently trained on synthetic data.** It's a solid baseline, but quality improves significantly once real user interactions replace the synthetic training pairs.
