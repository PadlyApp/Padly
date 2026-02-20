### **Quick Implementation Summary**

* **The Model:** A **Two-Tower Network** (standard for Netflix/YouTube/Uber).
* **The Inputs:** User history/preferences (Tower A) and Listing data (Tower B).
* **The "Brain":** It outputs a 0-1 score representing the likelihood of a "Swipe Right."
* **Integration:** This score feeds directly into your Gale-Shapley algorithm as the preference weight.

---

### **AI_IMPLEMENTATION.md**

```markdown
# AI Implementation Guide for Padly
**Version:** 1.0
**Status:** Draft
**Focus:** Recommendation Engine (Two-Tower) & Roommate Compatibility (Siamese)

---

## 1. High-Level Architecture
We are moving from a "Filter-based" system to a "Prediction-based" system.

### The Problem
Filters (Price < $1000) are rigid. They don't capture "I like $1100 if it has a gym."
Neural Networks capture these non-linear trade-offs.

### The Solution: Two-Tower Architecture
This architecture is industry standard for retrieval at scale.
* **User Tower:** Compresses user attributes + past swipes into a vector (embedding).
* **Item Tower:** Compresses listing attributes + images into a vector (embedding).
* **Matching:** The `Dot Product` of these two vectors = Probability of Match.

```mermaid
graph LR
    subgraph "User Tower"
    A[User Profile] --> B[Embedding Layer]
    C[Past Swipes] --> B
    B --> D[User Vector (u)]
    end

    subgraph "Item Tower"
    E[Listing Text] --> F[BERT/Sentence Transformer]
    G[Listing Images] --> H[ResNet/CLIP]
    F --> I[Item Vector (v)]
    H --> I
    end

    D --> J{Dot Product}
    I --> J
    J --> K[Compatibility Score (0-1)]

```

---

## 2. Pre-trained Models to Use

Don't train from scratch! Use these Hugging Face models to turn text/images into numbers (embeddings).

### A. For Text (Bios, Descriptions)

**Model:** `sentence-transformers/all-MiniLM-L6-v2`

* **Why:** Ultra-fast, lightweight, and very accurate for semantic similarity.
* **Size:** ~80MB
* **Input:** "Looking for a quiet place near UTM..."
* **Output:** 384-dimensional vector.

### B. For Images (Room Photos)

**Model:** `openai/clip-vit-base-patch32`

* **Why:** CLIP understands images *semantically* (it knows what a "cozy modern bedroom" looks like).
* **Size:** ~350MB
* **Input:** [Image File]
* **Output:** 512-dimensional vector.

---

## 3. The "Swipe" Data Strategy

The neural net needs data to learn. You will use a **Hybrid approach**.

### Phase 1: Cold Start (No data yet)

1. User answers 5 weighted questions during onboarding.
2. **Heuristic Score:** Calculate match based on rule-based logic (e.g., Budget match = +20 pts).
3. **Action:** Show listings sorted by Heuristic Score.

### Phase 2: Data Collection (The Swipe)

Every time a user swipes, you log a training example:

* **Table:** `user_interactions`
* **Columns:** `user_id`, `listing_id`, `action` (0 = left/pass, 1 = right/like), `timestamp`.

### Phase 3: The Learning Loop

Every night (or every 100 swipes), retrain the User Tower.

* If User A swiped RIGHT on Listing B (which had "modern kitchen" tags), the model learns User A likes modern kitchens, *even if they didn't explicitly say so.*

---

## 4. Implementation Steps (Python/FastAPI)

### Step 1: Install Libraries

```bash
pip install torch sentence-transformers transformers scikit-learn

```

### Step 2: Define the Model (`backend/app/ai/model.py`)

This PyTorch model takes user and item features and predicts compatibility.

```python
import torch
import torch.nn as nn

class TwoTowerModel(nn.Module):
    def __init__(self, user_dim, item_dim, embedding_dim=64):
        super().__init__()
        
        # Tower A: User Network
        self.user_tower = nn.Sequential(
            nn.Linear(user_dim, 128),
            nn.ReLU(),
            nn.Linear(128, embedding_dim), # Compresses to 64 dims
            nn.LayerNorm(embedding_dim)
        )
        
        # Tower B: Item Network
        self.item_tower = nn.Sequential(
            nn.Linear(item_dim, 128),
            nn.ReLU(),
            nn.Linear(128, embedding_dim), # Compresses to 64 dims
            nn.LayerNorm(embedding_dim)
        )

    def forward(self, user_features, item_features):
        # 1. Generate Embeddings
        user_embedding = self.user_tower(user_features)
        item_embedding = self.item_tower(item_features)
        
        # 2. Calculate Similarity (Dot Product)
        # Higher dot product = higher compatibility
        similarity = (user_embedding * item_embedding).sum(1)
        
        # 3. Sigmoid to squash output between 0 and 1
        return torch.sigmoid(similarity)

```

### Step 3: Integrate with Gale-Shapley (`backend/app/services/stable_matching.py`)

You don't need to change the core Gale-Shapley logic. You only change how the **Preference List** is sorted.

```python
def get_ai_adjusted_preferences(user_id, available_listings):
    """
    Returns listings sorted by AI score, filtering out hard dealbreakers.
    """
    
    # 1. Get Hard Constraints (The "Must Haves")
    # If budget > user.max_budget, remove from list immediately.
    valid_listings = filter_hard_constraints(user_id, available_listings)
    
    # 2. Get AI Scores (The "Vibe Check")
    # Call the model to predict probability of swipe right
    scores = {}
    for listing in valid_listings:
        # Calculate features (simplified for example)
        user_vec = get_user_vector(user_id) 
        item_vec = get_listing_vector(listing.id)
        
        # Inference
        with torch.no_grad():
            ai_score = model(user_vec, item_vec).item()
            
        scores[listing.id] = ai_score

    # 3. Sort listings by AI Score (Highest first)
    sorted_listings = sorted(valid_listings, key=lambda x: scores[x.id], reverse=True)
    
    return sorted_listings

```

---

## 5. Roommate Matching (The "Siamese" Network)

For roommate grouping, you replace the "Item Tower" with another "User Tower" (since both sides are users).

1. **Input:** Two User Profiles.
2. **Process:** Pass both through the *same* network to get two vectors.
3. **Output:** Calculate Euclidean Distance.
* **Small Distance:** Compatible (Similar vibes).
* **Large Distance:** Incompatible.



**Pro Tip:** Add a "Complementary Factor." Sometimes opposites attract (e.g., an Introvert might need an Extrovert to handle landlord calls). You can learn this by training on successful past roommate groups.

---

## 6. Next Steps for You

1. **Data Collection:** Ensure your database tracks `UserInteractions` (swipes).
2. **Feature Engineering:** Write a script to convert Listing text -> Vector using `sentence-transformers`.
3. **Deployment:** Load the PyTorch model inside your FastAPI app using `lifespan` events (so it loads once on startup, not on every request).

```

```