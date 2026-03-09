# Two-Tower History Embedding Implementation (Beginner-Friendly)

This document explains, in plain language, what was implemented to simulate swipe-style feedback and how it affects training.

Date: 2026-02-24 (updated 2026-03-03)  
Branch: `feature/history-embedding-two-tower`  
Safety tag: `backup/pre-history-implementation-2026-02-24`

---

## 0) New – Listing Categorization & User Feedback Array (2026-03-03)

### What was added

New standalone script: `backend/app/ai/categorize_and_map.py`

This script:
1. **Categorizes every listing** into exactly one of 6 rule-based categories
2. **Maps each renter to 15 "liked" listings** that pass their hard constraints
3. **Produces a feedback array** per user: `[c0, c1, c2, c3, c4, c5]` where `c_i` = number of liked listings in category `i`

### The 6 categories

| Index | Name              | Rule (priority cascade)                                                |
|-------|-------------------|------------------------------------------------------------------------|
| 0     | Budget Compact    | price < $900, sqfeet < 800, beds ≤ 1                                   |
| 1     | Spacious Family   | beds ≥ 3, sqfeet > 1100                                               |
| 2     | Pet-Friendly      | cats + dogs allowed (catch-all after higher-priority categories)        |
| 3     | Premium / Luxury  | price > $1500 AND (furnished OR w/d in unit OR garage parking)         |
| 4     | Urban Convenience | everything remaining (mostly moderate-price apartments)                 |
| 5     | Accessible Modern | wheelchair accessible OR EV charging                                   |

Categories are assigned via priority cascade (5 → 3 → 1 → 0 → 2 → 4) so each listing gets exactly one.

Listing distribution after categorization (261K cleaned listings):
- Budget Compact: 29,740 (11.4%)
- Spacious Family: 31,844 (12.2%)
- Pet-Friendly: 97,648 (37.3%)
- Premium / Luxury: 31,567 (12.1%)
- Urban Convenience: 48,373 (18.5%)
- Accessible Modern: 22,417 (8.6%)

### How user → category mapping works

1. Compute a **category affinity** vector for each renter based on their preferences:
   - Low budget → Budget Compact
   - Large household / many beds → Spacious Family
   - Has pets → Pet-Friendly
   - High income / wants furnished → Premium / Luxury
   - Prefers apartments / moderate budget → Urban Convenience
   - Needs wheelchair / has EV → Accessible Modern
2. Filter listings to only those passing **hard constraints** (budget ceiling, pet policy, smoking, wheelchair)
3. Sample 15 listings weighted by category affinity + small noise
4. Count how many of the 15 fall in each category → feedback array

### Example output

A user feedback array row:
```
renter_id, cat_0, cat_1, cat_2, cat_3, cat_4, cat_5
0,         1,     0,     11,    0,     0,     3
```
This means renter 0 liked 1 Budget Compact, 0 Spacious Family, 11 Pet-Friendly, 0 Premium/Luxury, 0 Urban Convenience, and 3 Accessible Modern listings.

### How to run

```bash
# From backend/
python -m app.ai.categorize_and_map                        # defaults (uses existing renters_synthetic.csv)
python -m app.ai.categorize_and_map --likes 20 --noise 0.3 # custom
```

### Output files

- `app/ai/dataset/listing_categories.csv` – listing id → category mapping
- `app/ai/dataset/user_feedback.csv` – per-user feedback array + dominant category
- `app/ai/dataset/liked_listings_detail.csv` – detailed log of every liked listing per user

### Integration into training pipeline (2026-03-03)

The feedback array and listing categories are now wired into `generate_renter_data.py`:

**User tower** gets 6 extra features (normalized feedback distribution):
- `cat_0` … `cat_5` → each row sums to 1.0, so [1,0,11,0,0,3] becomes [0.067, 0, 0.733, 0, 0, 0.2]
- Feature dimensions: 33 → 39

**Item tower** gets 6 extra features (one-hot listing category):
- If a listing is category 2 (Pet-Friendly) → `[0, 0, 1, 0, 0, 0]`
- Feature dimensions: 38 → 44

**How to regenerate with feedback:**
```bash
# From backend/
python -m app.ai.generate_renter_data \
  --feedback-csv app/ai/dataset/user_feedback.csv \
  --listing-cats-csv app/ai/dataset/listing_categories.csv
```

Without the `--feedback-csv` and `--listing-cats-csv` flags, the script behaves exactly as before (backward-compatible).

**Training comparison (10 epochs, same seed/data):**

| Model                | user_dim | item_dim | val_acc (epoch 10) | val_loss |
|----------------------|----------|----------|--------------------|----------|
| Baseline (no feedback) | 33     | 38       | 91.87%             | 0.1964   |
| + feedback + category  | 39     | 44       | **92.01%**         | **0.1915** |

Small improvement (+0.14% accuracy, −0.005 loss). This is expected since the feedback is derived from the same synthetic preferences — the lift signals the model can exploit the category taste signal. With real swipe data this gap should widen.

---

## 1) Problem we were solving

Before this change, the model learned from synthetic pair labels only (rule-based compatibility), but it did not explicitly ingest a "recent likes" signal.

Goal of this update:

- Simulate a user's last 15 "right swipes"
- Convert that into model input features
- Keep labels as pair-level `0/1` so training still matches binary like/pass setup

---

## 2) File changed

All code updates were made in:

- `backend/app/ai/generate_renter_data.py`

No model architecture code was changed in `two_tower_baseline.py`; the model automatically adapts to new input dimensions from the generated dataset.

---

## 3) High-level pipeline (after this change)

1. Load and clean listings
2. Assign each listing a synthetic category (`synthetic_category` + readable name)
3. Generate renters
4. Give each renter 1-2 preferred categories (`pref_cat_*`)
5. Simulate each renter's recent 15 likes (`history_cat_*`)
6. Build renter-listing pairs
7. Compute blended score (compatibility + category affinity)
8. Convert score to label (`1` if score >= threshold else `0`)
9. Encode features and save `.npz` for training

---

## 4) What was added and why

### A) Listing categories (with readable labels)

Functions added:

- `_build_category_catalog(num_categories)`
- `_assign_listing_categories(listings, num_categories, category_catalog)`

Each listing now gets:

- `synthetic_category` (id in `[0, num_categories-1]`)
- `synthetic_category_name` (human-friendly label)

Default category names:

- `Budget Saver`
- `Space Seeker`
- `Urban Convenience`
- `Amenities First`
- `Family Ready`
- `Premium Comfort`

Category assignment still uses listing attributes (price, sqft, beds, furnished, type), so it is deterministic and repeatable (not pure random).

Why:

- Gives a simple latent "taste cluster" signal
- Lets us model users preferring certain listing styles

### B) User preferred categories

In renter generation, each user is assigned preference for 1 or 2 categories:

- Stored as `pref_cat_0 ... pref_cat_{k-1}`
- Values are binary (`1` preferred, `0` not preferred)

Why:

- Simulates users having one main taste and sometimes a secondary taste

### C) Simulated recent likes history (15)

In renter generation:

- Simulate `history_likes` interactions (default 15)
- Likes sampled mostly from preferred categories
- Controlled noise via `history_noise` (default 0.25)
- Stored as normalized distribution `history_cat_*`

Why:

- Mimics "what user recently liked"
- Adds memory-like context to user features

### D) Label generation includes category affinity

In pair creation:

- Base score from existing `_match_score(...)`
- Category affinity score from `pref_cat_*` and `history_cat_*`
- Blend both and threshold to produce final label

Current blend inside generator:

- `final_score = 0.75 * base_compatibility + 0.25 * category_affinity`
- `label = 1 if final_score >= pos_threshold else 0`

Why:

- Keeps the existing compatibility logic
- Injects a feedback-like signal so labels reflect user taste pattern better

Also added pair-level debug metadata so each generated pair can be inspected later:

- `listing_category_name`
- `base_score`
- `category_affinity`
- `blended_score`
- `label`

### E) Expanded encoded features

User encoded matrix now includes:

- existing numeric/user preference fields
- `type_pref_*`
- `pref_cat_*`
- `history_cat_*`

Item encoded matrix now includes:

- existing numeric listing fields
- one-hots for `type`, `laundry_options`, `parking_options`
- one-hot for category (`cat_*`)

Why:

- Both towers now receive aligned category/history features

### F) Recommendation simulation preview output

Function added: `_build_recommendation_preview(...)`

This creates an easy-to-read simulation table per user showing:

- user preferred category names
- top-k recommended listings by blended score
- each listing category name
- pair label (`0/1`)
- whether recommendation category is in the user's preferred categories (`is_preferred_category`)

Why:

- Lets us quickly verify if recommendations align with mapped user preferences
- Gives frontend-ready data for visualization/testing

---

## 5) Concrete worked example

Assume `num_categories = 6` (cat0..cat5).

### Example user

User prefers categories 2 and 4:

- `pref_cat = [0, 0, 1, 0, 1, 0]`

Simulated last 15 likes happened mostly in cat2 and cat4:

- counts = `[1, 0, 8, 1, 5, 0]`
- normalized history:
  `history_cat = [0.067, 0.000, 0.533, 0.067, 0.333, 0.000]`

### Example listing

Listing belongs to category 2.

Then:

- `cat_pref = pref_cat[2] = 1`
- `cat_history = history_cat[2] = 0.533`
- `category_affinity = 0.7*1 + 0.3*min(1, 0.533*3)`
- `category_affinity = 0.7 + 0.3*1 = 1.0`

If base compatibility score is `0.58`, then:

- `final_score = 0.75*0.58 + 0.25*1.0 = 0.685`

With threshold `0.65`, label is:

- `label = 1`

This is how history/preferences can flip a borderline sample into a positive label.

---

## 6) New CLI parameters

Added to `generate_renter_data.py`:

- `--num-categories` (default `6`)
- `--history-likes` (default `15`)
- `--history-noise` (default `0.25`, clamped to `[0.0, 0.8]`)
- `--top-k` (default `5`)
- `--preview-users` (default `10`)
- `--out-category-csv` (default `app/ai/dataset/category_catalog.csv`)
- `--out-pairs-csv` (default `app/ai/dataset/pairs_with_labels.csv`)
- `--out-preview-csv` (default `app/ai/dataset/recommendation_preview.csv`)

Practical tuning guidance:

- Lower `history-noise` -> stronger category consistency per user
- Higher `history-noise` -> more diverse/noisy likes
- Increase `num-categories` -> more granular taste clusters

---

## 7) Validation that was run

Small sanity run completed successfully:

1. Generated dataset with 200 renters, 5 pairs each
2. Trained two-tower for 1 epoch

Observed generated feature shapes:

- `user_features`: `(1000, 45)`
- `item_features`: `(1000, 41)`

Training completed and produced a valid model artifact in the test run.

Temporary dev files were then deleted to keep the branch clean.

Additional simulation validation with named categories + preview export:

- Run with `--renters 120 --pairs-per-renter 8 --top-k 3 --preview-users 5`
- Generated outputs:
  - `app/ai/dataset/category_catalog_demo.csv`
  - `app/ai/dataset/pairs_with_labels_demo.csv`
  - `app/ai/dataset/recommendation_preview_demo.csv`
- Observed preview alignment metric from this run:
  - `53.33%` of shown recommendations were in user preferred categories

---

## 8) How to run (full)

From `backend/`:

```bash
# 1) Generate synthetic training data with history simulation
python -m app.ai.generate_renter_data \
  --renters 30000 \
  --pairs-per-renter 10 \
  --num-categories 6 \
  --history-likes 15 \
  --history-noise 0.25 \
  --top-k 5 \
  --preview-users 10 \
  --out-category-csv app/ai/dataset/category_catalog.csv \
  --out-pairs-csv app/ai/dataset/pairs_with_labels.csv \
  --out-preview-csv app/ai/dataset/recommendation_preview.csv \
  --out-renters-csv app/ai/dataset/renters_synthetic.csv \
  --out-npz app/ai/dataset/train_pairs.npz

# 2) Train two-tower model
python -m app.ai.two_tower_baseline \
  --npz-path app/ai/dataset/train_pairs.npz \
  --epochs 50 \
  --output-model app/ai/artifacts/two_tower_baseline.keras
```

Optional quick smoke test:

```bash
python -m app.ai.generate_renter_data \
  --renters 200 \
  --pairs-per-renter 5 \
  --top-k 3 \
  --preview-users 5 \
  --out-npz app/ai/dataset/train_pairs_dev.npz \
  --out-category-csv app/ai/dataset/category_catalog_dev.csv \
  --out-pairs-csv app/ai/dataset/pairs_with_labels_dev.csv \
  --out-preview-csv app/ai/dataset/recommendation_preview_dev.csv
python -m app.ai.two_tower_baseline --npz-path app/ai/dataset/train_pairs_dev.npz --epochs 1
```

Example of what the preview file looks like:

```text
renter_id,preferred_categories_text,rank,listing_id,listing_category_name,label,base_score,category_affinity,blended_score,is_preferred_category
0,Urban Convenience,1,7043599065,Urban Convenience,1,0.6996,1.0000,0.7747,True
0,Urban Convenience,2,7043368278,Urban Convenience,1,0.6259,1.0000,0.7194,True
0,Urban Convenience,3,7035818559,Family Ready,0,0.7277,0.0000,0.5458,False
```

This row format is the main artifact for checking: "Are recommended categories matching the user's mapped preferences?"

---

## 9) Important limitations (honest view)

- This still uses simulated feedback, not real swipe logs.
- Labels are still synthetic (`0/1` from generated score), not true user actions.
- This is a better pre-production baseline, not final personalization.

---

## 10) Recommended next step to go real

Implement interaction-driven training:

1. Collect real swipe events (`right=1`, `left=0`)
2. Build `(user, listing, label)` from those interactions
3. Build `history_cat_*` from each user's actual recent likes
4. Retrain and compare against this synthetic baseline

This will convert the system from "rule + simulated taste" to real behavioral learning.