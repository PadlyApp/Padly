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

## Why O(n² log n)?

1. **Hard Constraints:** O(n²) - check all group-listing pairs
2. **Scoring:** O(n²) - score each feasible pair
3. **Sorting Preferences:** **O(n² log n)** ← bottleneck
4. **Deferred Acceptance:** O(n²) - each group proposes ≤ n times
5. **Stability Check:** O(n²) - verify no blocking pairs

**Sorting dominates:** Each of n groups sorts their m listings = O(n × m log m) = O(n² log n)

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
