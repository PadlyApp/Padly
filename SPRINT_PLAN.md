# Sprint Plan — ML Integration (2 Weeks, 4 Members)

**Branch:** `neural_net`
**Sprint Dates:** Feb 10 – Feb 24, 2026
**Last Updated:** 2026-02-10

---

## Team Roles

| Member | Role | Focus Area |
|---|---|---|
| **Member 1** | Backend & Data Infrastructure | Database migrations, API routes, data pipeline |
| **Member 2** | ML Engineer | Two-Tower model, Siamese network, training pipeline |
| **Member 3** | Frontend Developer | Discover/swipe UI, preferences page updates |
| **Member 4** | Integration & Scoring | Scoring improvements, hybrid scorer, testing, documentation |

---

## Week 1 (Feb 10–16): Foundation

All 4 members work in parallel. No cross-dependencies until end of Week 1.

---

### 👤 Member 1 — Backend & Data Infrastructure

**Goal:** All new database tables exist, all new API endpoints work, data can flow.

#### Day 1–2: Database Migrations

- [ ] Write migration `004_user_interactions.sql`
  - `user_interactions` table with columns: `id`, `user_id`, `listing_id`, `action`, `position_in_feed`, `time_spent_seconds`, `session_id`, `created_at`
  - All indexes (user_id, listing_id, action, composite)
  - Foreign keys to `users` and `listings`
- [ ] Write migration `005_embedding_tables.sql`
  - `user_embeddings` table (user_id, embedding_vector, model_version, computed_at)
  - `listing_embeddings` table (listing_id, text_embedding, image_embedding, combined_embedding, model_version, computed_at)
- [ ] Write migration `006_scoring_improvements.sql`
  - Add `target_latitude`, `target_longitude` to `personal_preferences`
  - Add `photo_count` cache to `listings`
  - Add `host_verified` cache to `listings`
  - Create trigger to keep `photo_count` in sync with `listing_photos`
- [ ] Write migration `007_listing_categories.sql`
  - Add `category` column to `listings` (enum: budget, premium, campus, spacious, social)
  - Add `onboarding_completed` boolean to `users` (default false)
  - Index on `listings(category)`
- [ ] Apply all migrations to Supabase

#### Day 3–4: Interaction API

- [ ] Create `backend/app/routes/interactions.py`
- [ ] `POST /api/interactions` — log a swipe (like/pass/save/view)
  - Validate `listing_id` exists and is active
  - Validate `action` is one of: like, pass, save, view, click
  - Auto-fill `user_id` from JWT auth token
  - Return created interaction
- [ ] `GET /api/interactions/{user_id}/history` — get swipe history
  - Paginated (limit/offset)
  - Filter by action type
  - Sorted by `created_at DESC`
- [ ] `GET /api/interactions/{user_id}/stats` — get interaction stats
  - Total likes, passes, saves
  - Like/pass ratio
  - Most active day/time
- [ ] `DELETE /api/interactions/{interaction_id}` — undo a swipe
- [ ] Add Pydantic models to `models.py`: `InteractionCreate`, `InteractionResponse`, `InteractionStats`
- [ ] Register router in `main.py`

#### Day 5: Discovery Feed & Onboarding Endpoints

- [ ] `GET /api/discover/{user_id}` — get ranked listing feed
  - Parameters: `city` (required), `limit` (default 20), `offset`
  - Filter out already-swiped listings
  - Apply hard constraint filters (reuse `feasible_pairs.py`)
  - Sort by heuristic score for now (AI scoring comes in Week 2)
  - Return listing data with photos
- [ ] `GET /api/discover/{user_id}/onboarding` — get 5 categorized listings for onboarding
  - Returns 1 listing per category (budget, premium, campus, spacious, social)
  - Picks the highest-quality representative from each category in the user's target city
  - Only served if `user.onboarding_completed = false`
- [ ] `POST /api/discover/{user_id}/onboarding/complete` — mark onboarding as done
  - Sets `onboarding_completed = true` after all 5 swipes

**Files to create/modify:**
```
CREATE  backend/migrations/004_user_interactions.sql
CREATE  backend/migrations/005_embedding_tables.sql
CREATE  backend/migrations/006_scoring_improvements.sql
CREATE  backend/migrations/007_listing_categories.sql
CREATE  backend/app/routes/interactions.py
MODIFY  backend/app/models.py                          (add interaction models)
MODIFY  backend/app/main.py                            (register router)
```

---

### 👤 Member 2 — ML Engineer

**Goal:** Two-Tower model defined, feature engineering complete, training pipeline ready.

#### Day 1–2: Project Setup & Embeddings

- [ ] Create `backend/app/ai/` directory with `__init__.py`
- [ ] Create `backend/app/ai/config.py` — all hyperparameters and constants
  ```python
  USER_DIM = 476          # Total user feature dimensions
  ITEM_DIM = 927          # Total listing feature dimensions
  EMBEDDING_DIM = 64      # Output embedding size
  HIDDEN_DIM_1 = 256      # First hidden layer
  HIDDEN_DIM_2 = 128      # Second hidden layer
  LEARNING_RATE = 1e-3
  BATCH_SIZE = 64
  EPOCHS = 20
  DROPOUT_1 = 0.2
  DROPOUT_2 = 0.1
  NEGATIVE_SAMPLE_RATIO = 3
  ```
- [ ] Create `backend/app/ai/embeddings.py`
  - `TextEmbedder` class using `sentence-transformers/all-MiniLM-L6-v2`
    - `embed(text) → 384-dim numpy array`
    - `embed_listing(listing_dict) → 384-dim array` (combines title + description + house_rules)
    - `embed_bio(bio_text) → 384-dim array`
  - `ImageEmbedder` class using `openai/clip-vit-base-patch32`
    - `embed(image) → 512-dim numpy array`
    - `embed_listing_photos(photo_urls) → 512-dim array` (average of all photos)
- [ ] Update `requirements.txt` with ML dependencies
  - `torch>=2.2.0`, `sentence-transformers>=2.5.0`, `transformers>=4.38.0`, `numpy>=1.26.0`, `scikit-learn>=1.4.0`

#### Day 3–4: Feature Engineering & Model

- [ ] Create `backend/app/ai/feature_engineering.py`
  - `build_user_features(user, preferences, swipe_history) → torch.Tensor` (476-dim)
    - Handle all encoding: normalization, one-hot, cyclical, embedding concat
    - Handle missing values (default/neutral values)
  - `build_listing_features(listing, text_embedding, image_embedding) → torch.Tensor` (927-dim)
    - Handle all encoding: normalization, binary, one-hot, multi-hot, embedding concat
    - Handle missing values
  - `normalize(value, min_val, max_val) → float`
  - `cyclical_encode(month) → (sin, cos)`
  - `one_hot(value, categories) → list`
- [ ] Create `backend/app/ai/model.py`
  - `TwoTowerModel(nn.Module)` — as specified in the roadmap
    - `__init__(user_dim, item_dim, embedding_dim=64)`
    - `forward(user_features, item_features) → sigmoid score`
    - `get_user_embedding(user_features) → 64-dim tensor`
    - `get_item_embedding(item_features) → 64-dim tensor`
  - Unit test: verify input/output dimensions match

#### Day 5: Training Pipeline

- [ ] Create `backend/app/ai/training.py`
  - `InteractionDataset(Dataset)` — PyTorch dataset that loads from `user_interactions`
    - Returns (user_features, item_features, label) tuples
    - Implements negative sampling (3 negatives per positive)
  - `train_model(dataset, epochs, lr, batch_size) → trained model`
    - Train/val split (80/20 stratified by user)
    - Binary cross-entropy loss
    - AdamW optimizer with weight decay
    - Early stopping (patience=3 on validation loss)
    - Log metrics per epoch (loss, AUC, accuracy)
    - Save best model checkpoint to `backend/app/ai/checkpoints/`
  - `evaluate_model(model, val_dataset) → dict of metrics`
- [ ] Create `backend/app/ai/siamese.py`
  - `SiameseNetwork(nn.Module)` — shared-weight architecture
    - `__init__(user_dim, embedding_dim=64)`
    - `forward(user_a_features, user_b_features) → compatibility score`
  - Training data extraction from `group_members`

**Files to create:**
```
CREATE  backend/app/ai/__init__.py
CREATE  backend/app/ai/config.py
CREATE  backend/app/ai/embeddings.py
CREATE  backend/app/ai/feature_engineering.py
CREATE  backend/app/ai/model.py
CREATE  backend/app/ai/training.py
CREATE  backend/app/ai/siamese.py
MODIFY  requirements.txt                               (add ML deps)
```

---

### 👤 Member 3 — Frontend Developer

**Goal:** Users can browse and swipe on listings. Map picker on preferences page works.

#### Day 1–3: Discover Page & Swipe UI

- [ ] Create `frontend/src/app/discover/page.jsx` — main discover page
  - **Check `onboarding_completed`** — if false, show onboarding flow first
  - Calls `GET /api/discover/{user_id}?city=...` to get ranked listings
  - Displays listings as swipeable cards (one at a time, full-width)
  - Shows loading state, empty state ("No listings in your city")
  - Quick filter bar at top: city selector, budget range
- [ ] Create `frontend/src/components/OnboardingSwipe.jsx` — 5-card onboarding flow
  - Header: "Help us learn what you're looking for!"
  - Progress dots: ● ○ ○ ○ ○ (fills as user swipes)
  - Shows category label on each card (🏷️ BUDGET-FRIENDLY, 🏷️ PREMIUM, etc.)
  - Simplified buttons: "Not My Style" (✕) and "I Like This" (❤️)
  - After 5th swipe → calls `POST /api/discover/{user_id}/onboarding/complete`
  - Transition animation: "Great! Your feed is ready" → redirect to main discover feed
- [ ] Create `frontend/src/components/ListingCard.jsx`
  - Large photo carousel (swipe through listing photos)
  - Title, price, bedrooms, bathrooms, area
  - Furnished/utilities/deposit badges
  - Amenities chips (gym, AC, laundry, etc.)
  - Distance from target (if lat/lng available)
  - Expandable description section
  - Smooth card entry/exit animations
- [ ] Create `frontend/src/components/SwipeControls.jsx`
  - Pass button (✕) — red, left side
  - Save button (⭐) — yellow, center
  - Like button (❤️) — green, right side
  - Each button calls `POST /api/interactions` with the appropriate action
  - Visual feedback on tap (scale animation, color flash)
  - Keyboard shortcuts: ← = pass, ↑ = save, → = like
- [ ] Create `frontend/src/components/SwipeFeedback.jsx`
  - Overlay animation when swiping: "LIKED ❤️" or "PASSED ✕"
  - Slides the card off screen in the swipe direction
  - Auto-loads next card from the stack

#### Day 4–5: Preferences Page Updates

- [ ] Add map picker component to `/preferences` page
  - Use Mapbox GL JS or Leaflet (free, no API key needed)
  - User clicks on map to set target location
  - Shows a pin at selected location
  - Displays address/neighborhood name below map
  - Saves `target_latitude` and `target_longitude` to `personal_preferences`
  - Auto-center map on user's `target_city`
- [ ] Add "Swipe History" section to user profile or dashboard
  - Shows list of liked listings with thumbnail + title
  - "Undo" button to unlike (calls `DELETE /api/interactions/{id}`)
  - Stats: "You've liked 12 listings, passed on 34"

**Files to create/modify:**
```
CREATE  frontend/src/app/discover/page.jsx
CREATE  frontend/src/components/OnboardingSwipe.jsx
CREATE  frontend/src/components/ListingCard.jsx
CREATE  frontend/src/components/SwipeControls.jsx
CREATE  frontend/src/components/SwipeFeedback.jsx
CREATE  frontend/src/components/MapPicker.jsx
MODIFY  frontend/src/app/preferences/page.jsx          (add map picker)
```

---

### 👤 Member 4 — Integration & Scoring

**Goal:** Scoring system improved, hybrid scorer ready, documentation complete.

#### Day 1–3: Scoring Improvements & Listing Categorization

- [ ] Rewrite `backend/app/services/stable_matching/scoring.py`
  - New weight distribution (9 factors in 3 tiers):
    - Tier 1: Location proximity (25), house rules (20), price efficiency (15)
    - Tier 2: Deposit (15), listing quality (10), date closeness (5)
    - Tier 3: Bathrooms (4), furnished (3), utilities (3)
  - Implement `calculate_location_proximity_score()` — Haversine distance
  - Implement `calculate_price_efficiency_score()` — budget position scoring
  - Implement `calculate_listing_quality_score()` — photo count, description length, verification
  - Implement `calculate_date_closeness_score()` — graduated by days apart
  - Reduce weights on `calculate_bathroom_score()` (20→4)
  - Reduce weights on `calculate_furnished_score()` (20→3)
  - Reduce weights on `calculate_utilities_score()` (20→3)
  - Keep `calculate_house_rules_score()` at 20
  - Update `calculate_deposit_score()` to use 15 pts
  - Verify total still = 100
- [ ] Update `data_parser.py` to include `photo_count` and `host_verified` in parsed listing data
- [ ] Run existing matching test to verify improved scoring doesn't break stability
- [ ] Create `backend/app/services/listing_categorizer.py`
  - `categorize_listing(listing) → str` — rule-based labeling into 5 categories:
    - `budget`: price_per_person < $700
    - `premium`: price_per_person > $1,200 + 5+ amenities
    - `campus`: distance to nearest campus < 2 km
    - `social`: downtown_score > 0.7 (based on lat/lng)
    - `spacious`: 3+ bedrooms or 1,000+ sqft
  - `categorize_all_listings()` — batch-label all active listings
  - `get_onboarding_listings(city) → list[5]` — pick best representative from each category

#### Day 4–5: Hybrid Scorer & Testing

- [ ] Create `backend/app/services/stable_matching/ai_scorer.py`
  - `calculate_hybrid_score(group, listing, user_id, ai_weight)` function
  - `get_adaptive_ai_weight(user_id)` — returns weight based on swipe count:
    - < 20 swipes: 0.0 (pure rules)
    - 20–50 swipes: 0.3
    - 50–100 swipes: 0.5
    - 100+ swipes: 0.7
  - `blend_scores(rule_score, ai_score, weight)` — weighted average
- [ ] Modify `calculate_group_score()` to accept optional `ai_score` parameter
- [ ] Add `.env` flags: `AI_SCORING_ENABLED`, `AI_WEIGHT_OVERRIDE`
- [ ] Create `backend/app/ai/heuristic_scorer.py`
  - Wraps existing scoring into a per-user function for cold-start feed ranking
- [ ] Write integration tests:
  - Test scoring with AI disabled (should match old behavior)
  - Test scoring with AI enabled at various weights
  - Test adaptive weight calculation
  - Test that Gale-Shapley still produces stable matches with new scoring
- [ ] Prepare demo presentation material (update all .md docs with final details)

**Files to create/modify:**
```
MODIFY  backend/app/services/stable_matching/scoring.py      (rebalance weights, add new functions)
MODIFY  backend/app/services/data_parser.py                  (add photo_count, host_verified)
CREATE  backend/app/services/stable_matching/ai_scorer.py
CREATE  backend/app/services/listing_categorizer.py
CREATE  backend/app/ai/heuristic_scorer.py
MODIFY  backend/app/.env                                     (add AI flags)
```

---

## Week 2 (Feb 17–23): Integration & Polish

Week 2 is about **connecting everyone's work together** and making it demo-ready.

---

### 👤 Member 1 — Backend & Data Infrastructure

#### Day 6–7: Model Serving Infrastructure

- [ ] Create `backend/app/ai/inference.py`
  - `ModelServer` singleton class
    - `load_model(path)` — load trained PyTorch model from checkpoint
    - `predict(user_features, item_features) → float`
    - `predict_batch(user_features, item_features_list) → list[float]`
    - `is_loaded() → bool`
  - Add graceful fallback: if model not found, return `None` (triggers heuristic)
- [ ] Modify `main.py` — load model on app startup using `lifespan` handler
  - If model checkpoint exists → load it
  - If not → log warning, continue with heuristic-only scoring
- [ ] Create batch embedding script `backend/app/ai/batch_embed.py`
  - `--target listings` — embed all active listings, store in `listing_embeddings`
  - `--target users` — embed all users with 5+ swipes, store in `user_embeddings`
  - Can be run as a CLI: `python -m app.ai.batch_embed --target listings`
- [ ] Wire up `GET /api/discover/{user_id}` to use hybrid scoring
  - If model is loaded → compute AI scores → blend with rule scores
  - If model not loaded → use heuristic scores only

#### Day 8–10: End-to-End Testing & Bug Fixes

- [ ] Test full discovery flow: open page → see listings → swipe → logged in DB
- [ ] Test edge cases: no listings in city, user with no preferences, listing with no photos
- [ ] Performance test: scoring 100 listings should take < 500ms
- [ ] Fix any bugs from integration with Members 2, 3, 4

---

### 👤 Member 2 — ML Engineer

#### Day 6–7: Training with Synthetic Data

- [ ] Create `backend/app/ai/synthetic_data.py` — generate fake training data for testing
  - Generate 50 fake users with realistic preferences
  - Generate 100 fake listings with realistic features
  - Generate 2,000 fake interactions (likes/passes) with realistic patterns
    - Users near campus → more likely to like nearby listings
    - Users with low budget → more likely to like cheap listings
    - Random noise to simulate real behavior
  - Output: CSV or direct insertion into test database
- [ ] Train model on synthetic data
  - Verify training loop runs without errors
  - Verify loss decreases over epochs
  - Verify AUC > 0.60 on validation set (synthetic data is easy)
  - Save checkpoint to `backend/app/ai/checkpoints/latest.pt`

#### Day 8–9: Siamese Network Training

- [ ] Extract roommate pairs from `group_members` table
- [ ] Build training set with positive/negative/random pairs
- [ ] Train Siamese model (if enough data exists)
- [ ] If not enough data → train on synthetic pairs + document what's needed
- [ ] Save checkpoint to `backend/app/ai/checkpoints/siamese_v1.pt`

#### Day 10: Model Evaluation & Documentation

- [ ] Write evaluation report:
  - Training curves (loss per epoch)
  - Validation AUC, accuracy, precision, recall
  - Example predictions: "User X + Listing Y → score 0.87 (correct: liked)"
  - Model size, inference latency
- [ ] Document how to retrain: `python -m app.ai.training --data-source supabase --epochs 20`
- [ ] Create `backend/app/ai/checkpoints/README.md` explaining model versioning

---

### 👤 Member 3 — Frontend Developer

#### Day 6–7: Connect Frontend to Backend

- [ ] Connect discover page to `GET /api/discover/{user_id}` endpoint
  - Handle loading states, errors, empty results
  - Implement infinite scroll or "load more" when stack runs out
- [ ] Connect swipe buttons to `POST /api/interactions` endpoint
  - Show toast notification on swipe: "Listing saved!" / "Passed"
  - Handle network errors gracefully (retry, offline queue)
- [ ] Connect map picker to `PUT /api/preferences` endpoint
  - Auto-save lat/lng when user places pin
  - Show confirmation: "Target location saved ✓"

#### Day 8–9: Polish & Animations

- [ ] Smooth swipe animations (card slides left/right/up)
- [ ] Photo carousel with touch/swipe support
- [ ] Responsive design: works on mobile and desktop
- [ ] Dark mode support (if app has dark mode)
- [ ] Empty state illustrations ("No more listings — check back later!")
- [ ] Swipe history page with undo functionality

#### Day 10: Demo Preparation

- [ ] Record a screen recording of the full swipe flow
- [ ] Fix any visual bugs
- [ ] Ensure the demo path works end-to-end:
  1. User logs in
  2. Sets preferences (with map pin)
  3. Opens /discover
  4. Swipes through 5+ listings
  5. Views swipe history

---

### 👤 Member 4 — Integration & Scoring

#### Day 6–7: Full Pipeline Integration

- [ ] Connect hybrid scorer to Member 2's trained model:
  - `ai_scorer.py` calls `ModelServer.predict()` for AI scores
  - Falls back gracefully if model not loaded
- [ ] Wire hybrid scoring into the stable matching route (`routes/stable_matching.py`):
  - Before building preference lists, precompute AI scores for all feasible pairs
  - Pass AI scores into `build_preference_lists()`
  - Verify Gale-Shapley output is still stable
- [ ] Test A/B flag: `AI_SCORING_ENABLED=false` should produce identical results to old system

#### Day 8–9: End-to-End Validation

- [ ] Run full matching pipeline with AI scoring enabled:
  1. Fetch groups and listings from Supabase
  2. Build feasible pairs (hard constraints)
  3. Score with hybrid scorer (rule + AI)
  4. Run Gale-Shapley
  5. Run LNS optimizer
  6. Verify stable matches
- [ ] Compare match quality: AI-enabled vs. rule-only
  - Average match score
  - Number of feasible pairs
  - Any ranking differences
- [ ] Document results in a brief report

#### Day 10: Final Documentation & Presentation

- [ ] Update all .md files with final implementation details
- [ ] Create presentation slides covering:
  - What we built and why
  - Two-Tower architecture (use diagram from explainer doc)
  - Before/after scoring comparison
  - Demo walkthrough
  - Future work (Phases 6–7 from roadmap)
- [ ] Review all code, add docstrings where missing
- [ ] Final PR: merge `neural_net` → `main`

---

## Daily Standup Checkpoints

| Day | Date | Milestone |
|---|---|---|
| **1** | Feb 10 (Mon) | Everyone has their tasks, starts working |
| **2** | Feb 11 (Tue) | Member 1: migrations done. Member 2: config + embeddings done |
| **3** | Feb 12 (Wed) | Member 1: interaction API done. Member 3: discover page layout done |
| **4** | Feb 13 (Thu) | Member 2: model + features done. Member 4: scoring rewrite done |
| **5** | Feb 14 (Fri) | **Week 1 checkpoint: all individual parts work in isolation** |
| **6** | Feb 17 (Mon) | Start integration — connect frontend ↔ backend ↔ model |
| **7** | Feb 18 (Tue) | Member 2: synthetic data training. Member 1: model serving ready |
| **8** | Feb 19 (Wed) | Member 4: hybrid scorer wired to model. Member 3: swipe flow works |
| **9** | Feb 20 (Thu) | Full pipeline working end-to-end. Bug fixes. |
| **10** | Feb 21 (Fri) | **Final checkpoint: demo-ready, documented, PR prepared** |

---

## Dependency Map

```
                    WEEK 1 (Parallel)                          WEEK 2 (Integration)
                    ─────────────────                          ────────────────────

Member 1            ┌──────────────────┐                       ┌──────────────────┐
(Backend)           │ Migrations       │                       │ Model serving    │
                    │ Interaction API  │──────────────────────▶│ Discovery feed   │
                    │ Discovery route  │                       │ E2E testing      │
                    └──────────────────┘                       └────────┬─────────┘
                                                                       │
Member 2            ┌──────────────────┐                       ┌───────┴──────────┐
(ML)                │ Embeddings       │                       │ Synthetic train  │
                    │ Feature eng.     │──────────────────────▶│ Siamese network  │
                    │ Model + Training │                       │ Eval report      │
                    └──────────────────┘                       └────────┬─────────┘
                                                                       │
Member 3            ┌──────────────────┐                       ┌───────┴──────────┐
(Frontend)          │ Discover page    │                       │ Connect to API   │
                    │ Swipe UI         │──────────────────────▶│ Polish/animate   │
                    │ Map picker       │                       │ Demo prep        │
                    └──────────────────┘                       └────────┬─────────┘
                                                                       │
Member 4            ┌──────────────────┐                       ┌───────┴──────────┐
(Integration)       │ Scoring rewrite  │                       │ Wire hybrid      │
                    │ Hybrid scorer    │──────────────────────▶│ E2E validation   │
                    │ Heuristic scorer │                       │ Docs + slides    │
                    └──────────────────┘                       └──────────────────┘

                          ▲                                           ▲
                          │                                           │
                    No dependencies                           Everyone's Week 1
                    between members                           work must be done
```

---

## Risk Mitigation

| Risk | Impact | Who Owns | Mitigation |
|---|---|---|---|
| Migrations fail on Supabase | Blocks everyone | Member 1 | Test on local DB first; have rollback scripts |
| PyTorch install issues | Blocks ML work | Member 2 | Use `pip install torch --index-url https://download.pytorch.org/whl/cpu` for CPU-only |
| Sentence-transformer download slow | Delays embedding work | Member 2 | Download model on Day 1; cache in project |
| Frontend can't connect to backend (CORS) | Blocks integration | Members 1+3 | CORS is already configured in `main.py`; test early |
| Not enough real data for training | Model can't learn | Member 2 | Synthetic data generator (Day 6–7) serves as backup |
| Scoring rewrite breaks existing matching | Regressions | Member 4 | Run old tests before/after; compare outputs |
| Member falls behind | Sprint risk | Everyone | Daily standups; reassign tasks if someone's blocked |

---

## Definition of Done (Feb 24)

- [ ] ✅ All 4 migrations applied to Supabase (including listing categories)
- [ ] ✅ `POST /api/interactions` and `GET /api/discover/{user_id}` working
- [ ] ✅ All active listings categorized into 5 categories
- [ ] ✅ Onboarding flow: new user swipes on 5 categorized listings before seeing main feed
- [ ] ✅ `/discover` page renders listings and swipes log to database
- [ ] ✅ Map picker saves target lat/lng
- [ ] ✅ Scoring system rebalanced (9 factors, 3 tiers)
- [ ] ✅ Two-Tower model trains on synthetic data, saves checkpoint
- [ ] ✅ Hybrid scorer blends AI + rule scores with adaptive weight
- [ ] ✅ `AI_SCORING_ENABLED=false` produces identical results to old system
- [ ] ✅ Full pipeline runs: discover → swipe → match → stable output
- [ ] ✅ All .md documentation finalized
- [ ] ✅ Demo recording ready
- [ ] ✅ PR from `neural_net` → `main` prepared
