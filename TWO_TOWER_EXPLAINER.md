# The Two-Tower Model — Explained

**Purpose:** This document explains how the Two-Tower Neural Network works in Padly, what it outputs, and how it determines the order of listings a user sees when swiping.

---

## 1. What Problem Does It Solve?

When a user opens the Discover page, they see a **stack of listings to swipe through**. The question is:

> **In what order should we show those listings?**

A bad order means the user swipes left (pass) 20 times before finding something they like. They get frustrated and leave.

A good order means the first 5 listings are all things they'd love. They engage more, swipe right, and the matching algorithm gets better data.

**The Two-Tower model decides this order.**

---

## 2. Why "Two Towers"?

Because there are **two completely different types of things** being compared:

| Tower | What It Represents | Input Data |
|---|---|---|
| **User Tower** | A person looking for housing | Budget, bio, lifestyle, school, past swipes |
| **Item Tower** | A listing being offered | Price, location, photos, description, amenities |

You can't feed a user profile and a listing into the **same** neural network — they have completely different structures and dimensions. So you build two separate networks that each compress their input into the **same-sized output** (a 64-dimensional vector). Then you compare those outputs.

Think of it like this:

> **User Tower** translates "who Sarah is" into a point in 64-dimensional space.
> **Item Tower** translates "what this listing is" into a point in the same 64-dimensional space.
> If the two points are **close together**, it's a good match.

---

## 3. Architecture Diagram

```
                USER TOWER                              ITEM TOWER
        ┌──────────────────────┐              ┌──────────────────────┐
        │                      │              │                      │
        │  Raw User Features   │              │  Raw Listing Features│
        │  (~480 numbers)      │              │  (~923 numbers)      │
        │                      │              │                      │
        │  • Budget: $800-1200 │              │  • Price: $2,100/mo  │
        │  • City: Toronto     │              │  • Bedrooms: 2       │
        │  • Bio: [384-dim]    │              │  • Desc: [384-dim]   │
        │  • Lifestyle: quiet  │              │  • Photos: [512-dim] │
        │  • Past swipes: [64] │              │  • Furnished: yes    │
        │                      │              │  • Amenities: gym,AC │
        │         │            │              │         │            │
        │  ┌──────┴──────┐     │              │  ┌──────┴──────┐     │
        │  │   480 → 256  │     │              │  │   923 → 256  │     │
        │  │   ReLU       │     │              │  │   ReLU       │     │
        │  │   Dropout 0.2│     │              │  │   Dropout 0.2│     │
        │  ├──────────────┤     │              │  ├──────────────┤     │
        │  │   256 → 128  │     │              │  │   256 → 128  │     │
        │  │   ReLU       │     │              │  │   ReLU       │     │
        │  │   Dropout 0.1│     │              │  │   Dropout 0.1│     │
        │  ├──────────────┤     │              │  ├──────────────┤     │
        │  │   128 → 64   │     │              │  │   128 → 64   │     │
        │  │   LayerNorm  │     │              │  │   LayerNorm  │     │
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
                            │ u · v       │
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
                              │  0.83   │  ← "83% chance Sarah likes this listing"
                              └─────────┘
```

---

## 4. Full Numerical Example

### Meet Sarah

Sarah is a UTM grad student looking for housing. Here are her features:

```
Budget:              $800 – $1,200/person
Target city:         Toronto
Move-in:             May 2026 → encoded as sin(5/12 × 2π) = 0.87, cos = 0.50
Wants furnished:     Yes → 1
Cleanliness:         Very clean → one-hot [0, 0, 0, 1]
Noise level:         Quiet → one-hot [0, 0, 1]
Smoking:             No smoking → one-hot [0, 0, 1]
Pets:                No pets → one-hot [0, 1]
Guests:              Occasionally → one-hot [0, 1, 0]
Bio:                 "Grad student at UTM, quiet, keeps to myself..."
                     → Sentence transformer turns this into a 384-dimensional vector
Past swipe history:  Average embedding of her 15 liked listings → 64-dim vector
Verification:        Email verified → one-hot [0, 1, 0]
Role:                Renter → one-hot [1, 0, 0]
```

**Concatenated into a single input vector:**

```
[800, 1200, 0.87, 0.50, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0,
 0.12, -0.34, 0.56, ...(384 bio numbers)...,
 0.08, 0.22, -0.15, ...(64 swipe history numbers)...,
 0, 1, 0, 1, 0, 0]

Total: ~480 numbers
```

### Meet the Listings

There are 8 active listings in Toronto that passed Sarah's hard constraints. We need to score all 8.

Let's trace **Listing #3** in detail:

```
Listing #3: "Modern 2BR near UTM campus"
─────────────────────────────────────────
Price:              $2,100/mo ($1,050/person)
Bedrooms:           2
Bathrooms:          1
Area:               780 sqft → normalized to 0.52
Furnished:          Yes → 1
Utilities included: No → 0
Deposit:            $500 → normalized to 0.25
Property type:      Entire place → one-hot [1, 0, 0]
Lease type:         Fixed term → one-hot [1, 0]
Description:        "Beautiful modern apartment, 5 min walk from UTM..."
                    → Sentence transformer → 384-dimensional vector
Photos:             3 photos of clean, well-lit rooms
                    → CLIP model → averaged into a 512-dimensional vector
Amenities:          {gym: true, ac: true, laundry: false, ...}
                    → multi-hot [1, 1, 0, 0, 1, ...] (15 amenity flags)
```

**Concatenated into a single input vector:**

```
[1050, 2, 1, 0.52, 1, 0, 0.25, 1, 0, 0, 1, 0,
 0.45, -0.11, 0.78, ...(384 description numbers)...,
 0.33, 0.67, -0.22, ...(512 photo numbers)...,
 1, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0]

Total: ~923 numbers
```

### What Happens Inside the Towers

**User Tower** processes Sarah's 480 numbers:

```
Layer 1:  480 inputs × 256 weights + bias → 256 neurons → ReLU → Dropout
Layer 2:  256 inputs × 128 weights + bias → 128 neurons → ReLU → Dropout
Layer 3:  128 inputs × 64 weights + bias  → 64 neurons  → LayerNorm

Output: u = [0.82, -0.31, 0.47, 0.15, -0.63, ..., 0.38]  (64 numbers)
```

**Item Tower** processes Listing #3's 923 numbers:

```
Layer 1:  923 inputs × 256 weights + bias → 256 neurons → ReLU → Dropout
Layer 2:  256 inputs × 128 weights + bias → 128 neurons → ReLU → Dropout
Layer 3:  128 inputs × 64 weights + bias  → 64 neurons  → LayerNorm

Output: v = [0.74, -0.22, 0.59, -0.08, -0.55, ..., 0.29]  (64 numbers)
```

### The Dot Product

Now we multiply each pair of corresponding numbers and sum them:

```
u = [0.82, -0.31,  0.47,  0.15, -0.63, ..., 0.38]
v = [0.74, -0.22,  0.59, -0.08, -0.55, ..., 0.29]
     ────   ────   ────   ────   ────        ────
    0.607 + 0.068 + 0.277 - 0.012 + 0.347 + ... + 0.110

dot(u, v) = 1.89  (raw score — sum of all 64 products)
```

### Sigmoid Activation

The raw dot product could be any number. We squash it into a probability:

```
σ(1.89) = 1 / (1 + e^(-1.89))
        = 1 / (1 + 0.151)
        = 1 / 1.151
        = 0.869
```

### ✅ The Output

```
┌─────────────────────────────────────────────────┐
│  Model output for Sarah × Listing #3:  0.869    │
│                                                  │
│  Interpretation:                                 │
│  "There is an 86.9% probability that Sarah       │
│   would swipe right on this listing."            │
└─────────────────────────────────────────────────┘
```

**That single number (0.869) is the only output.** The model doesn't say *why* — it doesn't say "because it's near campus" or "because it's furnished." It just learned from thousands of past swipes that users like Sarah tend to swipe right on listings like this.

---

## 5. Scoring All 8 Listings

We repeat this process for every listing that passed hard constraints. Sarah's 64-dim embedding stays the same — we only recompute the Item Tower for each listing:

```
Sarah's Embedding (computed once):
u = [0.82, -0.31, 0.47, 0.15, -0.63, ..., 0.38]

Listing #1: "Basement 1BR on Dundas"
    v₁ = [...64 numbers...]
    dot(u, v₁) → σ → 0.34

Listing #2: "Shared room near Erindale"
    v₂ = [...64 numbers...]
    dot(u, v₂) → σ → 0.52

Listing #3: "Modern 2BR near UTM campus"      ← our example
    v₃ = [...64 numbers...]
    dot(u, v₃) → σ → 0.87

Listing #4: "Renovated studio, downtown"
    v₄ = [...64 numbers...]
    dot(u, v₄) → σ → 0.71

Listing #5: "Cozy 2BR, 15 min from UTM"
    v₅ = [...64 numbers...]
    dot(u, v₅) → σ → 0.79

Listing #6: "Large 3BR, Mississauga"
    v₆ = [...64 numbers...]
    dot(u, v₆) → σ → 0.45

Listing #7: "Bright 2BR, en-suite laundry"
    v₇ = [...64 numbers...]
    dot(u, v₇) → σ → 0.83

Listing #8: "Furnished 1BR near Square One"
    v₈ = [...64 numbers...]
    dot(u, v₈) → σ → 0.61
```

---

## 6. Building the Swipe Stack

Now we have 8 scores. We also have the **rule-based scores** from the existing `scoring.py`. We blend them:

```
                                AI       Rule    Blend
Listing                        Score    Score    (60/40)     Rank
──────────────────────────────────────────────────────────────────
#3  Modern 2BR near UTM        0.87     82/100   84.8        1st  ⬆ TOP
#7  Bright 2BR, en-suite       0.83     78/100   81.0        2nd
#5  Cozy 2BR, 15 min           0.79     75/100   77.4        3rd
#4  Renovated studio           0.71     68/100   69.8        4th
#8  Furnished 1BR Sq One       0.61     72/100   65.4        5th
#2  Shared room Erindale       0.52     65/100   57.2        6th
#6  Large 3BR Mississauga      0.45     58/100   50.2        7th
#1  Basement 1BR Dundas        0.34     55/100   42.4        8th  ⬇ BOTTOM
```

**Blend formula (for 100+ swipes, ai_weight = 0.6):**
```
Blend Score = (0.6 × AI × 100) + (0.4 × Rule Score)

Example for Listing #3:
= (0.6 × 0.87 × 100) + (0.4 × 82)
= 52.2 + 32.8
= 84.8  ← this is out of 100
```

---

## 7. What Sarah's Swipe Stack Looks Like

When Sarah opens the `/discover` page, she sees this stack of cards — **the top card is the listing the system is most confident she'll like**:

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                                                        │  │
│  │              📸 [Beautiful listing photo]               │  │
│  │                                                        │  │
│  │  Modern 2BR near UTM campus               Score: 84.8 │  │
│  │  $2,100/mo · 2 bed · 1 bath · Furnished               │  │
│  │  📍 5 min walk from UTM                                │  │
│  │                                                        │  │
│  │         ✕ PASS          ⭐ SAVE          ❤️ LIKE        │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ NEXT IN STACK ────────────────────────────────────────┐  │
│  │  Bright 2BR, en-suite laundry              Score: 81.0 │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Cozy 2BR, 15 min from UTM                 Score: 77.4 │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Renovated studio, downtown                Score: 69.8 │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Furnished 1BR near Square One             Score: 65.4 │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Shared room near Erindale                 Score: 57.2 │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Large 3BR, Mississauga                    Score: 50.2 │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Basement 1BR on Dundas                    Score: 42.4 │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│                    END OF LISTINGS                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Note:** The user never sees the scores — they just see the cards in order. The scores are internal.

---

## 8. What Happens When Sarah Swipes

Every swipe gets logged and feeds back into the model:

```
Sarah swipes RIGHT on "Modern 2BR near UTM" (Listing #3)
    → POST /api/interactions
    → { user_id: sarah, listing_id: 3, action: "like" }
    → Stored in user_interactions table

Sarah swipes LEFT on "Bright 2BR, en-suite" (Listing #7)
    → POST /api/interactions
    → { user_id: sarah, listing_id: 7, action: "pass" }
    → Stored in user_interactions table
```

Over time, these swipes become **training data** for the model:

```
TRAINING DATA (grows with every swipe)
─────────────────────────────────────────────
| user_id | listing_id | label (like=1, pass=0) |
|---------|------------|------------------------|
| sarah   | 3          | 1                      |
| sarah   | 7          | 0                      |
| sarah   | 5          | 1                      |
| mike    | 3          | 1                      |
| mike    | 1          | 0                      |
| ...     | ...        | ...                    |
```

When the model is retrained (nightly or every 100 swipes), it learns:
- "Sarah likes listings close to UTM" → adjusts User Tower weights
- "Sarah doesn't care about en-suite laundry" → reduces that feature's influence for her
- "Listings near UTM with modern photos get swiped right by most users" → adjusts Item Tower weights

**The swipe stack gets smarter every time Sarah uses the app.**

---

## 9. The Full Pipeline — End to End

```
STEP 1: HARD CONSTRAINT FILTER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All 200 listings in Toronto
        │
        ▼
    feasible_pairs.py checks:
    City? Budget? Date? Bedrooms? ...
        │
        ▼
    8 listings survive (192 eliminated)


STEP 2: AI SCORING (Two-Tower Model)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Sarah's features ──► User Tower ──► u = [64 dims]
                                             │
    For each of 8 listings:                  │
        Listing features ──► Item Tower ──► v = [64 dims]
                                             │
                                      dot(u, v) → sigmoid
                                             │
                                        AI Score (0-1)


STEP 3: RULE-BASED SCORING (Existing System)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    For each of 8 listings:
        scoring.py checks:
        Bathrooms? Furnished? Utilities? Deposit? House Rules?
                                             │
                                        Rule Score (0-100)


STEP 4: BLEND
━━━━━━━━━━━━━
    Final Score = (ai_weight × AI Score × 100) + ((1 - ai_weight) × Rule Score)

    ai_weight depends on how many swipes Sarah has:
        < 20 swipes:   0.0 (pure rules)
        20-50 swipes:  0.3
        50-100 swipes: 0.5
        100+ swipes:   0.7


STEP 5: RANK → SWIPE STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━
    Sort 8 listings by Final Score (highest first)
        │
        ▼
    This becomes the card stack on /discover
    User swipes through top to bottom


STEP 6: SWIPE → TRAINING DATA → RETRAIN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Each swipe is logged in user_interactions
        │
        ▼
    Nightly: retrain model with new swipe data
        │
        ▼
    Tomorrow's swipe stack is even more personalized
```

---

## 10. Key Takeaways for the Professor

1. **The model outputs a single float (0-1)** representing the probability a user would swipe right on a listing.

2. **It does NOT replace the existing system.** Hard constraints still filter first. The AI score is blended with the rule-based score using an adaptive weight.

3. **The two towers are separate neural networks** because users and listings have fundamentally different feature structures, but they map into the same 64-dimensional embedding space.

4. **The dot product measures alignment** in that shared space — if a user's embedding and a listing's embedding point in the same direction, the model predicts a match.

5. **The swipe stack is simply the feasible listings sorted by blended score.** The highest-scored listing appears first.

6. **The system bootstraps from zero.** New users get pure rule-based ranking. As they swipe, the AI gradually takes over, personalizing the order based on learned behavior.

7. **The Gale-Shapley algorithm is completely unaffected.** The AI only changes the preference list ordering — the stable matching guarantees are preserved.
