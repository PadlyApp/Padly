# Padly — Source of Truth
**Last Updated:** 2026-03-16
**Branch:** `neural_net`

---

## What Is Padly?

Padly is a housing and roommate matching platform for students, interns, and early-career professionals. It connects users into **roommate groups**, then matches those groups to **housing listings** using intelligent algorithms.

Core differentiator: most platforms match individuals to listings. Padly matches **groups to listings**, ensuring roommate compatibility before housing search.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, Mantine UI, TanStack React Query |
| Backend | FastAPI (Python), Uvicorn ASGI |
| Database | PostgreSQL via Supabase |
| Auth | Supabase Auth (JWT) |
| ML (in-progress) | PyTorch, sentence-transformers, CLIP |

**Run locally:**
```bash
# Backend (from /backend)
.\venv\Scripts\activate
uvicorn app.main:app --reload       # http://localhost:8000

# Frontend (from /frontend)
npm run dev                         # http://localhost:3000
```

---

## Project Structure

```
Padly/
├── backend/
│   └── app/
│       ├── main.py                         # FastAPI entry point
│       ├── models.py                       # Pydantic models
│       ├── routes/                         # API endpoints
│       │   ├── auth.py
│       │   ├── users.py
│       │   ├── groups.py                   # Roommate groups (large file)
│       │   ├── listings.py
│       │   ├── preferences.py
│       │   ├── matches.py
│       │   ├── roommates.py
│       │   ├── stable_matching.py
│       │   └── admin.py
│       ├── services/
│       │   ├── stable_matching/
│       │   │   ├── feasible_pairs.py       # Hard constraint filtering
│       │   │   ├── scoring.py              # Soft preference scoring (0-100)
│       │   │   ├── deferred_acceptance.py  # Gale-Shapley algorithm
│       │   │   ├── persistence.py
│       │   │   └── ai_scorer.py            # [TODO] Hybrid AI+rule scorer
│       │   ├── user_group_matching.py      # User-to-group compatibility
│       │   ├── lns_optimizer.py            # LNS optimization
│       │   ├── group_preferences_aggregator.py
│       │   ├── group_rematching_service.py
│       │   ├── listing_categorizer.py      # [TODO] 5-category labeling
│       │   └── data_parser.py
│       ├── ai/
│       │   ├── two_tower_baseline.py       # TF baseline (exists)
│       │   ├── generate_renter_data.py     # Synthetic data (exists)
│       │   ├── config.py                   # [TODO] Hyperparameters
│       │   ├── embeddings.py               # [TODO] Text + image embedders
│       │   ├── feature_engineering.py      # [TODO] Raw data → tensors
│       │   ├── model.py                    # [TODO] PyTorch TwoTowerModel
│       │   ├── training.py                 # [TODO] Training loop
│       │   ├── siamese.py                  # [TODO] Roommate compatibility
│       │   ├── inference.py                # [TODO] ModelServer singleton
│       │   ├── heuristic_scorer.py         # [TODO] Cold-start scorer
│       │   └── batch_embed.py              # [TODO] Precompute embeddings
│       ├── dependencies/
│       │   ├── auth.py
│       │   └── supabase.py
│       └── db.py
├── frontend/
│   └── src/app/
│       ├── page.jsx                        # Landing page
│       ├── layout.jsx
│       ├── login/page.jsx
│       ├── signup/page.jsx
│       ├── account/page.jsx
│       ├── onboarding/page.jsx
│       ├── groups/
│       │   ├── page.jsx
│       │   ├── create/page.jsx
│       │   └── [id]/page.jsx + edit/
│       ├── listings/[id]/page.jsx
│       ├── matches/page.jsx
│       ├── preferences/page.jsx            # Needs map picker
│       ├── invitations/page.jsx
│       ├── discover/page.jsx               # [TODO] Swipe/discover UI
│       ├── components/
│       │   ├── Navigation.jsx
│       │   ├── ProtectedRoute.jsx
│       │   ├── OnboardingSwipe.jsx         # [TODO]
│       │   ├── ListingCard.jsx             # [TODO]
│       │   ├── SwipeControls.jsx           # [TODO]
│       │   ├── SwipeFeedback.jsx           # [TODO]
│       │   └── MapPicker.jsx               # [TODO]
│       └── contexts/AuthContext.jsx
├── backend/migrations/
│   ├── 001_dynamic_group_sizing.sql        # ✅ Applied
│   ├── 002_solo_user_groups.sql            # ✅ Applied
│   ├── 003_expand_personal_preferences.sql # ✅ Applied (needs verification)
│   ├── 004_user_interactions.sql           # [TODO] Swipe tracking
│   ├── 005_embedding_tables.sql            # [TODO] Embedding cache
│   ├── 006_scoring_improvements.sql        # [TODO] lat/lng + photo count
│   └── 007_listing_categories.sql          # [TODO] category + onboarding_completed
└── run-dev.sh
```

---

## Matching Pipeline (Existing — Works)

```
User Preferences
    ↓
feasible_pairs.py      ← Hard constraints: city, budget, bedrooms, date, lease
    ↓
scoring.py             ← Soft scoring (0-100): bathrooms, furnished, utilities, deposit, house rules
    ↓
deferred_acceptance.py ← Gale-Shapley stable matching
    ↓
lns_optimizer.py       ← LNS optimization (+13.8% quality in tests)
    ↓
persistence.py         ← Save stable matches to DB
```

**Test results (Oakland, Dec 2025):** 23/24 groups matched, 1.37s execution time.

---

## ML Integration (In-Progress — `neural_net` branch)

### Goal

Replace static soft scoring with a **Two-Tower Neural Network** that learns from user swipe behavior. Add a **Swipe/Discover UI** to collect training data.

### Target Architecture (After ML)

```
User Preferences + Swipe History
    ↓
feasible_pairs.py      ← Hard constraints (unchanged)
    ↓
ai_scorer.py           ← Hybrid: (ai_weight × AI score) + ((1-ai_weight) × rule score)
    ↓
deferred_acceptance.py ← Gale-Shapley (unchanged)
    ↓
lns_optimizer.py       ← LNS (unchanged)
```

### Two-Tower Model

- **User Tower:** ~480-dim input → 256 → 128 → 64-dim embedding
- **Item Tower:** ~923-dim input → 256 → 128 → 64-dim embedding
- **Output:** `sigmoid(dot(user_emb, item_emb))` → 0-1 score
- **Training:** Binary cross-entropy on (like=1, pass=0) swipe data
- **Loss options:** `binary_crossentropy` or `softmax`

### Adaptive AI Weight (cold-start safe)

| Swipe count | AI weight | Behavior |
|---|---|---|
| < 20 | 0.0 | Pure rule-based |
| 20–50 | 0.3 | Mostly rules |
| 50–100 | 0.5 | Balanced |
| 100+ | 0.7 | Mostly AI |

### Siamese Network (roommate matching)

- Compares two user profiles through the same network
- Small Euclidean distance = compatible roommates
- Training data from `group_members` table (positive: same accepted group)

---

## Key Data Models

### User Preferences (`personal_preferences` table)

**Hard constraints:** `target_city`, `target_state_province`, `budget_min`, `budget_max`, `required_bedrooms`, `move_in_date`, `target_lease_type`, `target_lease_duration_months`

**Soft preferences:** `target_bathrooms`, `target_furnished`, `target_utilities_included`, `target_deposit_amount`, `target_house_rules`

**Pending (migration 006):** `target_latitude`, `target_longitude`

### Listing Categories (pending migration 007)

| Category | Rule |
|---|---|
| `budget` | price/person < $700 |
| `premium` | price/person > $1200 + 5+ amenities |
| `campus` | < 2km from nearest campus |
| `social` | downtown_score > 0.7 |
| `spacious` | 3+ bedrooms OR 1000+ sqft |

Used for **onboarding**: new users swipe on 5 categorized listings before seeing main feed.

---

## Scoring System

### Current (5 factors, 100 pts)

| Factor | Points |
|---|---|
| Bathrooms | 20 |
| Furnished | 20 |
| Utilities | 20 |
| Deposit | 20 |
| House rules | 20 |

### Proposed (9 factors, 3 tiers, 100 pts)

| Tier | Factor | Points |
|---|---|---|
| 1 (High) | Location proximity | 25 |
| 1 (High) | House rules | 20 |
| 1 (High) | Price efficiency | 15 |
| 2 (Med) | Deposit | 15 |
| 2 (Med) | Listing quality | 10 |
| 2 (Med) | Date closeness | 5 |
| 3 (Low) | Bathrooms | 4 |
| 3 (Low) | Furnished | 3 |
| 3 (Low) | Utilities | 3 |

---

## API Endpoints

### Auth
- `POST /api/auth/signup` / `signin` / `signout`
- `GET /api/auth/me`

### Users
- `GET/PUT /api/users/{user_id}`

### Groups
- `GET /api/roommate-groups` (with filters)
- `POST /api/roommate-groups` (create)
- `POST /api/roommate-groups/{id}/request-join`
- `POST /api/roommate-groups/{id}/accept-request/{user_id}`
- `DELETE /api/roommate-groups/{id}/leave`

### Matching
- `GET /api/matches/groups` — compatible groups for user
- `POST /api/stable-matches/run` — run matching algorithm
- `GET /api/stable-matches/active`

### Preferences
- `GET/PUT /api/preferences/{user_id}`

### Interactions (TODO — migration 004 needed)
- `POST /api/interactions` — log swipe
- `GET /api/interactions/{user_id}/history`
- `GET /api/interactions/{user_id}/stats`
- `DELETE /api/interactions/{interaction_id}`

### Discover (TODO)
- `GET /api/discover/{user_id}` — ranked listing feed
- `GET /api/discover/{user_id}/onboarding` — 5 categorized onboarding listings
- `POST /api/discover/{user_id}/onboarding/complete`

---

## What's Done vs. TODO

### ✅ Done
- Auth system (signup, login, JWT)
- User profiles and account management
- Roommate groups (create, join, request, approve, leave)
- Housing listings (browse, view, manage)
- Preferences system (all 13 fields synced frontend ↔ backend)
- Gale-Shapley stable matching
- LNS optimization
- User-to-group compatibility scoring
- TensorFlow two-tower baseline (`two_tower_baseline.py`)
- Synthetic data generator (`generate_renter_data.py`)

### ⏳ In-Progress / TODO (neural_net branch)

**Backend:**
- [ ] Migration 004: `user_interactions` table
- [ ] Migration 005: `user_embeddings` + `listing_embeddings` tables
- [ ] Migration 006: `target_latitude/longitude`, `photo_count`, `host_verified`
- [ ] Migration 007: `listings.category`, `users.onboarding_completed`
- [ ] `routes/interactions.py` — swipe logging API
- [ ] `services/listing_categorizer.py` — 5-category rule-based labeling
- [ ] `services/stable_matching/scoring.py` — rewrite with 9-factor system
- [ ] `services/stable_matching/ai_scorer.py` — hybrid scorer
- [ ] `ai/config.py` — hyperparameters
- [ ] `ai/embeddings.py` — TextEmbedder (MiniLM) + ImageEmbedder (CLIP)
- [ ] `ai/feature_engineering.py` — raw data → tensors
- [ ] `ai/model.py` — PyTorch TwoTowerModel
- [ ] `ai/training.py` — training loop + InteractionDataset
- [ ] `ai/siamese.py` — SiameseNetwork
- [ ] `ai/inference.py` — ModelServer singleton
- [ ] `ai/heuristic_scorer.py` — cold-start scoring wrapper
- [ ] `ai/batch_embed.py` — batch embedding pipeline
- [ ] Wire `GET /api/discover/{user_id}` with hybrid scoring
- [ ] Load model on FastAPI startup via `lifespan`

**Frontend:**
- [ ] `discover/page.jsx` — swipe/discover main page
- [ ] `components/OnboardingSwipe.jsx` — 5-card onboarding flow
- [ ] `components/ListingCard.jsx` — swipeable listing card
- [ ] `components/SwipeControls.jsx` — like/pass/save buttons
- [ ] `components/SwipeFeedback.jsx` — swipe animation overlay
- [ ] `components/MapPicker.jsx` — map pin for target location
- [ ] Update `preferences/page.jsx` — add map picker
- [ ] Swipe history section on profile

---

## Database Notes

- **Supabase project** — credentials in `backend/app/.env` (not committed)
- Migration 003 is written but needs Supabase SQL Editor execution to take effect
- Migrations 004–007 are planned but not yet written

---

## Key Docs in This Repo

| File | Contents |
|---|---|
| `README.md` | Setup instructions, tech stack, API overview |
| `ML_ROADMAP.md` | Full ML integration plan (Phases 0–7) |
| `SPRINT_PLAN.md` | 2-week sprint plan (Feb 10–24, 2026), 4-member team roles |
| `SCORING_IMPROVEMENTS.md` | Proposed 9-factor scoring rewrite with code |
| `TWO_TOWER_EXPLAINER.md` | How the Two-Tower model works, with full example |
| `DATASET_REQUIREMENTS.md` | Dataset schemas for ML training (A–E) |
| `ML_addition.md` | High-level AI implementation guide |
| `PREFERENCES_UPDATE_COMPLETE.md` | Preferences sync status (frontend ↔ backend) |
| `backend/MATCHING_ALGORITHM.md` | Full matching algorithm documentation |
| `SOURCE_OF_TRUTH.md` | **This file** |
