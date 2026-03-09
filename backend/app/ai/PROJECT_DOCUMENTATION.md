# Padly AI Component – Full Project Documentation

> **Date:** 2026-03-03  
> **Authors:** Amaan (development) + AI assistant (implementation)  
> **Codebase:** `backend/app/ai/`

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [What the Assignment Required](#2-what-the-assignment-required)
3. [The Dataset](#3-the-dataset)
4. [Two-Tower Neural Network Architecture](#4-two-tower-neural-network-architecture)
5. [Data Pipeline – End to End](#5-data-pipeline--end-to-end)
6. [Listing Categorization (6 Categories)](#6-listing-categorization-6-categories)
7. [User-to-Listing Mapping & Feedback Arrays](#7-user-to-listing-mapping--feedback-arrays)
8. [Integrating Feedback into the Model](#8-integrating-feedback-into-the-model)
9. [Training & Results](#9-training--results)
10. [File Inventory](#10-file-inventory)
11. [How to Run Everything](#11-how-to-run-everything)
12. [Current Limitations](#12-current-limitations)
13. [Future Improvements](#13-future-improvements)

---

## 1) Project Overview

**Padly** is a rental matching platform that works like a "Tinder for housing." Users (renters) swipe right on listings they like and left on listings they don't. The platform then uses a combination of AI-powered scoring and a stable matching algorithm (Gale-Shapley / Deferred Acceptance) to match renters to optimal listings.

The **AI component** is responsible for predicting how compatible a given renter–listing pair is. It does this using a **Two-Tower Neural Network** that learns separate embeddings for users and listings, then compares them via a dot product to produce a compatibility score.

### Why AI?

Simple rule-based filters (e.g., "show me apartments under $1500 with 2 beds") only capture explicit preferences. An AI model can learn **implicit preferences** from behavior — for example, a user who keeps swiping right on furnished downtown lofts probably prefers that style, even if they never explicitly said so. The two-tower architecture is the industry standard for this kind of large-scale recommendation (used by YouTube, Airbnb, and similar platforms).

---

## 2) What the Assignment Required

The overall task was to build a working AI recommendation pipeline for Padly. This broke down into several concrete deliverables:

### A) Listing Categorization

Classify every listing in the dataset into one of **6 meaningful categories** based on its attributes. This gives the model a higher-level "taste cluster" signal beyond raw numeric features.

### B) User-to-Listing Mapping

For each synthetic renter, simulate which listings they would **like** (swipe right on). This requires:
- Respecting **hard constraints** (budget, pet policy, smoking, wheelchair access)
- Using **category affinity** to make likes realistic (e.g., a low-budget user mostly likes Budget Compact listings)
- Producing exactly **15 liked listings** per user

### C) Feedback Array Generation

For each user, produce a **feedback array** — a vector of 6 integers `[c0, c1, c2, c3, c4, c5]` where `c_i` = how many of their 15 liked listings fall into category `i`. This captures user taste distribution.

### D) Model Integration

Wire the feedback arrays and listing categories into the two-tower model's training pipeline so the network can actually learn from this signal:
- **User tower** receives the feedback distribution as additional input features
- **Item tower** receives the listing's category as a one-hot encoded feature

### E) Training & Evaluation

Train the model with and without the new features and compare accuracy to verify the signal is useful.

---

## 3) The Dataset

### Source

`housing_train.csv` — a Craigslist housing listings dataset.

### Raw Statistics

| Metric | Value |
|--------|-------|
| Total raw rows | 265,190 |
| Rows after cleaning | 261,589 |
| Cleaning rules | price ∈ (50, 15000), sqfeet ∈ (50, 15000), beds ∈ [0, 10], lat/long not null |

### Feature Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Unique listing identifier |
| `price` | float | Monthly rent in USD |
| `sqfeet` | float | Square footage |
| `beds` | int | Number of bedrooms |
| `baths` | float | Number of bathrooms |
| `type` | str | Listing type (apartment, house, condo, townhouse, etc.) – 12 unique values |
| `cats_allowed` | 0/1 | Whether cats are permitted |
| `dogs_allowed` | 0/1 | Whether dogs are permitted |
| `smoking_allowed` | 0/1 | Whether smoking is permitted |
| `wheelchair_access` | 0/1 | Whether unit is wheelchair accessible |
| `electric_vehicle_charge` | 0/1 | Whether EV charging is available |
| `comes_furnished` | 0/1 | Whether unit is furnished |
| `laundry_options` | str | Laundry type (w/d in unit, w/d hookups, laundry in bldg, etc.) – 6 values |
| `parking_options` | str | Parking type (attached garage, off-street parking, etc.) – 8 values |
| `lat` / `long` | float | Latitude and longitude coordinates |
| `state` | str | US state abbreviation |
| `region` / `region_url` | str | Craigslist region info |

### Synthetic Renters

Since we don't have real user data, `generate_renter_data.py` creates **30,000 synthetic renter profiles** with correlated demographics:

| Feature | Distribution |
|---------|-------------|
| Age | Uniform 18–70 |
| Household size | Categorical [1,2,3,4,5] with weights [0.30, 0.30, 0.20, 0.12, 0.08] |
| Income | Base = 25K + 800 × min(age,50) + noise, scaled by household size |
| Budget | ~30% of monthly income with ±30% range |
| Desired beds | household_size ± 1 |
| Desired baths | ceil(beds/2) + small noise |
| Desired sqft | Derived from listing sqft distribution + bed scaling |
| Has cats | 25% probability |
| Has dogs | 30% probability |
| Is smoker | 12% probability |
| Needs wheelchair | 4% probability |
| Has EV | 6% (only if income > 60K) |
| Wants furnished | 18% probability |
| Location preference | Sampled from real listing coordinates + jitter |
| Max distance (km) | Uniform 5–80 |
| Type preferences | 1–3 randomly selected from 12 listing types |
| Credit score | Correlated with income |
| Move urgency | [flexible=35%, soon=45%, urgent=20%] |

---

## 4) Two-Tower Neural Network Architecture

### What is a Two-Tower Model?

It's a neural network with **two separate sub-networks** (towers) that process different kinds of input:

```
     USER FEATURES                    LISTING FEATURES
          │                                  │
    ┌─────┴─────┐                     ┌──────┴──────┐
    │ User Tower │                     │ Item Tower  │
    │ Dense(256) │                     │ Dense(256)  │
    │ Dropout(.2)│                     │ Dropout(.2) │
    │ Dense(128) │                     │ Dense(128)  │
    │ Dense(64)  │                     │ Dense(64)   │
    │ L2 Norm    │                     │ L2 Norm     │
    └─────┬─────┘                     └──────┬──────┘
          │                                  │
     64-dim embedding                   64-dim embedding
          │                                  │
          └──────────┐     ┌─────────────────┘
                     │     │
                 ┌───┴─────┴───┐
                 │ Dot Product  │
                 └──────┬──────┘
                        │
                   scalar score
                        │
                ┌───────┴────────┐
                │ Dense(2, logits)│
                └───────┬────────┘
                        │
                [no-match, match]
                   (softmax)
```

### Why Two Towers?

1. **Modularity** — Each tower specializes in understanding its own domain (users vs. listings)
2. **Scalability** — Embeddings can be pre-computed and cached. At serving time, you only need to compute the embedding for new items, then do a fast dot-product lookup against all cached user embeddings
3. **Flexibility** — You can add new user features (like feedback arrays) to the user tower without touching the item tower

### Layer-by-Layer Breakdown

Each tower follows the same architecture:

| Layer | Operation | Output Shape | Purpose |
|-------|-----------|-------------|---------|
| Input | Raw features | (batch, user_dim) or (batch, item_dim) | Accept raw feature vector |
| Dense(256, relu) | Linear + ReLU | (batch, 256) | First hidden layer — learn feature interactions |
| Dropout(0.2) | Random zero-out | (batch, 256) | Regularization — prevents overfitting |
| Dense(128, relu) | Linear + ReLU | (batch, 128) | Second hidden layer — compress representations |
| Dense(64) | Linear (no activation) | (batch, 64) | Project to embedding space |
| L2 Normalize | x / ‖x‖ | (batch, 64) | Normalize so dot product = cosine similarity ∈ [−1, 1] |

### Scoring

After both towers produce their 64-dimensional L2-normalized embeddings:

1. **Dot product** → single scalar per pair (cosine similarity)
2. **Dense(2)** → two logits: `[score_no_match, score_match]`
3. **Softmax** → probabilities that sum to 1

### Loss Function

**Sparse Categorical Cross-Entropy** (from logits). The label is either `0` (no match) or `1` (match), and the loss penalizes the model for assigning high probability to the wrong class.

### Optimizer

**Adam** with learning rate `1e-3` (default). Adam adapts the learning rate per-parameter, which works well for sparse features.

---

## 5) Data Pipeline – End to End

The full pipeline from raw CSV to trained model has 4 stages:

```
Stage 1: Categorize          Stage 2: Map Users          Stage 3: Generate Pairs          Stage 4: Train
─────────────────────        ────────────────────        ─────────────────────────        ─────────────
housing_train.csv            renters_synthetic.csv       renters + listings               train_pairs.npz
        │                            │                           │                             │
   clean listings              load renters                sample 10 listings            load .npz
        │                            │                     per renter                         │
   apply 6 rules               compute affinity                  │                    80/20 train/val
        │                            │                     compute _match_score               │
   listing_categories.csv      filter hard constraints           │                    build_model()
                                     │                     label: score >= 0.65 → 1          │
                               sample 15 likes                   │                    fit(epochs=10)
                                     │                     join feedback + cats               │
                               user_feedback.csv                 │                    save .keras
                                                           encode features
                                                                 │
                                                           save .npz
```

### Detailed Steps

#### Stage 1: Listing Categorization (`categorize_and_map.py`)

1. Load `housing_train.csv` (265K rows)
2. Clean: remove outlier prices, sqft, beds; drop rows with missing lat/long → 261,589 rows
3. Apply priority cascade to assign exactly 1 of 6 categories to each listing
4. Save `listing_categories.csv` (columns: `id`, `category_id`, `category_name`)

#### Stage 2: User Feedback Mapping (`categorize_and_map.py`)

1. Load `renters_synthetic.csv` (30,000 rows)
2. For each renter:
   - Compute 6-element category affinity vector based on demographics
   - Filter all 261K listings down to those passing hard constraints
   - Build sampling weights = affinity[listing_category] + noise
   - Sample 15 listings (without replacement)
   - Count how many fall in each category → feedback array
3. Save `user_feedback.csv` (columns: `renter_id`, `cat_0` … `cat_5`, `dominant_category_id`, etc.)
4. Save `liked_listings_detail.csv` (every individual liked listing with metadata)

#### Stage 3: Pair Generation & Feature Encoding (`generate_renter_data.py`)

1. Load `housing_train.csv`, clean, generate 30K renters → save `renters_synthetic.csv`
2. Optionally load `user_feedback.csv` and `listing_categories.csv`
3. For each renter, sample 10 random listings from the dataset
4. Compute `_match_score()` for each pair (weighted combination of constraint checks + soft preferences)
5. Label `1` if score ≥ 0.65 (positive/match), else `0` (negative/no match)
6. Join feedback columns onto renter pair rows; join category_id onto listing pair rows
7. Encode user features → numeric matrix (user_dim × N)
8. Encode listing features → numeric matrix (item_dim × N)
9. Save `train_pairs.npz` containing: `user_features`, `item_features`, `labels`

#### Stage 4: Training (`two_tower_baseline.py`)

1. Load `train_pairs.npz`
2. 80/20 sequential split (first 80% train, last 20% validation)
3. Build model with detected dimensions
4. Compile with Adam optimizer + SparseCategoricalCrossentropy
5. Train for N epochs (default 10)
6. Save model to `artifacts/two_tower_baseline.keras`

---

## 6) Listing Categorization (6 Categories)

### The Categories

| Index | Name | Rule | Real-World Meaning |
|-------|------|------|--------------------|
| 0 | Budget Compact | price < $900 AND sqfeet < 800 AND beds ≤ 1 | Studios and 1-beds for cost-conscious renters |
| 1 | Spacious Family | beds ≥ 3 AND sqfeet > 1100 | Large homes for families or groups |
| 2 | Pet-Friendly | cats AND dogs both allowed | General listings welcoming pets |
| 3 | Premium / Luxury | price > $1500 AND (furnished OR w/d in unit OR garage) | High-end listings with upscale amenities |
| 4 | Urban Convenience | everything remaining | Moderate apartments, the "default" bucket |
| 5 | Accessible Modern | wheelchair accessible OR EV charging | Listings with accessibility or green features |

### Why Priority Cascade?

Many listings could match multiple rules (e.g., an expensive, wheelchair-accessible, pet-friendly condo). We need each listing in **exactly one** category. The priority cascade ensures deterministic, non-overlapping assignment:

```
Check order (highest priority first):
  5  Accessible Modern    ← checked first (rarest, most important signal)
  3  Premium / Luxury     ← checked second
  1  Spacious Family      ← checked third
  0  Budget Compact       ← checked fourth
  2  Pet-Friendly         ← checked fifth (broad, catches many)
  4  Urban Convenience    ← catch-all (everything left)
```

Once a listing is assigned, it is skipped in later checks. This means a $2000 wheelchair-accessible apartment goes into **Accessible Modern** (category 5), not Premium/Luxury, because Accessible Modern has higher priority.

### Distribution After Categorization

```
Category              Count      Percentage
──────────────────────────────────────────
Budget Compact        29,740     11.4%
Spacious Family       31,844     12.2%
Pet-Friendly          97,648     37.3%
Premium / Luxury      31,567     12.1%
Urban Convenience     48,373     18.5%
Accessible Modern     22,417      8.6%
──────────────────────────────────────────
Total                261,589    100.0%
```

Pet-Friendly is the largest because many listings allow both cats and dogs, and the pet rule is a broad catch-all after higher-priority categories are assigned.

---

## 7) User-to-Listing Mapping & Feedback Arrays

### The Goal

Simulate a user's browsing behavior. In a real app, this data would come from actual swipes. Since we don't have that, we **synthesize** it deterministically based on each user's demographics and preferences.

### Hard Constraint Filtering

Before a user can "like" a listing, the listing must pass ALL of these non-negotiable checks:

| Constraint | Logic | Why |
|-----------|-------|-----|
| Budget | listing.price ≤ renter.budget_max × 1.20 | Allow 20% stretch above stated max |
| Cats | If renter has cats, listing must allow cats | Non-negotiable for pet owners |
| Dogs | If renter has dogs, listing must allow dogs | Non-negotiable for pet owners |
| Smoking | If renter smokes, listing must allow smoking | Non-negotiable for smokers |
| Wheelchair | If renter needs wheelchair, listing must be accessible | Non-negotiable for accessibility |

This filter is implemented with **vectorized pandas operations** for speed (processing 30K renters × 261K listings).

### Category Affinity

Each user gets a 6-element affinity vector based on their preferences:

```python
# Example for a low-budget renter with a cat:
affinity = [0.85,   # Budget Compact (low budget → strong)
            0.05,   # Spacious Family (base)
            0.55,   # Pet-Friendly (has cat)
            0.05,   # Premium/Luxury (base)
            0.45,   # Urban Convenience (moderate budget)
            0.05]   # Accessible Modern (base)
```

This drives the sampling weights so the user's 15 liked listings mostly come from categories they'd realistically prefer.

### Affinity Rules

| Category | Boosted When |
|----------|-------------|
| Budget Compact (0) | budget_max < 900 (+0.8), budget_max < 1100 (+0.3) |
| Spacious Family (1) | desired_beds ≥ 3 (+0.7), household_size ≥ 3 (+0.4), desired_sqft > 1100 (+0.3) |
| Pet-Friendly (2) | has_cats (+0.5), has_dogs (+0.5) |
| Premium/Luxury (3) | budget_max > 1500 (+0.6), wants_furnished (+0.5), income > 80K (+0.3) |
| Urban Convenience (4) | prefers apartment type (+0.6), budget 900–1500 (+0.4) |
| Accessible Modern (5) | needs_wheelchair (+1.0), has_ev (+0.8) |

### Sampling Process

1. Apply hard constraint filter → only eligible listings remain
2. For each eligible listing, weight = `affinity[listing_category] + uniform_noise(0, 0.20)`
3. Sample 15 listings **without replacement** using these weights
4. Count liked listings per category → feedback array

### Example Output

```
renter_id, cat_0, cat_1, cat_2, cat_3, cat_4, cat_5
0,         1,     0,     11,    0,     0,     3
```

Interpretation: Renter 0 liked 1 Budget Compact, 0 Spacious Family, 11 Pet-Friendly, 0 Premium/Luxury, 0 Urban Convenience, and 3 Accessible Modern listings. Their **dominant category** is Pet-Friendly (category 2).

### Full Run Statistics

| Metric | Value |
|--------|-------|
| Total renters processed | 30,000 |
| Likes per renter | 15 |
| Total liked pairs generated | 450,000 |
| Feedback array shape | (30000, 6) |

---

## 8) Integrating Feedback into the Model

### The Problem

The feedback arrays and listing categories existed as CSV files, but were **not fed into the neural network**. The model was ignoring this information.

### The Solution

Two changes were made to `generate_renter_data.py` (the encoding functions):

### User Tower Enhancement

**Before:** 33 input dimensions (demographics + preferences + type prefs)

**After:** 39 input dimensions (+6 normalized feedback features)

The 6 feedback columns (`cat_0` through `cat_5`) are **row-normalized** so each row sums to 1.0. This converts raw counts into a **probability distribution** over categories.

```
Raw feedback:     [1, 0, 11, 0, 0, 3]     (15 total likes)
Normalized:       [0.067, 0, 0.733, 0, 0, 0.2]     (sums to 1.0)
```

This normalization is important because different users might have different total like counts in the future (if some users like more/fewer than 15). The distribution captures **proportional taste**, not absolute counts.

### Item Tower Enhancement

**Before:** 38 input dimensions (numeric features + type/laundry/parking dummies)

**After:** 44 input dimensions (+6 category one-hot)

Each listing gets a **one-hot vector** indicating its category:

```
Category 2 (Pet-Friendly) → [0, 0, 1, 0, 0, 0]
Category 5 (Accessible)   → [0, 0, 0, 0, 0, 1]
```

### Why This Helps

The dot product between the user's feedback distribution and the listing's category one-hot effectively computes: **"How much does this user tend to like listings in this category?"**

If a user's normalized feedback is `[0.067, 0, 0.733, 0, 0, 0.2]` and a listing is category 2, the contribution from these features alone is `0.733 × 1.0 = 0.733` — a strong positive signal.

### Backward Compatibility

Both changes check whether the relevant columns exist in the DataFrame:

```python
# In encode_renter_features():
has_feedback = all(c in renters.columns for c in FEEDBACK_COLS)
if has_feedback:
    # append normalized feedback

# In encode_listing_features():
if "category_id" in listings.columns:
    # append one-hot category
```

Without the `--feedback-csv` and `--listing-cats-csv` CLI flags, the script produces the same output as before.

---

## 9) Training & Results

### Training Configuration

| Parameter | Value |
|-----------|-------|
| Optimizer | Adam |
| Learning rate | 1e-3 |
| Loss function | SparseCategoricalCrossentropy (from logits) |
| Embedding dimension | 64 |
| Dropout rate | 0.2 |
| Batch size | 256 |
| Epochs | 10 |
| Train/Val split | 80/20 (sequential, no shuffle) |
| Random seed | 42 |

### Dataset Statistics

| Metric | Value |
|--------|-------|
| Total pairs | 300,000 (30K renters × 10 listings each) |
| Positive pairs (label=1) | ~119,000 (39.7%) |
| Negative pairs (label=0) | ~181,000 (60.3%) |
| Training samples | 240,000 |
| Validation samples | 60,000 |

### Comparison: Baseline vs. With Feedback

Two models were trained identically except for the presence of feedback/category features:

| Model | user_dim | item_dim | val_accuracy (epoch 10) | val_loss |
|-------|----------|----------|------------------------|----------|
| Baseline (no feedback) | 33 | 38 | 91.87% | 0.1964 |
| + feedback + category | 39 | 44 | **92.01%** | **0.1915** |

**Improvement:** +0.14% accuracy, −0.005 loss

### Why the Improvement is Small

The improvement is modest because:

1. **Feedback is derived from the same synthetic preferences** — The feedback array is computed from the same demographic rules that also drive the match labels. The model already has access to most of this signal through the raw demographic features.

2. **Only 10 epochs** — The feedback features might need more training time to be fully exploited.

3. **No hard negative mining** — The training pairs are randomly sampled, so many "negative" pairs are obviously bad matches that the model can already classify easily. Hard negatives (near-miss pairs) would force the model to use every available signal.

With **real swipe data** (where feedback captures behavioral patterns not present in demographics), this gap is expected to widen significantly.

---

## 10) File Inventory

### Scripts (What They Do)

| File | Lines | Purpose |
|------|-------|---------|
| `categorize_and_map.py` | 469 | Categorize listings into 6 categories, map renters to liked listings, generate feedback arrays |
| `generate_renter_data.py` | 546 | Generate synthetic renters, build training pairs, encode features into .npz for model training |
| `two_tower_baseline.py` | 132 | Define and train the two-tower neural network model |

### Data Files (Generated)

| File | Contents |
|------|----------|
| `dataset/housing_train.csv` | Raw Craigslist listings dataset (input) |
| `dataset/renters_synthetic.csv` | 30,000 synthetic renter profiles |
| `dataset/listing_categories.csv` | Mapping of listing id → category_id + category_name |
| `dataset/user_feedback.csv` | Per-user feedback array [cat_0 … cat_5] + dominant category |
| `dataset/liked_listings_detail.csv` | Detailed log of every liked listing per user (450K rows) |
| `dataset/train_pairs.npz` | Compressed numpy archive with user_features, item_features, labels |

### Model Artifacts

| File | Contents |
|------|----------|
| `artifacts/two_tower_baseline.keras` | Trained Keras model (saveable/loadable) |

### Documentation

| File | Contents |
|------|----------|
| `CURRENT_WORK.md` | Detailed technical log of all changes made (history embedding + feedback integration) |
| `PROJECT_DOCUMENTATION.md` | This file — comprehensive project overview |

### Root-Level Documentation

| File | Contents |
|------|----------|
| `TWO_TOWER_EXPLAINER.md` | Detailed Two-Tower architecture explanation with worked numerical examples |
| `ML_ROADMAP.md` | Full ML integration roadmap (DB schemas, API endpoints, phases) |
| `ML_addition.md` | Quick implementation guide with architecture diagram |

---

## 11) How to Run Everything

### Prerequisites

```bash
pip install tensorflow pandas numpy
```

Tested with: Python 3.13, TensorFlow 2.20.0

### Step-by-Step (from `backend/` directory)

#### Step 1: Generate Synthetic Renters + Base Training Pairs

```bash
python -m app.ai.generate_renter_data \
  --renters 30000 \
  --pairs-per-renter 10 \
  --out-renters-csv app/ai/dataset/renters_synthetic.csv \
  --out-npz app/ai/dataset/train_pairs.npz
```

This creates `renters_synthetic.csv` (30K renters) and a baseline `train_pairs.npz`.

#### Step 2: Categorize Listings & Generate Feedback Arrays

```bash
python -m app.ai.categorize_and_map \
  --listings-csv app/ai/dataset/housing_train.csv \
  --renters-csv app/ai/dataset/renters_synthetic.csv \
  --likes 15 \
  --noise 0.20 \
  --seed 42
```

This creates:
- `listing_categories.csv` (261K listings with category assignments)
- `user_feedback.csv` (30K users with feedback arrays)
- `liked_listings_detail.csv` (450K individual liked pairs)

#### Step 3: Re-generate Training Pairs WITH Feedback

```bash
python -m app.ai.generate_renter_data \
  --renters 30000 \
  --pairs-per-renter 10 \
  --feedback-csv app/ai/dataset/user_feedback.csv \
  --listing-cats-csv app/ai/dataset/listing_categories.csv \
  --out-npz app/ai/dataset/train_pairs.npz
```

This appends feedback columns to the user features and category one-hot to the item features.

#### Step 4: Train the Model

```bash
python -m app.ai.two_tower_baseline \
  --npz-path app/ai/dataset/train_pairs.npz \
  --epochs 10 \
  --output-model app/ai/artifacts/two_tower_baseline.keras
```

### Quick Smoke Test

If you want to verify everything works with a small run:

```bash
# Small data generation
python -m app.ai.generate_renter_data --renters 200 --pairs-per-renter 5 \
  --out-npz app/ai/dataset/train_pairs_dev.npz

# Categorize + map (uses same renters)
python -m app.ai.categorize_and_map --likes 15

# Train 1 epoch
python -m app.ai.two_tower_baseline --npz-path app/ai/dataset/train_pairs_dev.npz --epochs 1
```

---

## 12) Current Limitations

### Synthetic Data

All training data is synthetic. Renter profiles are generated from statistical distributions, and "likes" are simulated from rule-based affinity. This means:
- The model is learning synthetic patterns, not real human behavior
- Feedback signal is circular (derived from the same demographics that drive labels)
- Real users may have preferences not captured by our rules

### Sequential Train/Val Split

The 80/20 split is sequential (first 80% of rows = train, last 20% = validation). Since renters are generated in order, this means the validation set contains renter IDs 24000–29999, which may have slightly different demographic distributions than the training set. A **shuffled split** would be more rigorous.

### No Hard Negative Mining

Training pairs are randomly sampled. Most negative pairs are "obviously" bad matches (e.g., a $500-budget user paired with a $3000 listing). The model easily classifies these, learning less from each example. Hard negatives (near-miss pairs where the score is close to the threshold) would provide more useful gradient signal.

### Limited Epochs

Only 10 epochs were trained. More epochs with early stopping could squeeze out additional accuracy.

### No Learning Rate Scheduling

A fixed learning rate of 1e-3 is used throughout. Cosine annealing or step-decay would allow the model to fine-tune in later epochs.

---

## 13) Future Improvements

Ranked by expected impact:

| # | Improvement | Difficulty | Expected Impact |
|---|------------|------------|-----------------|
| 1 | **Shuffle before split** | Trivial | Fix distribution skew in val set |
| 2 | **Early stopping** (patience=5, restore best) | Easy | Prevent overfitting, find optimal epoch |
| 3 | **Learning rate schedule** (cosine or reduce-on-plateau) | Easy | Better convergence in later epochs |
| 4 | **Deeper towers** (add BatchNorm + 3rd hidden layer) | Medium | Learn more complex feature interactions |
| 5 | **Hard negative mining** (sample near-threshold negatives) | Medium | Force model to learn subtle distinctions |
| 6 | **More training epochs** (50+ with early stopping) | Easy | Use more of the training budget |
| 7 | **Real swipe data integration** | Hard | True behavioral signal instead of synthetic |
| 8 | **Text embeddings** (sentence-transformers for listing descriptions) | Hard | Capture semantic info not in tabular features |

### Architecture Improvements

```
Current:  Dense(256) → Dropout → Dense(128) → Dense(64) → L2Norm

Proposed: Dense(256) → BatchNorm → ReLU → Dropout(0.3)
          Dense(128) → BatchNorm → ReLU → Dropout(0.2)
          Dense(64)  → L2Norm
```

BatchNorm stabilizes training and often allows higher learning rates.

### Expected Accuracy Targets

| Configuration | Estimated Accuracy |
|--------------|-------------------|
| Current (10 epochs, no tricks) | 92.01% |
| + Shuffle + early stopping + LR schedule | ~93–94% |
| + Deeper towers + hard negatives | ~94–95% |
| + Real swipe data | Unknown (but fundamentally better signal) |

---

## Summary

This project implemented a complete AI recommendation pipeline for the Padly rental platform:

1. **Listing categorization** — 261K listings classified into 6 rule-based categories using a priority cascade
2. **User mapping** — 30K synthetic renters each mapped to 15 liked listings via affinity-weighted sampling with hard constraint enforcement
3. **Feedback arrays** — Per-user taste distributions capturing how many liked listings fall into each category
4. **Model integration** — Feedback features added to user tower (+6 dims), category one-hot added to item tower (+6 dims)
5. **Training** — Two-tower model trained with softmax loss, achieving 92.01% validation accuracy

The system is fully functional as a pre-production baseline. The next major leap would come from replacing synthetic feedback with real user swipe data, which would give the model access to behavioral patterns that cannot be captured by rule-based simulation.
