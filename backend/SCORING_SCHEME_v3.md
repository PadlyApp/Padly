## Hard Constraints (Must ALL Pass)

All hard constraints must be satisfied for a match to be considered. If any constraint fails, the pair receives a score of 0.

| Constraint | Rule |
|-----------|------|
| **City** | Exact match (case-insensitive) |
| **State** | Exact match (case-insensitive) |
| **Budget** | `min_budget × group_size ≤ listing_price ≤ (max_budget × group_size) + $100` |
| **Bedrooms** | `listing_bedrooms ≥ group_size` |
| **Move-in Date** | Within ±60 days |
| **Lease Type** | Exact match (e.g., fixed_term, month_to_month, open_ended) |
| **Lease Duration** | **EXACT MATCH** (e.g., both must be 12 months, or both 6 months) |

## Soft Preferences (100 Points Total)

Once hard constraints pass, compatibility is scored across 5 categories (20 points each):

### 1. Bathroom Count Match (20 points)
- **20 pts**: Listing has ≥ target bathrooms
- **10 pts**: Listing has ≥ target - 0.5 bathrooms
- **5 pts**: Below target by more than 0.5

### 2. Furnished Preference Match (20 points)
- **20 pts**: Listing matches group's furnished preference exactly
- **10 pts**: Listing doesn't match preference (neutral)

### 3. Utilities Included Preference Match (20 points)
- **20 pts**: Listing matches group's utilities preference exactly
- **10 pts**: Listing doesn't match preference (neutral)

### 4. Deposit Amount Within Range (20 points)
- **20 pts**: Listing deposit ≤ target deposit
- **10 pts**: Listing deposit ≤ target + $500
- **5 pts**: Listing deposit ≤ target + $1,500
- **0 pts**: Listing deposit > target + $1,500

### 5. House Rules Compatibility (20 points)
- **20 pts**: Perfect match (no conflicts, or identical rules)
- **10 pts**: Good match (1-2 conflicts, or missing rules on one side)
- **0 pts**: Poor match (3+ conflicts)

Common rule conflicts checked:
- Smoking (no smoking vs smoking allowed)
- Pets (no pets vs pets allowed)
- Parties (no parties vs parties allowed)

## Final Score Calculation

```
Group Score = Bathrooms (20) + Furnished (20) + Utilities (20) + Deposit (20) + House Rules (20)
Maximum Score = 100 points
```

## Listing Scoring (Asymmetric Preferences)

Listings evaluate groups differently (100 points total):

### 1. Budget Affordability (40 points)
Listings prefer groups with higher budgets:
- **40 pts**: Group budget ≥ 150% of asking price
- **35 pts**: Group budget ≥ 130% of asking price
- **30 pts**: Group budget ≥ 115% of asking price
- **25 pts**: Group budget ≥ 105% of asking price
- **20 pts**: Group budget ≥ 100% of asking price
- **15 pts**: Group budget ≥ 95% of asking price
- **5 pts**: Below 95% (rare due to hard constraints)

### 2. Security Deposit (30 points)
Listings prefer groups willing to pay higher deposits:
- **30 pts**: Group willing to pay ≥ 150% of listing deposit
- **25 pts**: Group willing to pay ≥ 120% of listing deposit
- **20 pts**: Group willing to pay ≥ 100% of listing deposit
- **15 pts**: Group willing to pay ≥ 80% of listing deposit
- **10 pts**: Below 80%

### 3. Preference Match (30 points)
Groups that want what the listing offers:
- **10 pts**: Furnished preference matches
- **10 pts**: Utilities preference matches
- **10 pts**: No house rules conflicts (same logic as group scoring)

````
