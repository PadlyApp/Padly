# Padly AI — Research Findings & Design Decisions

> **Date:** 2026-03-09
> **Branch:** amaan/user-feedback
> **Authors:** Yousef + Amaan

---

## Table of Contents

1. [Industry Parallel — Airbnb 2018 Paper](#1-industry-parallel--airbnb-2018-paper)
2. [How the Airbnb Paper Relates to Padly](#2-how-the-airbnb-paper-relates-to-padly)
3. [Key Differences Between Airbnb and Padly](#3-key-differences-between-airbnb-and-padly)
4. [What the Airbnb Paper Actually Does (Training Details)](#4-what-the-airbnb-paper-actually-does-training-details)
5. [Current Padly Model — Inputs & Architecture](#5-current-padly-model--inputs--architecture)
6. [What Categorization Is Actually For](#6-what-categorization-is-actually-for)
7. [Planned Model Changes (Professor Feedback)](#7-planned-model-changes-professor-feedback)
8. [Roommate Matching — The Three-Step Problem](#8-roommate-matching--the-three-step-problem)
9. [User Feedback & UI Design](#9-user-feedback--ui-design)
10. [Cold Start Problem](#10-cold-start-problem)
11. [Roadmap Summary](#11-roadmap-summary)

---

## 1) Industry Parallel — Airbnb 2018 Paper

**Paper:** *"Real-time Personalization using Embeddings for Search Ranking at Airbnb"* (KDD 2018)

This paper is one of the closest industry parallels to what Padly is building. Airbnb faced the same core problem — matching users to listings in a two-sided marketplace — and solved it using embeddings.

### Short-Term Model (Listing Embeddings)

- **Input:** Click sessions — sequences of listing IDs a user clicked on, where a new session starts after 30 minutes of inactivity
- **Objective:** Skip-gram (word2vec style) — given a center clicked listing, predict the neighboring clicked listings within a context window
- **Training signal:** Positive pairs = (listing, neighboring listing) from the same session. Negative pairs = randomly sampled listings from the full vocabulary
- **Key tweak 1:** If a session ends in a booking, the booked listing is treated as a global context target for every listing in that session, even outside the normal window. This pulls the embeddings of clicked listings toward the eventually booked listing.
- **Key tweak 2:** Negative samples are drawn from the same market (same city) rather than the full vocabulary, making the model learn finer-grained preferences within a city rather than trivially distinguishing Paris from LA.
- **Scale:** Trained on 800M+ click sessions

### Long-Term Model (User-Type & Listing-Type Embeddings)

- **Problem:** Individual users don't have enough bookings to learn a reliable per-user embedding
- **Solution:** Bucket users into **user types** and listings into **listing types** using rule-based metadata (country, price, room type, capacity, device, language, reviews, etc.)
- **Input:** Time-ordered sequences of booking events, where each event is a (user_type, listing_type) tuple
- **Objective:** Skip-gram over these sequences — predict nearby user/listing types in booking history
- **Additional signal:** Host rejections are used as explicit negatives, so embeddings encode host-side preferences too
- **Scale:** Trained on booking sequences from 50M users

### Cold Start for New Listings

When a new listing is added and has no interaction history, Airbnb initializes its embedding by averaging the embeddings of 3 nearby listings with similar type and price. They report this covers more than 98% of new listings.

### Results

- Listing embeddings trained on click sessions improved booking performance when added to ranking
- For similar-listing recommendations, beat the old method by 20% CTR
- Launched user/listing-type embeddings as ranking features in production

---

## 2) How the Airbnb Paper Relates to Padly

| Concept | Airbnb | Padly |
|---|---|---|
| Shared embedding space | Users and listings embedded in same vector space | Same — Two-Tower dot product |
| Rule-based bucketing | Listing types and user types from metadata | 6 listing categories from `categorize_and_map.py` |
| Hard constraint filtering | Filter candidates before ranking | `passes_hard_constraints()` in pipeline |
| Cold start for new listings | Average embeddings of nearby similar listings | Not implemented yet — needed for production |
| Behavioral signal | 800M real click sessions | Synthetic liked listings (for now) |

The categorization approach in `categorize_and_map.py` independently arrived at the same idea as Airbnb's listing-type bucketing. That's a good sign — it validates the approach.

---

## 3) Key Differences Between Airbnb and Padly

### Architecture
- **Airbnb:** Uses word2vec / skip-gram (self-supervised, learned from behavioral sequences). No explicit match score.
- **Padly:** Uses a Two-Tower neural net with supervised labels. Explicitly computes a `_match_score()` and trains the model to predict it. Closer to the **YouTube Two-Tower paper** in architecture.

### The Three-Way Matching Problem
This is where Padly is fundamentally more complex than Airbnb:

- **Airbnb:** `user → listing` (one-to-one)
- **Padly:** `user → user → group → listing` (three steps)

Padly doesn't just match users to listings. It first matches users to compatible roommates, forms a group, and then matches that group to a listing as a unit. No major company has published a clean solution to this specific setup, which makes Padly's matching system genuinely novel.

### Data
- **Airbnb:** Real behavioral data (clicks, bookings, rejections)
- **Padly:** Synthetic data with simulated preferences (for now)

### Sequential Signal
- **Airbnb:** Trains on ordered sequences of interactions — the order matters
- **Padly:** Currently treats every renter-listing pair independently with no notion of sequence

---

## 4) What the Airbnb Paper Actually Does (Training Details)

In plain terms, Airbnb trains on two kinds of sequences:

1. **Click sequences of listing IDs** → for short-term intent (what does this user want right now?)
2. **Booking sequences of (user_type, listing_type) events** → for long-term preference (what kind of person is this user overall?)

The embeddings are trained separately from the final ranker. The embedding similarities are later used as **features in a downstream ranking model**, rather than one single end-to-end model consuming all raw features.

This is different from Padly's current approach where the Two-Tower model is trained end-to-end to predict match scores directly.

---

## 5) Current Padly Model — Inputs & Architecture

### User Tower Input (`encode_renter_features`)

**Profile features:**
```
age, household_size, income, credit_score,
budget_min, budget_max,
desired_beds, desired_baths, desired_sqft_min,
has_cats, has_dogs, is_smoker,
needs_wheelchair, has_ev, wants_furnished,
pref_lat, pref_lon, max_distance_km,
laundry_pref, parking_pref, move_urgency
```

**Type preference flags (12 columns):**
```
type_pref_apartment, type_pref_house, type_pref_condo, etc.
```

**User feedback (6 columns, if feedback CSV is provided):**
```
cat_0_Budget_Compact, cat_1_Spacious_Family, cat_2_Pet-Friendly,
cat_3_Premium_Luxury, cat_4_Urban_Convenience, cat_5_Accessible_Modern
```
Normalized so they sum to 1 per user.

### Item Tower Input (`encode_listing_features`)

**Raw features:**
```
price, sqfeet, beds, baths,
cats_allowed, dogs_allowed, smoking_allowed,
wheelchair_access, electric_vehicle_charge, comes_furnished,
lat, long
```

**One-hot encoded categoricals:**
```
type (apartment, house, condo, etc.)
laundry_options
parking_options
```

**Category one-hot (6 columns, if listing categories CSV is provided):**
```
[1, 0, 0, 0, 0, 0] = Budget Compact
[0, 1, 0, 0, 0, 0] = Spacious Family
etc.
```

### Model Architecture

- Two towers, each with Dense(256) → Dropout → Dense(128) → Dense(embedding_dim) → L2 normalize
- Dot product of the two normalized embeddings → scalar similarity
- Dense(2) projection → 2-class logits [no-match, match]
- Trained with SparseCategoricalCrossentropy

---

## 6) What Categorization Is Actually For

**Important distinction:** Categorization is a data generation tool, not a model feature.

The 6 listing categories exist purely to simulate realistic user behavior when generating synthetic training data. The idea is:

1. Bucket listings into 6 types (Budget Compact, Spacious Family, Pet-Friendly, etc.)
2. Compute each synthetic renter's affinity for each category based on their profile
3. Sample liked listings weighted by that affinity
4. This produces a realistic `liked_listings_detail.csv` where users consistently like similar types of listings

The model itself should NOT know about categories. If we feed category labels as features, we are telling the model the answer. The whole point is for the model to discover preference patterns on its own from raw features.

---

## 7) Planned Model Changes (Professor Feedback)

### What changes and why

The professor's feedback is to remove all categorization knowledge from the model and replace it with raw behavioral signal — the actual liked listings themselves.

### Change 1: Remove category features from user tower
**Remove:** The 6 `cat_0` through `cat_5` feedback columns from user features
**Why:** These are category-derived and leak the hand-crafted bucketing into the model

### Change 2: Remove category one-hot from listing tower
**Remove:** The 6-dimensional category one-hot appended to listing features
**Why:** Same reason — we don't want the model to know about our invented categories

### Change 3: Add averaged liked listings to user tower
**Add:** For each user, aggregate their liked listings from `liked_listings_detail.csv` into a fixed-size vector by averaging:
- `mean_price`
- `mean_beds`
- `mean_sqfeet`
- mean of one-hot encoded `listing_type` (soft distribution over types)

**Why:** This is raw behavioral signal — what listings did this user actually like? The model can learn preferences from this without any category knowledge baked in. This is much closer to what Airbnb does (learning from behavioral sequences).

**The file:** `liked_listings_detail.csv` already exists and has exactly what we need:
```
renter_id, listing_id, listing_price, listing_beds, listing_sqfeet, listing_type, category_id, category_name
```
We use `listing_price`, `listing_beds`, `listing_sqfeet`, and `listing_type` only. We ignore `category_id` and `category_name`.

### Files to modify
- `generate_renter_data.py` → load `liked_listings_detail.csv`, aggregate per user, merge onto renter rows, update `encode_renter_features()` and `encode_listing_features()`

---

## 8) Roommate Matching — The Three-Step Problem

### The full matching flow

```
Step 1: user ←→ user  (roommate compatibility)
Step 2: compatible users → group  (group formation)
Step 3: group → listing  (housing match)
```

### Step 1: User-User Matching

**Core idea:** Use listing interaction behavior as a proxy for lifestyle compatibility. Two users who consistently like the same types of listings probably have compatible lifestyles and preferences.

**What listing behavior tells you:**
- Budget range
- Location preference
- Amenities they care about (pets, parking, furnished, etc.)
- Housing type preference

**What it doesn't tell you (soft constraints — need onboarding questionnaire):**
- Sleep schedule (night owl vs early riser)
- Cleanliness standards
- Guests / social habits
- Noise tolerance
- Work from home vs office
- Cooking vs ordering food
- Chore preferences
- Introverted vs extroverted at home

**Profile information to surface when browsing roommates:**
- Where they are originally from
- Ethnicity
- Age
- Company they work at / are joining
- Where they study

This information lets users make personal decisions — maybe you want a roommate who works at the same company for the commute, or maybe you specifically want someone from a different background.

**On whether a separate model is needed:**
If users are already embedded in the same vector space from their listing interactions, you can measure cosine similarity between two user embeddings directly — no separate model needed. Users close in embedding space are already compatible by definition.

### Step 2: Mutual Opt-In (Double Opt-In)

Users are shown compatible roommates and both have to choose each other for a match to form. This is a mutual like / double opt-in mechanic (similar to Tinder's match system). Neither person sees a one-sided rejection — only mutual matches are surfaced.

### Step 3: Group-to-Listing Matching

Once a group is formed, the group needs a single representation to match against listings. Options include averaging user embeddings or taking the most constrained member's preferences. This is an open problem and will be figured out as the product matures.

---

## 9) User Feedback & UI Design

### For listing browsing (collecting behavioral signal)

**Recommended approach: Browse and save (implicit feedback)**
- Show listing cards, users click into ones they find interesting
- Track: clicks, saves/hearts, time spent, return visits
- This is what Zillow and Apartments.com do — feels natural for housing
- Housing is a high-stakes decision; forcing a binary swipe feels too trivial

**Why not swipe for listings:**
- Swiping feels low-stakes; apartments are a big life decision
- People want to browse at their own pace, not be forced into instant binary judgments

### For roommate browsing

**Recommended approach: Swipe (explicit feedback)**
- Show user profiles with compatibility info, swipe right to express interest
- Mutual match = both swiped right on each other
- Swipe makes sense here — it's a person, stakes feel lower per swipe, and the mutual match mechanic maps perfectly onto the double opt-in

---

## 10) Cold Start Problem

### New listing cold start
When a new listing is added with no interaction history, the model has no embedding for it.

**Solution (from Airbnb paper):** Average the embeddings of 3 nearby listings with similar type and price. The new listing borrows a representation from its neighbors until it accumulates real interactions.

**Not implemented yet — needed before production launch.**

### New user cold start
When a new user signs up, they have no liked listings, so the averaged liked listing features vector would be all zeros. The model has no useful signal.

**Planned solution: Onboarding swipe session**
- Show the new user 10-15 listing cards during onboarding
- Ask them to quickly like or dislike each one
- Now we have enough interactions to build their liked listings vector
- Doubles as a good UX moment — feels like personalization setup, not a survey
- This is what Spotify does with the genre picker on signup

**Status:** To be implemented when the UI is built.

---

## 11) Training Results — Post Phase 1-3 Changes (2026-03-09)

### What changed
- **Phase 1:** Removed all category-derived features from both towers (no more `cat_0`–`cat_5` in user tower, no more category one-hot in item tower)
- **Phase 2:** Added averaged liked listing features to the user tower — for each user, `listing_price`, `listing_beds`, `listing_sqfeet`, and one-hot `listing_type` are averaged across all liked listings and appended as raw behavioral signal
- **Phase 3:** Regenerated training data and retrained the model

### Data stats
| | Value |
|---|---|
| Total training pairs | 300,000 |
| Positives | 157,684 (52.56%) |
| Negatives | 142,316 (47.44%) |
| User feature dimension | 50 |
| Item feature dimension | 38 |

### Training results (10 epochs, batch size 256, lr 1e-3)

| Epoch | Train Acc | Train Loss | Val Acc | Val Loss |
|---|---|---|---|---|
| 1 | 74.96% | 0.5189 | 82.93% | 0.4052 |
| 2 | 83.56% | 0.3754 | 86.84% | 0.3155 |
| 3 | 86.58% | 0.3097 | 88.66% | 0.2712 |
| 4 | 88.04% | 0.2748 | 89.94% | 0.2440 |
| 5 | 88.83% | 0.2553 | 90.54% | 0.2282 |
| 6 | 89.49% | 0.2404 | 91.01% | 0.2155 |
| 7 | 89.92% | 0.2307 | 91.42% | 0.2065 |
| 8 | 90.38% | 0.2220 | 91.63% | 0.2013 |
| 9 | 90.58% | 0.2168 | 91.78% | 0.1973 |
| 10 | 90.77% | 0.2130 | **92.24%** | **0.1903** |

### Model parameters

input → Dense(256) → Dense(128) → Dense(64)                                                                                                                                                                                               
                                                                                                                                                                                                                                            
  Each Dense layer connects every neuron from the previous layer to every neuron in the next layer. So:                                                                                                                                     
                                                                                                                                                                                                                                            
  Layer 1: Dense(256)
  - Takes the input (50 features for user, 38 for item)
  - Connects each input feature to each of the 256 neurons
  - 50 × 256 = the weights (one weight per connection)
  - + 256 = one bias per neuron
  - Result: 13,056 params

  Layer 2: Dense(128)
  - Now the input is the 256 neurons from the previous layer
  - Connects each of those 256 to each of the 128 new neurons
  - 256 × 128 = the weights
  - + 128 = one bias per neuron
  - Result: 32,896 params

  Layer 3: Dense(64)
  - Input is now 128 neurons from previous layer
  - 128 × 64 = weights
  - + 64 = biases
  - Result: 8,256 params

Each Dense layer has `(input_dim × output_dim) + output_dim` parameters (weights + biases).

**User Tower (input = 50):**
| Layer | Calculation | Params |
|---|---|---|
| Dense(256) | (50 × 256) + 256 | 13,056 |
| Dense(128) | (256 × 128) + 128 | 32,896 |
| Dense(64) | (128 × 64) + 64 | 8,256 |
| **Tower total** | | **54,208** |

**Item Tower (input = 38):**
| Layer | Calculation | Params |
|---|---|---|
| Dense(256) | (38 × 256) + 256 | 9,984 |
| Dense(128) | (256 × 128) + 128 | 32,896 |
| Dense(64) | (128 × 64) + 64 | 8,256 |
| **Tower total** | | **51,136** |

**Logits layer:**
| Layer | Calculation | Params |
|---|---|---|
| Dense(2, no bias) | 1 × 2 | 2 |

The input to the logits layer is the dot product of the two tower outputs — a scalar (shape `(None, 1)`) — so it only needs 2 weights to project to 2 classes. No bias because `use_bias=False`.

The two towers have different parameter counts only because of their first layer — user input is 50 dims vs item input is 38 dims. Everything after that is identical.

| | Params |
|---|---|
| User tower | 54,208 |
| Item tower | 51,136 |
| Logits layer | 2 |
| **Total** | **105,346 (411.51 KB)** |

### Notes
- Val accuracy is consistently higher than train accuracy across all epochs — no overfitting, the model generalizes well
- Still improving at epoch 10 — running more epochs would likely push accuracy higher
- Model saved to `app/ai/artifacts/two_tower_baseline.keras`

---

## 12) Loss Function Comparison — Softmax vs Binary Cross-Entropy

Both models trained on the same data with the same architecture, hyperparameters, and seed. The only difference is the loss function and output layer.

### Architecture difference
| | Softmax | BCE |
|---|---|---|
| Output layer | `Dense(2, use_bias=False)` → 2-class logits | `Dense(1, use_bias=False, activation="sigmoid")` → match probability |
| Output params | 2 | 1 |
| Total params | 105,346 | 105,345 |
| Loss function | SparseCategoricalCrossentropy(from_logits=True) | BinaryCrossentropy() |
| Metric | SparseCategoricalAccuracy | BinaryAccuracy |

### Results

**Softmax:**
| Epoch | Train Acc | Train Loss | Val Acc | Val Loss |
|---|---|---|---|---|
| 1 | 74.96% | 0.5189 | 82.93% | 0.4052 |
| 5 | 88.83% | 0.2553 | 90.54% | 0.2282 |
| 10 | 90.77% | 0.2130 | **92.24%** | **0.1903** |

**Binary Cross-Entropy:**
| Epoch | Train Acc | Train Loss | Val Acc | Val Loss |
|---|---|---|---|---|
| 1 | 73.19% | 0.5778 | 81.02% | 0.4859 |
| 5 | 86.87% | 0.3196 | 88.58% | 0.2890 |
| 10 | 90.05% | 0.2366 | **91.47%** | **0.2162** |

### Head-to-head at epoch 10
| Metric | Softmax | BCE | Winner |
|---|---|---|---|
| Val Accuracy | 92.24% | 91.47% | Softmax (+0.77%) |
| Val Loss | 0.1903 | 0.2162 | Softmax |
| Train Accuracy | 90.77% | 90.05% | Softmax |
| Output interpretability | Needs softmax post-processing | Direct probability (0–1) | BCE |
| Params | 105,346 | 105,345 | Tie |

### Verdict
Softmax wins on accuracy and loss at 10 epochs. BCE converges slightly slower but both models are still improving at epoch 10 — BCE may close the gap at more epochs.

However the accuracy difference is small (0.77%). The practical advantage of BCE is that its output is a **direct match probability between 0 and 1** that you can show users as a compatibility score (e.g. "92% match") without any post-processing. Softmax requires an extra `softmax(logits)[1]` step to extract the same value.

**Current decision:** BCE is the saved baseline (`two_tower_baseline.keras`) and the default loss when running `two_tower_baseline.py`. Softmax is kept for reference. Both models are saved separately:
- `app/ai/artifacts/two_tower_baseline.keras` → BCE (main)
- `app/ai/artifacts/two_tower_softmax.keras` → Softmax (reference)
- `app/ai/artifacts/two_tower_bce.keras` → BCE (reference copy)

---

## 12) Roadmap Summary

| Item | Status | Notes |
|---|---|---|
| Two-Tower model | Done | Trained on synthetic data |
| Listing categorization | Done | `categorize_and_map.py` |
| User feedback simulation | Done | `liked_listings_detail.csv` |
| Remove category features from model | Done | Phase 1 |
| Add averaged liked listings to user tower | Done | Phase 2 |
| Retrain and validate | Done | Phase 3 — 92.2% val accuracy |
| Roommate matching (user-user) | Not started | Use user embedding similarity + soft constraints questionnaire |
| Group formation | Not started | After roommate matching |
| Group-to-listing matching | Not started | After group formation |
| Cold start for new listings | Not started | Needed before production |
| Cold start for new users (onboarding swipe) | Not started | Needed with UI |
| Real behavioral data (replace synthetic) | Not started | Needed for production quality |
| Sequential training (like Airbnb skip-gram) | Not started | Long-term improvement |

---

*This document covers research findings and design decisions made as of 2026-03-09. It should be updated as the system evolves.*
