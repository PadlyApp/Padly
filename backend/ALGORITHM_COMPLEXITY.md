# Stable Matching Algorithm - Complexity

## Time Complexity

**Worst Case:** **O(n² log n)**
- n = number of groups (or listings)
- Dominated by sorting preference lists

**Average Case:** **O(n² log n)**
- Same as worst case
- Sorting still required even with filtering

**Practical Case:** **O(n)**
- Hard constraints filter ~99% of pairs
- Each group has ~3-10 feasible options
- Effective complexity reduces to linear

## Space Complexity

**Worst Case:** **O(n²)**
- Storing all feasible pairs
- Full preference lists for all groups/listings

**Average Case:** **O(n)**
- With strict constraints (city, exact lease duration, budget, dates)
- Only ~3-10 feasible pairs per group stored

## Phase-by-Phase Runtime

| Phase | Operation | Complexity | File & Lines |
|-------|-----------|------------|--------------|
| 1. Hard Constraints | Check all n×m pairs | O(n²) | `feasible_pairs.py` lines 238-290 |
| 2. Scoring | Score each feasible pair | O(n²) | `scoring.py` lines 308-459 |
| 3. **Sorting Preferences** | **n groups sort m listings each** | **O(n² log n)** ⬅ bottleneck | `scoring.py` lines 389-461 |
| 4. Deferred Acceptance | n groups propose ≤ m times | O(n²) | `deferred_acceptance.py` lines 157-208 |
| 5. Stability Check | Check all potential blocking pairs | O(n²) | `deferred_acceptance.py` lines 384-430 |

**Total: O(n² log n)** - sorting dominates

**Phase 3 Details:**
- `rank_listings_for_group()`: lines 389-421 - sorts m listings for each group
- `rank_groups_for_listing()`: lines 424-461 - sorts n groups for each listing

## Gale-Shapley Properties

- Always terminates
- Always produces stable matching
- At most n² proposals
- Each operation is O(1) with dict lookups

## Real Example

Oakland: 4 groups, 12 listings
- Theoretical worst: 4 × 12 = 48 comparisons
- Actual feasible: 12 pairs (75% filtered)
- Proposals: 5
- Time: <0.01s
