# Stable Matching Algorithm - Test Results

## Oakland Test Run (December 3, 2025)

| Metric | Result |
|--------|--------|
| Groups Matched | 23 / 24 (96%) |
| Listings Matched | 23 / 23 (100%) |
| LNS Quality Improvement | +13.8% |
| Matching Stable | ✅ Yes (no blocking pairs) |
| Execution Time | 1.37 seconds |
| Feasible Pairs | 366 |
| Date Window | Oct 28, 2025 → Mar 17, 2026 |

---

## How It Works

### 1. Feasible Pairs (Hard Constraints)
First, we filter all group-listing pairs that satisfy **hard constraints**:
- City match
- State match (if specified)
- Budget range (listing price ÷ group size within budget)
- Bedroom count ≥ group size
- Move-in date within ±60 days
- Lease type match
- Lease duration match

**Result**: 366 feasible pairs from 24 groups × 47 listings

### 2. Scoring (Soft Preferences)
Each feasible pair gets scored 0-100 based on:
- Bathroom count match (20 pts)
- Furnished preference (20 pts)
- Utilities included (20 pts)
- Deposit amount (20 pts)
- House rules compatibility (20 pts)

### 3. Gale-Shapley Deferred Acceptance
Classic stable matching algorithm:
1. Each group proposes to their top-ranked listing
2. Listings tentatively accept best proposal, reject others
3. Rejected groups propose to next choice
4. Repeat until no more proposals

**Properties**:
- Guarantees stable matching (no blocking pairs)
- Group-optimal (best stable match for groups)
- O(n²) time complexity

### 4. LNS Optimization
Large Neighborhood Search improves match quality after Gale-Shapley produces a stable but not necessarily optimal matching.

#### Why LNS?
Gale-Shapley guarantees stability but is **group-optimal / listing-pessimal**. LNS explores the solution space to find better overall quality while accepting some instability trade-offs.

#### Quality Score Formula
Each match has a quality score calculated as:
```
quality = 0.4 × group_score      # How much group likes listing
        + 0.3 × listing_score    # How much listing likes group  
        + 0.2 × (100 / (group_rank + 1))   # Inverse of group's rank
        + 0.1 × (100 / (listing_rank + 1)) # Inverse of listing's rank
```

#### LNS Algorithm Steps

**Step 1: Identify Worst Matches (Destroy Phase)**
```python
# Sort matches by quality score (ascending)
# Take bottom 15% (worst matches)
destroy_count = max(1, int(total_matches * 0.15))
worst_matches = sorted(matches, key=quality)[:destroy_count]
```

**Step 2: Destroy Heuristics** (rotates each iteration)
| Heuristic | When | Strategy |
|-----------|------|----------|
| Worst-First | Every iteration | Target real problem matches |
| Random | Every 5th iteration | Diversification & exploration |
| Cluster | Every 3rd iteration | Destroy matches in same budget range |

**Step 3: Repair with Regret-Greedy**
```
For each unmatched group:
  1. Score all available listings
  2. Calculate regret = best_score - second_best_score
  3. Pair with highest regret first (most to lose if delayed)
  4. Remove from available pools
  5. Repeat until all paired
```

**Why Regret?** High regret means "if I don't assign this group now, they'll lose their best option." This prioritizes urgent assignments.

**Step 4: Acceptance Criterion (Simulated Annealing)**
```python
temperature = 0.1 × (max_iterations - current) / max_iterations

if new_quality >= current_quality:
    accept = True  # Always accept improvements
else:
    # Sometimes accept worse solutions for exploration
    delta = new_quality - current_quality
    accept = random() < exp(delta / temperature)
```
Temperature decreases over time → less exploration, more exploitation.

**Step 5: Early Stopping**
- Stop after 50 iterations OR
- Stop if no improvement for 10 consecutive iterations

#### Our Results
```
Initial (Gale-Shapley): avg_quality = X
After LNS (50 iters):   avg_quality = X × 1.138
Improvement:            +13.8%
```

#### Example Iteration
```
Iteration 12:
  → Destroy: 4 worst matches (worst-first heuristic)
  → Freed groups: [g1, g2, g3, g4]
  → Freed listings: [l1, l2, l3, l4]
  → Repair with regret-greedy:
      g2 → l3 (regret=25, highest)
      g4 → l1 (regret=18)
      g1 → l4 (regret=12)
      g3 → l2 (regret=8)
  → New quality: 72.5 > 68.3 (old)
  → Accepted ✓
```

---

## Sample Matches

| Group | Listing | Group Score | Listing Score | Rank |
|-------|---------|-------------|---------------|------|
| 9d78fdf1... | d6565b96... | 75/100 | 45/100 | #1 |
| de9e4ad2... | c422b36b... | 75/100 | 50/100 | #2 |
| f0e92780... | db6aa26a... | 75/100 | 45/100 | #3 |

---

## API Endpoints

```bash
# Run matching for a city
POST /api/stable-matches/run
{"city": "Oakland", "date_flexibility_days": 30}

# Get active matches
GET /api/stable-matches/active?city=Oakland

# Get statistics
GET /api/stable-matches/stats
```
