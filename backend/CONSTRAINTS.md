# Padly Matching Constraints

## Hard Constraints (Must ALL Pass)

If any hard constraint fails, the group-listing pair is **rejected** (score = 0).

| Constraint | Rule | Tolerance |
|-----------|------|-----------|
| **City** | `group.target_city == listing.city` | Case-insensitive |
| **State** | `group.target_state_province == listing.state_province` | Case-insensitive |
| **Budget** | `min_budget × group_size ≤ listing_price ≤ (max_budget × group_size) + $100` | $100 buffer |
| **Bedrooms** | `listing.bedrooms ≥ group_size` | None |
| **Move-in Date** | `|group.target_date - listing.available_from| ≤ 60 days` | ±60 days |
| **Lease Type** | `group.lease_type == listing.lease_type` | Only if both set |
| **Lease Duration** | `group.duration == listing.duration` (exact) | Only if both set |

---

## Soft Preferences (100 Points)

Once hard constraints pass, pairs are **scored and ranked**.

### Group → Listing (How much group likes listing)

| Category | Points | Scoring |
|----------|--------|---------|
| Bathrooms | 20 | ≥ target: 20 \| within 0.5: 10 \| below: 5 |
| Furnished | 20 | Match: 20 \| No match: 10 |
| Utilities | 20 | Match: 20 \| No match: 10 |
| Deposit | 20 | ≤ target: 20 \| +$500: 10 \| +$1500: 5 \| >+$1500: 0 |
| House Rules | 20 | 0 conflicts: 20 \| 1-2: 10 \| 3+: 0 |

### Listing → Group (How much listing prefers group)

| Category | Points | Scoring |
|----------|--------|---------|
| Budget | 40 | ≥150% asking: 40 \| ≥130%: 35 \| ≥115%: 30 \| ≥105%: 25 \| ≥100%: 20 |
| Deposit | 30 | ≥150%: 30 \| ≥120%: 25 \| ≥100%: 20 \| ≥80%: 15 |
| Preferences | 30 | Furnished: 10 \| Utilities: 10 \| Rules: 10 |

---

## Required Fields

### Group (`roommate_groups`)
- `target_city` ✅
- `target_state_province`
- `budget_per_person_min` ✅
- `budget_per_person_max` ✅
- `target_group_size` ✅
- `target_move_in_date` ✅
- `target_lease_type`
- `target_lease_duration_months`
- `target_bathrooms`
- `target_furnished`
- `target_utilities_included`
- `target_deposit_amount`
- `target_house_rules`

### Listing (`listings`)
- `city` ✅
- `state_province`
- `price_per_month` ✅
- `number_of_bedrooms` ✅
- `available_from` ✅
- `lease_type`
- `lease_duration_months`
- `number_of_bathrooms`
- `furnished`
- `utilities_included`
- `deposit_amount`
- `house_rules`

✅ = Required for hard constraint matching
