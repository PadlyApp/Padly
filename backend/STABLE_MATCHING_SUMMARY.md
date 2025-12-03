# Stable Matching Algorithm - Quick Reference

## Algorithm
**Gale-Shapley Deferred Acceptance** (groups-proposing)

## Complexity
- **Time:** O(n² log n) worst case, O(n) practical
- **Space:** O(n²) worst case, O(n) practical

## How It Works
1. **Filter:** Check 7 hard constraints (city, budget, lease duration, etc.)
2. **Score:** Rate each feasible pair on 5 soft preferences (bathrooms, furnished, utilities, deposit, house rules)
3. **Match:** Groups propose to listings in preference order, listings accept best offer
4. **Verify:** Ensure no blocking pairs exist

## Features
✅ Guaranteed stable matching (no blocking pairs)  
✅ Group-optimal (best outcome for groups)  
✅ Asymmetric preferences (groups & listings score differently)  
✅ Handles competition (rank #2, #3, etc.)

## Scoring

### Groups Score Listings (0-100)
- Bathrooms: 20 pts
- Furnished match: 20 pts
- Utilities match: 20 pts
- Deposit in range: 20 pts
- House rules compatible: 20 pts

### Listings Score Groups (0-100)
- Budget (higher = better): 40 pts
- Security deposit (higher = better): 30 pts
- Preference match: 30 pts

## Performance
- 10-50 groups: <0.1s
- 100-500 groups: <1s
- 1,000-5,000 groups: 1-10s

## Real-World Example
**Oakland:** 4 groups, 12 listings
- 12 feasible pairs (75% filtered by hard constraints)
- 5 proposals, 1 rejection
- 4 stable matches (including 1 rank #2)
- Execution: 5 iterations

## Files
- `deferred_acceptance.py` - Core algorithm
- `scoring.py` - Scoring functions
- `feasible_pairs.py` - Hard constraint filtering
- `run_matching.py` - Execute for all cities
- `SCORING_SCHEME_v3.md` - Detailed scoring rules
- `COMPLEXITY_ANALYSIS.md` - Full complexity breakdown
