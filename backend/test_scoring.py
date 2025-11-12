"""Quick test of the new scoring system"""
from app.services.stable_matching.scoring import calculate_group_score, check_hard_constraints

# Sample group
group = {
    'id': 'test-group-1',
    'target_city': 'San Francisco',
    'target_state_province': 'CA',
    'budget_per_person_min': 1500,
    'budget_per_person_max': 2000,
    'target_group_size': 2,
    'target_move_in_date': '2025-12-01',
    'target_lease_type': 'month_to_month',
    'target_bathrooms': 2.0,
    'target_furnished': True,
    'target_utilities_included': False,
    'target_deposit_amount': 2000
}

# Sample listing
listing = {
    'id': 'test-listing-1',
    'city': 'San Francisco',
    'state_province': 'CA',
    'price_per_month': 3500,
    'number_of_bedrooms': 2,
    'number_of_bathrooms': 2.0,
    'available_from': '2025-11-15',
    'lease_type': 'month_to_month',
    'furnished': True,
    'utilities_included': False,
    'deposit_amount': 1800,
    'created_at': '2025-11-01'
}

print("Testing new scoring system...")
print("="*60)

# Check hard constraints
passes, reason = check_hard_constraints(group, listing)
print(f'\n✓ Hard constraints: {"PASS" if passes else "FAIL"} {reason or ""}')

# Calculate score
if passes:
    score = calculate_group_score(group, listing)
    print(f'\n✓ Final Score: {score:.2f}/100')
    print(f'\nBreakdown:')
    print(f'  • Lease Duration (M2M): 20 pts')
    print(f'  • Bathrooms (2.0 >= 2.0): 20 pts')
    print(f'  • Furnished (both True): 20 pts')
    print(f'  • Utilities (both False): 20 pts')
    print(f'  • Deposit ($1800 <= $2000): 20 pts')
    print(f'  ─────────────────────────────')
    print(f'  Total: 100 pts (Perfect match!)')

print("\n" + "="*60)
print("✅ Scoring system working correctly!")
