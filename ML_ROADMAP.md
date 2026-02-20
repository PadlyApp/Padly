# 🧠 Padly ML Integration Roadmap

**Branch:** `neural_net`
**Status:** Planning
**Last Updated:** 2026-02-09

---

## Overview

This roadmap details how to integrate the **Two-Tower Neural Network** (listing recommendations) and **Siamese Network** (roommate compatibility) into Padly's existing matching pipeline. Every phase maps directly to the current codebase structure.

### Current Architecture (What Exists)

```
User Preferences ──► Hard Constraint Filters ──► Soft Scoring (0-100) ──► Gale-Shapley DA ──► LNS Optimizer ──► Stable Matches
                     (feasible_pairs.py)         (scoring.py)             (deferred_acceptance.py)  (lns_optimizer.py)   (persistence.py)
```

### Target Architecture (After ML)

```
User Preferences ─┐
                   ├──► Hard Constraint Filters ──► Hybrid Score (Rule + AI) ──► Gale-Shapley DA ──► LNS Optimizer ──► Stable Matches
Swipe History ─────┘    (feasible_pairs.py)         (ai_scorer.py)               (deferred_acceptance.py)  (lns_optimizer.py)   (persistence.py)
                                                         │
                                                    Two-Tower Model
                                                    (model.py)
```

---

## Phase 0 — Foundation & Data Infrastructure
> **Goal:** Set up the database tables and backend scaffolding needed before any ML code.
> **Duration:** ~1 week
> **Prerequisites:** None (starts immediately)

### 0.1 Database: `user_interactions` Table

This is the most critical piece — without swipe data, the model can't learn.

**Migration file:** `backend/migrations/004_user_interactions.sql`

```sql
-- User interaction tracking (swipes, clicks, saves)
CREATE TABLE public.user_interactions (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    listing_id uuid NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('like', 'pass', 'save', 'view', 'click')),
    -- Context at time of interaction (for feature engineering)
    session_id uuid,
    position_in_feed INTEGER,             -- Where was the listing shown (rank bias correction)
    time_spent_seconds NUMERIC,           -- How long they looked at it
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT user_interactions_pkey PRIMARY KEY (id),
    CONSTRAINT user_interactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
    CONSTRAINT user_interactions_listing_id_fkey FOREIGN KEY (listing_id) REFERENCES public.listings(id)
);

-- Indexes for fast lookups during training & inference
CREATE INDEX idx_user_interactions_user_id ON public.user_interactions(user_id);
CREATE INDEX idx_user_interactions_listing_id ON public.user_interactions(listing_id);
CREATE INDEX idx_user_interactions_action ON public.user_interactions(action);
CREATE INDEX idx_user_interactions_created_at ON public.user_interactions(created_at DESC);

-- Composite index for fetching a user's history efficiently
CREATE INDEX idx_user_interactions_user_action ON public.user_interactions(user_id, action, created_at DESC);
```

### 0.2 Database: `user_embeddings` Cache Table

Store precomputed embeddings so inference is fast (no recalculating every request).

```sql
CREATE TABLE public.user_embeddings (
    user_id uuid NOT NULL,
    embedding_vector FLOAT8[] NOT NULL,       -- 64-dim vector from User Tower
    embedding_version INTEGER NOT NULL DEFAULT 1,
    model_version VARCHAR(50) NOT NULL DEFAULT 'v0.1',
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    interaction_count INTEGER NOT NULL DEFAULT 0,  -- How many swipes were used to compute this
    
    CONSTRAINT user_embeddings_pkey PRIMARY KEY (user_id),
    CONSTRAINT user_embeddings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
```

### 0.3 Database: `listing_embeddings` Cache Table

```sql
CREATE TABLE public.listing_embeddings (
    listing_id uuid NOT NULL,
    text_embedding FLOAT8[],                  -- 384-dim from sentence-transformers
    image_embedding FLOAT8[],                 -- 512-dim from CLIP
    combined_embedding FLOAT8[] NOT NULL,     -- 64-dim from Item Tower
    embedding_version INTEGER NOT NULL DEFAULT 1,
    model_version VARCHAR(50) NOT NULL DEFAULT 'v0.1',
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT listing_embeddings_pkey PRIMARY KEY (listing_id),
    CONSTRAINT listing_embeddings_listing_id_fkey FOREIGN KEY (listing_id) REFERENCES public.listings(id)
);
```

### 0.4 Backend Scaffolding

Create the directory structure for AI modules:

```
backend/app/
├── ai/                          # NEW — All ML code lives here
│   ├── __init__.py
│   ├── config.py                # Model paths, hyperparameters, feature dimensions
│   ├── model.py                 # TwoTowerModel (PyTorch nn.Module)
│   ├── feature_engineering.py   # Raw data → tensor conversion
│   ├── embeddings.py            # Sentence-transformer & CLIP wrappers
│   ├── inference.py             # Load model + predict score
│   ├── training.py              # Training loop + data loader
│   └── siamese.py               # Roommate Siamese network (Phase 5)
├── routes/
│   └── interactions.py          # NEW — API for logging swipes
├── services/
│   └── stable_matching/
│       └── ai_scorer.py         # NEW — Hybrid scoring (rules + AI)
```

### 0.5 Update `requirements.txt`

```
# --- Existing ---
fastapi==0.118.0
uvicorn==0.37.0
supabase==2.21.1
python-dotenv==1.0.0
pydantic[email]==2.12.3
email-validator==2.2.0
httpx>=0.27

# --- NEW: ML Dependencies ---
torch>=2.2.0
sentence-transformers>=2.5.0
transformers>=4.38.0
numpy>=1.26.0
scikit-learn>=1.4.0
```

### 0.6 Deliverables Checklist

- [ ] Migration `004_user_interactions.sql` written & applied
- [ ] Migration `005_embedding_tables.sql` written & applied
- [ ] `backend/app/ai/` directory created with `__init__.py` and `config.py`
- [ ] `backend/app/routes/interactions.py` stub created
- [ ] `requirements.txt` updated with ML deps
- [ ] Router registered in `main.py`

---

## Phase 1 — Interaction Logging API & Swipe UI
> **Goal:** Build the data pipeline — users swipe, backend logs it.
> **Duration:** ~1.5 weeks
> **Prerequisites:** Phase 0

### 1.1 Backend: Interaction Routes

**File:** `backend/app/routes/interactions.py`

Endpoints to build:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/interactions` | Log a swipe (like/pass/save/view) |
| `GET` | `/api/interactions/{user_id}/history` | Get user's swipe history (for profile/analytics) |
| `GET` | `/api/interactions/{user_id}/stats` | Get interaction stats (total likes, passes, ratio) |
| `DELETE` | `/api/interactions/{interaction_id}` | Undo a swipe |

**Pydantic models to add in `models.py`:**

```python
class InteractionCreate(BaseModel):
    listing_id: str
    action: str  # 'like' | 'pass' | 'save' | 'view' | 'click'
    position_in_feed: Optional[int] = None
    time_spent_seconds: Optional[float] = None

class InteractionResponse(BaseModel):
    id: str
    user_id: str
    listing_id: str
    action: str
    created_at: datetime
```

### 1.2 Frontend: Swipe/Discover UI

**New page:** `frontend/src/app/discover/page.jsx`

This is the core new UX — a card-based discovery feed (think Tinder for apartments).

**Components needed:**

| Component | Purpose |
|-----------|---------|
| `ListingCard.jsx` | Full-screen swipeable listing card with photos, price, details |
| `SwipeControls.jsx` | Like (❤️), Pass (✕), Save (⭐) buttons |
| `SwipeFeedback.jsx` | Visual feedback animation on swipe |
| `DiscoverFilters.jsx` | Quick filter bar (city, budget range) |

**User flow:**
1. User visits `/discover`
2. Backend serves listings sorted by heuristic score (Phase 1) or AI score (Phase 3+)
3. User swipes right (like) or left (pass) on each listing
4. Each swipe calls `POST /api/interactions` with action + metadata
5. Liked listings appear on `/matches` page

### 1.3 Heuristic Cold-Start Scoring

Before the ML model is trained, we need a baseline scoring function that uses **explicit preferences** rather than swipe data.

**File:** `backend/app/ai/heuristic_scorer.py`

This wraps the existing `calculate_group_score()` from `scoring.py` into a per-user scoring function:

```python
def calculate_heuristic_score(user_prefs: dict, listing: dict) -> float:
    """
    Rule-based score (0-1) using existing preference weights.
    Used during cold start before the ML model has enough data.
    
    Scoring breakdown:
    - Budget fit:           25 pts
    - Location match:       20 pts  
    - Date compatibility:   15 pts
    - Amenity match:        15 pts
    - Lifestyle match:      15 pts
    - Verification bonus:   10 pts
    
    Returns: float between 0.0 and 1.0
    """
```

### 1.4 Deliverables Checklist

- [ ] `POST /api/interactions` endpoint working
- [ ] `GET /api/interactions/{user_id}/history` endpoint working
- [ ] Pydantic models for interactions added to `models.py`
- [ ] Interactions router registered in `main.py`
- [ ] `/discover` page with swipeable listing cards
- [ ] Each swipe logs to `user_interactions` table
- [ ] Heuristic scorer wrapping existing `scoring.py` logic
- [ ] Feed sorted by heuristic score for cold-start users

---

## Phase 2 — Feature Engineering & Embedding Pipeline
> **Goal:** Turn raw user/listing data into numerical vectors the model can consume.
> **Duration:** ~1.5 weeks
> **Prerequisites:** Phase 1

### 2.1 Text Embeddings

**File:** `backend/app/ai/embeddings.py`

Use `sentence-transformers/all-MiniLM-L6-v2` (~80MB) to embed:
- Listing titles + descriptions → 384-dim vector
- User bios → 384-dim vector
- House rules text → 384-dim vector

```python
from sentence_transformers import SentenceTransformer

class TextEmbedder:
    def __init__(self):
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    
    def embed(self, text: str) -> np.ndarray:
        """Returns 384-dim vector."""
        return self.model.encode(text, normalize_embeddings=True)
    
    def embed_listing(self, listing: dict) -> np.ndarray:
        """Combine title + description + house_rules into single embedding."""
        parts = [
            listing.get('title', ''),
            listing.get('description', ''),
            listing.get('house_rules', '')
        ]
        combined = ' '.join(p for p in parts if p)
        return self.embed(combined)
```

### 2.2 Image Embeddings (for listing photos)

**File:** `backend/app/ai/embeddings.py` (same file)

Use `openai/clip-vit-base-patch32` (~350MB) to embed listing photos:

```python
from transformers import CLIPProcessor, CLIPModel

class ImageEmbedder:
    def __init__(self):
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    
    def embed(self, image) -> np.ndarray:
        """Returns 512-dim vector from a single image."""
        inputs = self.processor(images=image, return_tensors="pt")
        outputs = self.model.get_image_features(**inputs)
        return outputs.detach().numpy().flatten()
    
    def embed_listing_photos(self, photo_urls: list) -> np.ndarray:
        """Average embeddings of all listing photos."""
        # Fetch images from URLs, embed each, return mean vector
```

### 2.3 Numerical Feature Engineering

**File:** `backend/app/ai/feature_engineering.py`

Convert structured data into feature tensors. This file bridges your existing Supabase data with PyTorch.

**User features** (input to User Tower):

| Feature | Source | Encoding |
|---------|--------|----------|
| `budget_min` | `personal_preferences.budget_min` | Normalized float |
| `budget_max` | `personal_preferences.budget_max` | Normalized float |
| `move_in_month` | `personal_preferences.move_in_date` | Cyclical (sin/cos of month) |
| `bio_embedding` | `users.bio` → sentence-transformer | 384-dim vector |
| `lifestyle_*` | `personal_preferences.lifestyle_preferences` | One-hot encoded (5 attributes × ~4 levels) |
| `swipe_history_embedding` | Mean of liked listing embeddings | 64-dim vector |
| `verification_status` | `users.verification_status` | One-hot (3 levels) |
| `role` | `users.role` | One-hot (3 levels) |

**→ Total user_dim ≈ 384 + 20 + 64 + 6 + 4 + 2 = ~480 features**

**Item (Listing) features** (input to Item Tower):

| Feature | Source | Encoding |
|---------|--------|----------|
| `price_per_month` | `listings.price_per_month` | Normalized float |
| `bedrooms` | `listings.number_of_bedrooms` | Integer |
| `bathrooms` | `listings.number_of_bathrooms` | Float |
| `area_sqft` | `listings.area_sqft` | Normalized float |
| `furnished` | `listings.furnished` | Binary |
| `utilities_included` | `listings.utilities_included` | Binary |
| `deposit_amount` | `listings.deposit_amount` | Normalized float |
| `text_embedding` | title + description → sentence-transformer | 384-dim vector |
| `image_embedding` | photos → CLIP | 512-dim vector |
| `property_type` | `listings.property_type` | One-hot (3 levels) |
| `lease_type` | `listings.lease_type` | One-hot (2 levels) |
| `amenities_vector` | `listings.amenities` (JSONB) | Multi-hot (N amenities) |

**→ Total item_dim ≈ 384 + 512 + 7 + 3 + 2 + ~15 = ~923 features**

### 2.4 Batch Embedding Pipeline

**File:** `backend/app/ai/batch_embed.py`

Script to precompute and cache embeddings in `listing_embeddings` and `user_embeddings` tables.

```bash
# Run nightly or on-demand
python -m app.ai.batch_embed --target listings  # Embed all active listings
python -m app.ai.batch_embed --target users     # Embed all users with 5+ swipes
```

### 2.5 Deliverables Checklist

- [ ] `TextEmbedder` class with listing/bio embedding methods
- [ ] `ImageEmbedder` class with CLIP integration
- [ ] `build_user_features()` function returning a PyTorch tensor
- [ ] `build_listing_features()` function returning a PyTorch tensor
- [ ] Batch embedding script for listings
- [ ] Batch embedding script for users
- [ ] Embeddings cached in `user_embeddings` and `listing_embeddings` tables
- [ ] Unit tests for feature dimensions (assert shapes match model input)

---

## Phase 3 — Two-Tower Model: Training & Inference
> **Goal:** Train the core recommendation model and wire it into the scoring pipeline.
> **Duration:** ~2 weeks
> **Prerequisites:** Phase 2 + at least ~500 swipe interactions collected

### 3.1 Model Definition

**File:** `backend/app/ai/model.py`

```python
import torch
import torch.nn as nn

class TwoTowerModel(nn.Module):
    """
    Two-Tower architecture for user↔listing compatibility.
    
    Architecture:
        User Tower:  user_dim → 256 → 128 → 64 (embedding)
        Item Tower:  item_dim → 256 → 128 → 64 (embedding)
        Output:      sigmoid(dot(user_emb, item_emb)) → [0, 1]
    """
    def __init__(self, user_dim: int, item_dim: int, embedding_dim: int = 64):
        super().__init__()
        
        self.user_tower = nn.Sequential(
            nn.Linear(user_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, embedding_dim),
            nn.LayerNorm(embedding_dim)
        )
        
        self.item_tower = nn.Sequential(
            nn.Linear(item_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, embedding_dim),
            nn.LayerNorm(embedding_dim)
        )

    def forward(self, user_features, item_features):
        user_emb = self.user_tower(user_features)
        item_emb = self.item_tower(item_features)
        similarity = (user_emb * item_emb).sum(dim=1)
        return torch.sigmoid(similarity)
    
    def get_user_embedding(self, user_features):
        """Extract user embedding (for caching)."""
        with torch.no_grad():
            return self.user_tower(user_features)
    
    def get_item_embedding(self, item_features):
        """Extract item embedding (for caching)."""
        with torch.no_grad():
            return self.item_tower(item_features)
```

### 3.2 Training Pipeline

**File:** `backend/app/ai/training.py`

| Aspect | Decision |
|--------|----------|
| **Loss** | Binary Cross-Entropy (like=1, pass=0) |
| **Optimizer** | AdamW, lr=1e-3, weight_decay=1e-4 |
| **Batch size** | 64 |
| **Epochs** | 20 (early stopping on validation loss, patience=3) |
| **Train/Val split** | 80/20 stratified by user |
| **Negative sampling** | For each `like`, sample 3 random uninteracted listings as implicit `pass` |
| **Trigger** | Nightly cron OR when any user reaches 100 new swipes |

**Training data source:**
```sql
SELECT
    ui.user_id,
    ui.listing_id,
    CASE WHEN ui.action = 'like' THEN 1 ELSE 0 END AS label,
    ui.position_in_feed,
    ui.time_spent_seconds
FROM user_interactions ui
WHERE ui.action IN ('like', 'pass')
ORDER BY ui.created_at;
```

### 3.3 Model Serving & Inference

**File:** `backend/app/ai/inference.py`

```python
class ModelServer:
    """Manages model lifecycle within FastAPI."""
    
    _instance = None
    
    def __init__(self):
        self.model = None
        self.text_embedder = None
        self.image_embedder = None
        self.model_version = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def load_model(self, model_path: str):
        """Load trained model from disk."""
        checkpoint = torch.load(model_path, map_location='cpu')
        self.model = TwoTowerModel(
            user_dim=checkpoint['user_dim'],
            item_dim=checkpoint['item_dim']
        )
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        self.model_version = checkpoint.get('version', 'unknown')
    
    def predict(self, user_features, item_features) -> float:
        """Predict compatibility score (0-1)."""
        with torch.no_grad():
            score = self.model(user_features, item_features)
        return score.item()
    
    def predict_batch(self, user_features, item_features_batch) -> list:
        """Score one user against many listings."""
        with torch.no_grad():
            # Expand user features to match batch
            user_batch = user_features.expand(len(item_features_batch), -1)
            scores = self.model(user_batch, item_features_batch)
        return scores.tolist()
```

**Load model on FastAPI startup** (modify `backend/app/main.py`):

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load ML model
    from app.ai.inference import ModelServer
    server = ModelServer.get_instance()
    model_path = os.getenv("MODEL_PATH", "app/ai/checkpoints/latest.pt")
    if os.path.exists(model_path):
        server.load_model(model_path)
        logger.info(f"ML model loaded: {server.model_version}")
    else:
        logger.warning("No ML model found — using heuristic scoring only")
    yield
    # Shutdown: cleanup

app = FastAPI(..., lifespan=lifespan)
```

### 3.4 Deliverables Checklist

- [ ] `TwoTowerModel` class with forward, get_user_embedding, get_item_embedding
- [ ] Training script with data loading, train/val split, early stopping
- [ ] Negative sampling strategy implemented
- [ ] Model checkpointing (save best model to `app/ai/checkpoints/`)
- [ ] `ModelServer` singleton with load, predict, predict_batch
- [ ] Model loaded at FastAPI startup via `lifespan`
- [ ] Training metrics logged (loss, AUC, accuracy per epoch)
- [ ] Validation AUC > 0.65 before proceeding to Phase 4

---

## Phase 4 — Integration with Gale-Shapley Pipeline
> **Goal:** Replace the static scoring in `scoring.py` with a hybrid AI + rule-based score.
> **Duration:** ~1 week
> **Prerequisites:** Phase 3 (trained model with AUC > 0.65)

### 4.1 The Hybrid Scorer

**File:** `backend/app/services/stable_matching/ai_scorer.py`

This is the **key integration point**. It sits between the existing `scoring.py` and the AI model.

```python
def calculate_hybrid_score(
    group: dict, 
    listing: dict, 
    user_id: str,
    ai_weight: float = 0.6  # How much to trust the AI vs rules
) -> float:
    """
    Hybrid score combining rule-based and AI scoring.
    
    Formula: final_score = (ai_weight × ai_score) + ((1 - ai_weight) × rule_score)
    
    The ai_weight ramps up as we collect more data:
      - < 20 swipes:  ai_weight = 0.0 (pure rules)
      - 20-50 swipes:  ai_weight = 0.3
      - 50-100 swipes: ai_weight = 0.5
      - 100+ swipes:   ai_weight = 0.7
    
    This ensures we never fully abandon the rule-based system.
    """
```

### 4.2 Where It Plugs In

The integration requires changes to **two existing files**:

#### A. `scoring.py` → `calculate_group_score()`

**Current** (line ~150):
```python
def calculate_group_score(group, listing) -> float:
    # Pure rule-based: bathrooms + furnished + utilities + deposit + house_rules
    score = 0
    score += calculate_bathroom_score(group, listing)
    score += calculate_furnished_score(group, listing)
    ...
    return score
```

**Modified:**
```python
def calculate_group_score(group, listing, ai_score: Optional[float] = None) -> float:
    rule_score = 0
    rule_score += calculate_bathroom_score(group, listing)
    rule_score += calculate_furnished_score(group, listing)
    ...
    
    if ai_score is not None:
        # Blend: AI score is 0-1, rule score is 0-100
        ai_normalized = ai_score * MAX_SCORE  # Scale AI to same range
        return blend_scores(rule_score, ai_normalized, ai_weight=get_ai_weight(group))
    
    return rule_score
```

#### B. `build_preference_lists()` → Pass AI scores through

**Current flow:**
```
build_preference_lists() → rank_listings_for_group() → calculate_group_score()
```

**Modified flow:**
```
build_preference_lists(ai_scores) → rank_listings_for_group(ai_scores) → calculate_group_score(ai_score=...)
```

The AI scores dict is precomputed in the route handler (`routes/stable_matching.py`) before calling the matching pipeline, so the **core Gale-Shapley algorithm (`deferred_acceptance.py`) doesn't change at all.** Only the preference list ordering changes.

### 4.3 Feed Ranking for `/discover`

**File:** `backend/app/routes/interactions.py` — add a new endpoint:

```
GET /api/discover/{user_id}?city=Toronto&limit=20
```

Returns listings ranked by hybrid score for the swipe feed:

```python
@router.get("/api/discover/{user_id}")
async def get_discovery_feed(user_id: str, city: str, limit: int = 20):
    # 1. Get all active listings in city
    # 2. Filter hard constraints
    # 3. Score each with hybrid scorer
    # 4. Exclude already-swiped listings
    # 5. Return top N sorted by score
```

### 4.4 A/B Testing Flag

Add an env variable so you can toggle AI scoring on/off per deployment:

```
# .env
AI_SCORING_ENABLED=true    # false = pure rule-based (rollback safety)
AI_WEIGHT_OVERRIDE=         # Empty = use adaptive weight; 0.5 = force 50% AI
```

### 4.5 Deliverables Checklist

- [ ] `ai_scorer.py` with `calculate_hybrid_score()` function
- [ ] Adaptive `ai_weight` based on user's swipe count
- [ ] `scoring.py` modified to accept optional `ai_score` parameter
- [ ] `build_preference_lists()` updated to pass AI scores
- [ ] `GET /api/discover/{user_id}` endpoint for ranked feed
- [ ] A/B testing flag in `.env`
- [ ] Gale-Shapley (`deferred_acceptance.py`) remains **unchanged**
- [ ] LNS optimizer (`lns_optimizer.py`) remains **unchanged**
- [ ] End-to-end test: run matching with AI scores, verify stable output

---

## Phase 5 — Roommate Siamese Network
> **Goal:** Use a Siamese Network to predict roommate compatibility between two users.
> **Duration:** ~1.5 weeks
> **Prerequisites:** Phase 2 (feature engineering)

### 5.1 The Siamese Architecture

**File:** `backend/app/ai/siamese.py`

Unlike the Two-Tower model (user vs. listing), the Siamese network compares **two users** through the **same** network (shared weights).

```
User A Profile ──► Shared Network ──► Embedding A ─┐
                                                     ├──► Euclidean Distance ──► Compatibility (0-1)
User B Profile ──► Shared Network ──► Embedding B ─┘
```

**Key difference:** Smaller distance = more compatible.

### 5.2 Training Data

Training data comes from **existing successful roommate groups**:

| Source | Label |
|--------|-------|
| Users in the **same accepted group** | Positive (compatible) |
| Users in **different groups** (random pairs) | Negative (unknown) |
| Users who **left a group** | Hard negative (incompatible) |

Query to extract training pairs:
```sql
-- Positive pairs: users in the same active group
SELECT 
    gm1.user_id AS user_a,
    gm2.user_id AS user_b,
    1 AS label
FROM group_members gm1
JOIN group_members gm2 ON gm1.group_id = gm2.group_id
WHERE gm1.user_id < gm2.user_id  -- avoid duplicates
  AND gm1.status = 'accepted'
  AND gm2.status = 'accepted';
```

### 5.3 Integration with Group System

This plugs into `user_group_matching.py`, specifically the `calculate_user_group_compatibility()` function (line 25).

**Current:** Pure rule-based (budget=20, date=15, lifestyle=20, etc. → 0-100)

**Modified:** Blend Siamese score with rule score, similar to Phase 4's hybrid approach.

### 5.4 "Complementary Factor"

Not all compatibility = similarity. Add a learned "complementary bonus":

- Introvert + Extrovert → bonus (handles social/landlord balance)
- Night owl + Early bird → penalty (sleep schedule conflict)
- Messy + Very clean → penalty (lifestyle clash)

This is learned from data — the model discovers which opposites attract and which clash.

### 5.5 Deliverables Checklist

- [ ] `SiameseNetwork` class in `siamese.py`
- [ ] Training data extraction from `group_members` table
- [ ] Contrastive loss function implemented
- [ ] `calculate_user_group_compatibility()` updated with AI blend
- [ ] Complementary factor logic
- [ ] Group recommendation endpoint returns AI-scored results

---

## Phase 6 — Production Hardening & Monitoring
> **Goal:** Make everything production-ready, observable, and maintainable.
> **Duration:** ~1.5 weeks
> **Prerequisites:** Phases 4 and 5

### 6.1 Model Versioning

```
backend/app/ai/
├── checkpoints/
│   ├── two_tower_v1.pt          # First trained model
│   ├── two_tower_v2.pt          # Retrained with more data
│   ├── siamese_v1.pt
│   └── latest.pt → two_tower_v2.pt  # Symlink to current best
```

Track which model version produced each match:
```sql
ALTER TABLE stable_matches ADD COLUMN model_version VARCHAR(50);
```

### 6.2 Monitoring Dashboard

Track these metrics:

| Metric | Target | Alert If |
|--------|--------|----------|
| AI model AUC (validation) | > 0.70 | < 0.60 |
| Average AI score for liked listings | > 0.65 | < 0.50 |
| Average AI score for passed listings | < 0.40 | > 0.55 |
| Model inference latency (p99) | < 50ms | > 200ms |
| Embedding cache hit rate | > 95% | < 80% |
| Daily interaction count | Growing | Drops > 30% |

### 6.3 Retraining Pipeline

```
Nightly cron (2:00 AM) OR manual trigger:
1. Export latest interactions from Supabase
2. Build train/val datasets
3. Train new model (TwoTower + Siamese)
4. Evaluate on held-out set
5. If AUC improved → save as new version → hot-reload
6. If AUC degraded → alert, keep old model
7. Recompute user/listing embeddings with new model
8. Update embedding cache tables
```

### 6.4 Fallback Strategy

The system should **never depend on the AI model being available.** Fallbacks:

| Scenario | Behavior |
|----------|----------|
| Model file missing | Use pure rule-based scoring (existing `scoring.py`) |
| Model inference error | Log error, fallback to heuristic score for that pair |
| User has < 5 swipes | Use pure heuristic score (no AI influence) |
| Listings have no embeddings | Compute on-the-fly OR fallback to text-only features |
| `.env AI_SCORING_ENABLED=false` | Disable AI completely (instant rollback) |

### 6.5 Deliverables Checklist

- [ ] Model versioning with symlink-based latest pointer
- [ ] `model_version` column added to `stable_matches`
- [ ] Monitoring metrics endpoint (`GET /api/ai/metrics`)
- [ ] Nightly retraining script (`scripts/retrain.py`)
- [ ] Auto-evaluation gate (only deploy if AUC improves)
- [ ] Graceful fallback on all error paths
- [ ] Load test: 100 concurrent scoring requests < 200ms p99

---

## Phase 7 — Advanced Features (Post-MVP)
> **Goal:** Stretch goals that further improve the recommendation system.
> **Duration:** Ongoing
> **Prerequisites:** Phases 0-6 stable in production

### 7.1 Explore/Exploit with Multi-Armed Bandits

Instead of always showing the highest-scored listings, occasionally show "exploration" listings to discover hidden preferences.

- Thompson Sampling: For each listing, sample from a Beta distribution based on like/pass history
- Epsilon-greedy: 90% exploit (top AI score), 10% explore (random)

### 7.2 Real-Time Embedding Updates

When a user swipes, immediately update their embedding in-memory (without full model retrain):

```python
# After user likes Listing X:
user_embedding = 0.9 * user_embedding + 0.1 * listing_x_embedding
# Effectively "nudges" the user vector toward the liked listing.
```

### 7.3 Image-Aware Recommendations

Use CLIP to understand visual preferences:
- "This user likes listings with hardwood floors and large windows"
- Generate visual preference tags automatically

### 7.4 Natural Language Search

Allow users to search with natural language:
- "Modern 2-bedroom near campus with gym under $1200"
- Encode query with sentence-transformer → compare with listing embeddings → rank by cosine similarity

### 7.5 Notification-Driven Matching

When a new listing is posted that scores > 0.85 for a user:
- Push notification: "🏠 A new listing just dropped that matches your vibe!"
- Email digest of top 5 new listings weekly

---

## Summary Timeline

| Phase | Name | Duration | Key Output |
|-------|------|----------|------------|
| **0** | Foundation & Data Infra | 1 week | DB tables, directory structure, deps |
| **1** | Interaction Logging + Swipe UI | 1.5 weeks | `/discover` page, swipe API, heuristic scoring |
| **2** | Feature Engineering & Embeddings | 1.5 weeks | Text/image embeddings, feature tensors, batch pipeline |
| **3** | Two-Tower Training & Inference | 2 weeks | Trained model, model server, FastAPI integration |
| **4** | Gale-Shapley Integration | 1 week | Hybrid scoring in matching pipeline, A/B flag |
| **5** | Roommate Siamese Network | 1.5 weeks | Roommate compatibility scoring |
| **6** | Production Hardening | 1.5 weeks | Monitoring, retraining, fallbacks |
| **7** | Advanced Features | Ongoing | Explore/exploit, real-time updates, NL search |

**Total estimated time to production-ready (Phases 0-6): ~10 weeks**

---

## Risk Log

| Risk | Impact | Mitigation |
|------|--------|------------|
| Not enough swipe data to train | Model underfits, bad recs | Heuristic fallback; synthetic data augmentation |
| PyTorch too heavy for deployment | Memory/CPU issues | Use ONNX Runtime for inference; quantize model |
| CLIP model too large (~350MB) | Slow startup, high memory | Lazy-load; use smaller CLIP variant; cache aggressively |
| Users don't use swipe UI | No data collected | Make `/discover` the default landing page; gamify |
| AI scores conflict with stable matching properties | Theoretical instability | AI only changes preference ordering, not the DA algorithm itself — stability is preserved |

---

*This roadmap is a living document. Update it as phases are completed.*
