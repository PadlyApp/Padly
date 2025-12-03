"""
Scoring & Preference Lists for Group↔Listing matching.
Hard constraints: city, state, budget, bedrooms, date (±60d), lease type/duration.
Soft preferences: bathrooms(20), furnished(20), utilities(20), deposit(20), house_rules(20).
"""

from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)

# Weights (100 pts total)
GROUP_SCORING_WEIGHTS = {'bathrooms': 20, 'furnished': 20, 'utilities': 20, 'deposit': 20, 'house_rules': 20}
LISTING_SCORING_WEIGHTS = {'bathrooms': 20, 'furnished': 20, 'utilities': 20, 'deposit': 20, 'house_rules': 20}
MAX_SCORE = 100

# --- HARD CONSTRAINTS ---

def check_hard_constraints(group: Dict, listing: Dict) -> Tuple[bool, Optional[str]]:
    """Check all hard constraints. Returns (passes, rejection_reason)."""
    
    # City match
    group_city = (group.get('target_city') or '').strip().lower()
    listing_city = (listing.get('city') or '').strip().lower()
    if group_city != listing_city:
        return False, f"city_mismatch_{group_city}_vs_{listing_city}"
    
    # State match (if both specified)
    group_state = (group.get('target_state_province') or '').strip().lower()
    listing_state = (listing.get('state_province') or '').strip().lower()
    if group_state and listing_state and group_state != listing_state:
        return False, f"state_mismatch_{group_state}_vs_{listing_state}"
    
    # Budget range
    group_size = group.get('target_group_size', 2)
    min_budget = group.get('budget_per_person_min', 0)
    max_budget = group.get('budget_per_person_max', 0)
    listing_price = listing.get('price_per_month', 0)
    min_total = min_budget * group_size
    max_total = (max_budget * group_size) + 100
    
    if not (min_total <= listing_price <= max_total):
        return False, f"budget_mismatch_${listing_price}_not_in_[${min_total},${max_total}]"
    
    # Bedroom count
    if listing.get('number_of_bedrooms', 0) < group_size:
        return False, f"insufficient_bedrooms"
    
    # Move-in date (±60 days)
    group_date = group.get('target_move_in_date')
    listing_date = listing.get('available_from')
    if group_date and listing_date:
        if isinstance(group_date, str):
            group_date = datetime.fromisoformat(group_date.replace('Z', '+00:00')).date()
        if isinstance(listing_date, str):
            listing_date = datetime.fromisoformat(listing_date.replace('Z', '+00:00')).date()
        if abs((listing_date - group_date).days) > 60:
            return False, f"date_mismatch"
    
    # Lease type/duration (if specified)
    group_lease_type = (group.get('target_lease_type') or '').strip().lower()
    listing_lease_type = (listing.get('lease_type') or '').strip().lower()
    if group_lease_type and listing_lease_type and group_lease_type != listing_lease_type:
        return False, f"lease_type_mismatch"
    
    group_duration = group.get('target_lease_duration_months')
    listing_duration = listing.get('lease_duration_months')
    if group_duration is not None and listing_duration is not None and group_duration != listing_duration:
        return False, f"lease_duration_mismatch"
    
    return True, None


# --- SOFT PREFERENCE SCORING (20 pts each) ---

def calculate_bathroom_score(group: Dict, listing: Dict) -> float:
    """Bathroom match: meets/exceeds=20, within 0.5=10, else=5."""
    target = float(group.get('target_bathrooms', 1.0))
    actual = float(listing.get('number_of_bathrooms', 1.0))
    if actual >= target:
        return 20.0
    if actual >= target - 0.5:
        return 10.0
    return 5.0


def calculate_furnished_score(group: Dict, listing: Dict) -> float:
    """Furnished match: same=20, different=10."""
    group_pref = group.get('target_furnished', False)
    listing_val = listing.get('furnished', False)
    if isinstance(group_pref, str):
        group_pref = group_pref.lower() in ['true', 't', '1', 'yes']
    if isinstance(listing_val, str):
        listing_val = listing_val.lower() in ['true', 't', '1', 'yes']
    return 20.0 if group_pref == listing_val else 10.0


def calculate_utilities_score(group: Dict, listing: Dict) -> float:
    """Utilities match: same=20, different=10."""
    group_pref = group.get('target_utilities_included', False)
    listing_val = listing.get('utilities_included', False)
    if isinstance(group_pref, str):
        group_pref = group_pref.lower() in ['true', 't', '1', 'yes']
    if isinstance(listing_val, str):
        listing_val = listing_val.lower() in ['true', 't', '1', 'yes']
    return 20.0 if group_pref == listing_val else 10.0


def calculate_deposit_score(group: Dict, listing: Dict) -> float:
    """Deposit: at/below=20, +$500=10, +$1500=5, else=0."""
    target = float(group.get('target_deposit_amount') or 0)
    actual = float(listing.get('deposit_amount') or 0)
    if actual <= target:
        return 20.0
    if actual <= target + 500:
        return 10.0
    if actual <= target + 1500:
        return 5.0
    return 0.0


def calculate_house_rules_score(group: Dict, listing: Dict) -> float:
    """House rules: no conflicts=20, 1-2 conflicts=10, 3+ conflicts=0."""
    group_rules = (group.get('target_house_rules') or '').lower()
    listing_rules = (listing.get('house_rules') or '').lower()
    
    if not group_rules or not listing_rules:
        return 10.0
    if group_rules == listing_rules:
        return 20.0
    
    conflicts = 0
    if 'no smoking' in listing_rules and 'smoking' in group_rules and 'no smoking' not in group_rules:
        conflicts += 1
    if 'no pets' in listing_rules and 'pet' in group_rules and 'no pet' not in group_rules:
        conflicts += 1
    if 'no parties' in listing_rules and 'parties' in group_rules and 'no parties' not in group_rules:
        conflicts += 1
    
    if conflicts == 0:
        return 20.0
    if conflicts <= 2:
        return 10.0
    return 0.0


# --- OVERALL SCORING ---

def calculate_group_score(group: Dict[str, Any], listing: Dict[str, Any]) -> float:
    """Calculate how much a group likes a listing (0-100)."""
    # Check hard constraints first
    passes, reason = check_hard_constraints(group, listing)
    if not passes:
        logger.debug(f"Group {group.get('id')} rejected listing {listing.get('id')}: {reason}")
        return 0.0
    
    # Calculate soft preference scores (5 categories × 20 points = 100 max)
    score = (
        calculate_bathroom_score(group, listing) +
        calculate_furnished_score(group, listing) +
        calculate_utilities_score(group, listing) +
        calculate_deposit_score(group, listing) +
        calculate_house_rules_score(group, listing)
    )
    
    score = max(0.0, min(MAX_SCORE, score))
    logger.debug(f"Group {group.get('id')} scores listing {listing.get('id')}: {score:.2f}/100")
    return score


def calculate_listing_score(listing: Dict[str, Any], group: Dict[str, Any]) -> float:
    """Calculate how much a listing likes a group (0-100)."""
    score = 0.0
    
    # Budget score (40 pts) - prefer groups with higher budgets
    listing_price = listing.get('price_per_month', 0)
    group_budget = group.get('budget_per_person_max', 0) * group.get('target_group_size', 2)
    budget_ratio = group_budget / listing_price if listing_price > 0 and group_budget > 0 else 1.0
    
    if budget_ratio >= 1.5: score += 40
    elif budget_ratio >= 1.3: score += 35
    elif budget_ratio >= 1.15: score += 30
    elif budget_ratio >= 1.05: score += 25
    elif budget_ratio >= 1.0: score += 20
    elif budget_ratio >= 0.95: score += 15
    else: score += 5
    
    # Deposit score (30 pts) - prefer groups willing to pay higher deposits
    listing_deposit = listing.get('deposit_amount', 0)
    group_deposit = group.get('target_deposit_amount', 0)
    deposit_ratio = 1.0
    
    if listing_deposit and group_deposit:
        deposit_ratio = group_deposit / listing_deposit
        if deposit_ratio >= 1.5: score += 30
        elif deposit_ratio >= 1.2: score += 25
        elif deposit_ratio >= 1.0: score += 20
        elif deposit_ratio >= 0.8: score += 15
        else: score += 10
    else:
        score += 20 if not listing_deposit else 15
    
    # Preference match (30 pts) - groups that want what listing offers
    if group.get('target_furnished') is not None:
        if listing.get('furnished') == group.get('target_furnished'):
            score += 10
    
    if group.get('target_utilities_included') is not None:
        if listing.get('utilities_included') == group.get('target_utilities_included'):
            score += 10
    
    # House rules compatibility (10 pts)
    listing_rules = listing.get('house_rules', {})
    group_rules = group.get('target_house_rules', {})
    if isinstance(listing_rules, dict) and isinstance(group_rules, dict):
        conflicts = sum(1 for rule in ['smoking_allowed', 'pets_allowed', 'parties_allowed']
                       if group_rules.get(rule) and not listing_rules.get(rule, True))
        score += max(0, 10 - (conflicts * 3.33))
    
    logger.debug(f"Listing {listing.get('id')} scores group {group.get('id')}: {score:.1f}")
    return round(score, 1)


# --- RANKING & PREFERENCE LISTS ---

def rank_listings_for_group(group: Dict[str, Any], feasible_listings: List[Dict[str, Any]]) -> List[Tuple[str, int, float]]:
    """Rank all feasible listings for a group. Returns [(listing_id, rank, score)]."""
    scored = []
    for listing in feasible_listings:
        score = calculate_group_score(group, listing)
        if score > 0:
            created_at = listing.get('created_at', '')
            if hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            scored.append({
                'listing_id': listing['id'],
                'score': score,
                'created_at': created_at or '',
                'price': listing.get('price_per_month', 0)
            })
    
    # Sort by: score desc, created_at desc, price asc
    scored.sort(key=lambda x: (-x['score'], -hash(x['created_at']) if x['created_at'] else 0, x['price']))
    
    ranked = [(item['listing_id'], rank, item['score']) for rank, item in enumerate(scored, start=1)]
    logger.info(f"Group {group.get('id')} ranked {len(ranked)} listings")
    return ranked


def rank_groups_for_listing(listing: Dict[str, Any], feasible_groups: List[Dict[str, Any]]) -> List[Tuple[str, int, float]]:
    """Rank all feasible groups for a listing. Returns [(group_id, rank, score)]."""
    scored = []
    for group in feasible_groups:
        score = calculate_listing_score(listing, group)
        if score > 0:
            created_at = group.get('created_at', '')
            if hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            scored.append({
                'group_id': group['id'],
                'score': score,
                'created_at': created_at or ''
            })
    
    # Sort by: score desc, created_at desc
    scored.sort(key=lambda x: (-x['score'], -hash(x['created_at']) if x['created_at'] else 0, x['group_id']))
    
    ranked = [(item['group_id'], rank, item['score']) for rank, item in enumerate(scored, start=1)]
    logger.info(f"Listing {listing.get('id')} ranked {len(ranked)} groups")
    return ranked


def build_preference_lists(
    feasible_pairs: List[Tuple[str, str]],
    groups: List[Dict[str, Any]],
    listings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Build preference lists for all groups and listings from feasible pairs."""
    logger.info(f"Building preference lists from {len(feasible_pairs)} feasible pairs...")
    
    groups_dict = {g['id']: g for g in groups}
    listings_dict = {l['id']: l for l in listings}
    
    # Build compatibility maps
    group_listings = {}  # group_id -> [listing_ids]
    listing_groups = {}  # listing_id -> [group_ids]
    
    for group_id, listing_id in feasible_pairs:
        group_listings.setdefault(group_id, []).append(listing_id)
        listing_groups.setdefault(listing_id, []).append(group_id)
    
    # Build group preferences
    group_preferences = {}
    for group_id, listing_ids in group_listings.items():
        group = groups_dict.get(group_id)
        if group:
            compatible = [listings_dict[lid] for lid in listing_ids if lid in listings_dict]
            group_preferences[group_id] = rank_listings_for_group(group, compatible)
    
    # Build listing preferences
    listing_preferences = {}
    for listing_id, group_ids in listing_groups.items():
        listing = listings_dict.get(listing_id)
        if listing:
            compatible = [groups_dict[gid] for gid in group_ids if gid in groups_dict]
            listing_preferences[listing_id] = rank_groups_for_listing(listing, compatible)
    
    metadata = {
        'total_groups': len(group_preferences),
        'total_listings': len(listing_preferences),
        'feasible_pairs': len(feasible_pairs),
        'avg_listings_per_group': len(feasible_pairs) / len(group_preferences) if group_preferences else 0,
        'avg_groups_per_listing': len(feasible_pairs) / len(listing_preferences) if listing_preferences else 0
    }
    
    logger.info(f"Built preferences for {len(group_preferences)} groups, {len(listing_preferences)} listings")
    
    return {
        'group_preferences': group_preferences,
        'listing_preferences': listing_preferences,
        'metadata': metadata
    }


# Export public API
__all__ = [
    'check_hard_constraints',
    'calculate_group_score',
    'calculate_listing_score',
    'rank_listings_for_group',
    'rank_groups_for_listing',
    'build_preference_lists',
    'GROUP_SCORING_WEIGHTS',
    'LISTING_SCORING_WEIGHTS',
    'MAX_SCORE'
]
