"""
Stable Matching - Phase 3: Scoring & Preference Lists

This module calculates compatibility scores between groups and listings
based on hard constraints and soft preferences.

Scoring Scheme v3.0:
- Hard Constraints: Binary (must all pass)
  * City match
  * State match
  * Budget range
  * Bedroom count (≥ group size)
  * Move-in date (±60 days)
  * Lease type match
  * Lease duration match (exact)
  
- Soft Preferences: 100 points total (5 categories × 20 points each)
  * Bathroom count match (20 pts)
  * Furnished preference match (20 pts)
  * Utilities included preference match (20 pts)
  * Deposit amount within range (20 pts)
  * House rules compatibility (20 pts)

Author: Padly Matching Team
Version: 3.0.0
"""

from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Scoring Weights
# =============================================================================

GROUP_SCORING_WEIGHTS = {
    'bathrooms': 20,
    'furnished': 20,
    'utilities': 20,
    'deposit': 20,
    'house_rules': 20
}

LISTING_SCORING_WEIGHTS = {
    'bathrooms': 20,
    'furnished': 20,
    'utilities': 20,
    'deposit': 20,
    'house_rules': 20
}

MAX_SCORE = 100


# =============================================================================
# Hard Constraints
# =============================================================================

def check_hard_constraints(
    group: Dict[str, Any],
    listing: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Check if group and listing satisfy all hard constraints.
    
    Args:
        group: Group data dictionary
        listing: Listing data dictionary
        
    Returns:
        Tuple of (passes, rejection_reason)
        - (True, None) if all constraints pass
        - (False, reason_string) if any constraint fails
    """
    # 1. City Match (case-insensitive)
    group_city = (group.get('target_city') or '').strip().lower()
    listing_city = (listing.get('city') or '').strip().lower()
    if group_city != listing_city:
        return False, f"city_mismatch_{group_city}_vs_{listing_city}"
    
    # 2. State Match (case-insensitive)
    group_state = (group.get('target_state_province') or '').strip().lower()
    listing_state = (listing.get('state_province') or '').strip().lower()
    if group_state != listing_state:
        return False, f"state_mismatch_{group_state}_vs_{listing_state}"
    
    # 3. Budget Range
    group_size = group.get('target_group_size', 2)
    min_budget = group.get('budget_per_person_min', 0)
    max_budget = group.get('budget_per_person_max', 0)
    listing_price = listing.get('price_per_month', 0)
    
    min_total = min_budget * group_size
    max_total = (max_budget * group_size) + 100  # $100 buffer
    
    if not (min_total <= listing_price <= max_total):
        return False, f"budget_mismatch_${listing_price}_not_in_[${min_total},${max_total}]"
    
    # 4. Bedroom Count
    listing_bedrooms = listing.get('number_of_bedrooms', 0)
    if listing_bedrooms < group_size:
        return False, f"insufficient_bedrooms_{listing_bedrooms}_<_{group_size}"
    
    # 5. Move-in Date (±60 days)
    group_date = group.get('target_move_in_date')
    listing_date = listing.get('available_from')
    
    if group_date and listing_date:
        # Convert to date objects if they're strings
        if isinstance(group_date, str):
            group_date = datetime.fromisoformat(group_date.replace('Z', '+00:00')).date()
        if isinstance(listing_date, str):
            listing_date = datetime.fromisoformat(listing_date.replace('Z', '+00:00')).date()
        
        date_diff = abs((listing_date - group_date).days)
        if date_diff > 60:
            return False, f"date_mismatch_{date_diff}_days_apart"
    
    # 6. Lease Type Match
    group_lease_type = (group.get('target_lease_type') or '').strip().lower()
    listing_lease_type = (listing.get('lease_type') or '').strip().lower()
    
    if group_lease_type and listing_lease_type:
        if group_lease_type != listing_lease_type:
            return False, f"lease_type_mismatch_{group_lease_type}_vs_{listing_lease_type}"
    
    # 7. Lease Duration Match (Exact)
    group_duration = group.get('target_lease_duration_months')
    listing_duration = listing.get('lease_duration_months')
    
    if group_duration is not None and listing_duration is not None:
        if group_duration != listing_duration:
            return False, f"lease_duration_mismatch_{group_duration}_vs_{listing_duration}_months"
    
    return True, None


# =============================================================================
# Soft Preferences - Individual Scoring Functions
# =============================================================================

def calculate_bathroom_score(
    group: Dict[str, Any],
    listing: Dict[str, Any]
) -> float:
    """
    Score: 20 points max
    - Meets or exceeds target: 20
    - Within 0.5 of target: 10
    - Below target: 5
    """
    target_bathrooms = group.get('target_bathrooms', 1.0)
    listing_bathrooms = listing.get('number_of_bathrooms', 1.0)
    
    # Convert to float for comparison
    if isinstance(target_bathrooms, (int, str)):
        target_bathrooms = float(target_bathrooms)
    if isinstance(listing_bathrooms, (int, str)):
        listing_bathrooms = float(listing_bathrooms)
    
    # Meets or exceeds target
    if listing_bathrooms >= target_bathrooms:
        return 20.0
    
    # Within 0.5 of target
    if listing_bathrooms >= target_bathrooms - 0.5:
        return 10.0
    
    # Below target
    return 5.0


def calculate_furnished_score(
    group: Dict[str, Any],
    listing: Dict[str, Any]
) -> float:
    """
    Score: 20 points max
    - Matches preference: 20
    - Doesn't match: 10
    """
    group_prefers_furnished = group.get('target_furnished', False)
    listing_is_furnished = listing.get('furnished', False)
    
    # Convert to boolean
    if isinstance(group_prefers_furnished, str):
        group_prefers_furnished = group_prefers_furnished.lower() in ['true', 't', '1', 'yes']
    if isinstance(listing_is_furnished, str):
        listing_is_furnished = listing_is_furnished.lower() in ['true', 't', '1', 'yes']
    
    # Preferences match
    if group_prefers_furnished == listing_is_furnished:
        return 20.0
    
    # Preferences don't match
    return 10.0


def calculate_utilities_score(
    group: Dict[str, Any],
    listing: Dict[str, Any]
) -> float:
    """
    Score: 20 points max
    - Matches preference: 20
    - Doesn't match: 10
    """
    group_prefers_utilities = group.get('target_utilities_included', False)
    listing_has_utilities = listing.get('utilities_included', False)
    
    # Convert to boolean
    if isinstance(group_prefers_utilities, str):
        group_prefers_utilities = group_prefers_utilities.lower() in ['true', 't', '1', 'yes']
    if isinstance(listing_has_utilities, str):
        listing_has_utilities = listing_has_utilities.lower() in ['true', 't', '1', 'yes']
    
    # Preferences match
    if group_prefers_utilities == listing_has_utilities:
        return 20.0
    
    # Preferences don't match
    return 10.0


def calculate_deposit_score(
    group: Dict[str, Any],
    listing: Dict[str, Any]
) -> float:
    """
    Score: 20 points max
    - listing_deposit ≤ target_deposit: 20
    - target_deposit < listing_deposit ≤ target_deposit + 500: 10
    - target_deposit + 500 < listing_deposit ≤ target_deposit + 1500: 5
    - listing_deposit > target_deposit + 1500: 0
    """
    target_deposit = group.get('target_deposit_amount', 0)
    listing_deposit = listing.get('deposit_amount', 0)
    
    # Convert to float for comparison
    if target_deposit is None:
        target_deposit = 0
    if listing_deposit is None:
        listing_deposit = 0
    
    target_deposit = float(target_deposit)
    listing_deposit = float(listing_deposit)
    
    # Listing deposit is at or below target
    if listing_deposit <= target_deposit:
        return 20.0
    
    # Listing deposit is $0-$500 over target
    if listing_deposit <= target_deposit + 500:
        return 10.0
    
    # Listing deposit is $500-$1500 over target
    if listing_deposit <= target_deposit + 1500:
        return 5.0
    
    # Listing deposit is more than $1500 over target
    return 0.0


def calculate_house_rules_score(
    group: Dict[str, Any],
    listing: Dict[str, Any]
) -> float:
    """
    Score: 20 points max
    Compare house rules compatibility between group and listing.
    - Perfect match (all rules compatible): 20
    - Good match (1-2 conflicts): 10
    - Poor match (3+ conflicts): 0
    """
    group_rules = group.get('target_house_rules', '')
    listing_rules = listing.get('house_rules', '')
    
    # If either is empty/None, give neutral score
    if not group_rules or not listing_rules:
        return 10.0
    
    # Convert to lowercase for comparison
    group_rules_lower = group_rules.lower()
    listing_rules_lower = listing_rules.lower()
    
    # Check for common rule keywords and conflicts
    conflicts = 0
    
    # Smoking conflict
    if 'no smoking' in listing_rules_lower and 'smoking' in group_rules_lower and 'no smoking' not in group_rules_lower:
        conflicts += 1
    
    # Pet conflict
    if 'no pets' in listing_rules_lower and 'pet' in group_rules_lower and 'no pet' not in group_rules_lower:
        conflicts += 1
    
    # Party/guests conflict
    if 'no parties' in listing_rules_lower and 'parties' in group_rules_lower and 'no parties' not in group_rules_lower:
        conflicts += 1
    
    # If rules are very similar (high text overlap), likely compatible
    if group_rules_lower == listing_rules_lower:
        return 20.0
    
    # Score based on conflicts
    if conflicts == 0:
        return 20.0
    elif conflicts <= 2:
        return 10.0
    else:
        return 0.0


# =============================================================================
# Overall Scoring Functions
# =============================================================================

def calculate_group_score(
    group: Dict[str, Any],
    listing: Dict[str, Any]
) -> float:
    """
    Calculate how much a group likes a listing (0-100 points).
    
    This represents the group's preference for this listing based on
    how well it matches their target criteria.
    
    Args:
        group: Group data dictionary
        listing: Listing data dictionary
        
    Returns:
        Score from 0-100 (higher is better)
    """
    # Check hard constraints first
    passes, reason = check_hard_constraints(group, listing)
    if not passes:
        logger.debug(f"Group {group.get('id')} rejected listing {listing.get('id')}: {reason}")
        return 0.0
    
    # Calculate soft preference scores (5 categories × 20 points = 100 max)
    score = 0.0
    
    score += calculate_bathroom_score(group, listing)
    score += calculate_furnished_score(group, listing)
    score += calculate_utilities_score(group, listing)
    score += calculate_deposit_score(group, listing)
    score += calculate_house_rules_score(group, listing)
    
    # Ensure score is within bounds
    score = max(0.0, min(MAX_SCORE, score))
    
    logger.debug(f"Group {group.get('id')} scores listing {listing.get('id')}: {score:.2f}/100")
    return score


def calculate_listing_score(
    listing: Dict[str, Any],
    group: Dict[str, Any]
) -> float:
    """
    Calculate how much a listing likes a group (0-100 points).
    
    Listings prefer groups with:
    - Higher budgets (willing to pay more = 40 points)
    - Larger security deposits (more protection = 30 points)  
    - Matching preferences (furnished, utilities, etc. = 30 points)
    
    Args:
        listing: Listing data dictionary
        group: Group data dictionary
        
    Returns:
        Score from 0-100 (higher is better)
    """
    score = 0.0
    
    # 1. Budget Score (40 points) - Prefer groups with higher budgets
    listing_price = listing.get('price_per_month', 0)
    group_budget = group.get('budget_per_person_max', 0) * group.get('target_group_size', 2)
    
    if listing_price > 0 and group_budget > 0:
        # Calculate budget ratio (how much over asking price)
        budget_ratio = group_budget / listing_price
        
        if budget_ratio >= 1.5:  # 50%+ over asking
            score += 40
        elif budget_ratio >= 1.3:  # 30-50% over
            score += 35
        elif budget_ratio >= 1.15:  # 15-30% over
            score += 30
        elif budget_ratio >= 1.05:  # 5-15% over
            score += 25
        elif budget_ratio >= 1.0:  # Exactly at or slightly over asking
            score += 20
        elif budget_ratio >= 0.95:  # Within 5% of asking
            score += 15
        else:  # Less than 95% (shouldn't happen due to hard constraints)
            score += 5
    
    # 2. Security Deposit Score (30 points) - Prefer groups willing to pay higher deposits
    listing_deposit = listing.get('deposit_amount', 0)
    group_target_deposit = group.get('target_deposit_amount', 0)
    
    if listing_deposit and group_target_deposit:
        deposit_ratio = group_target_deposit / listing_deposit
        
        if deposit_ratio >= 1.5:  # Willing to pay 50%+ more
            score += 30
        elif deposit_ratio >= 1.2:  # 20-50% more
            score += 25
        elif deposit_ratio >= 1.0:  # At or above asking
            score += 20
        elif deposit_ratio >= 0.8:  # 80-100% of asking
            score += 15
        else:  # Less than 80%
            score += 10
    elif not listing_deposit:  # Listing has no deposit requirement
        score += 20  # Neutral score
    
    # 3. Preference Match Score (30 points) - Groups that want what listing offers
    pref_score = 0.0
    pref_count = 0
    
    # Furnished match (10 points)
    listing_furnished = listing.get('furnished', False)
    group_wants_furnished = group.get('target_furnished', None)
    if group_wants_furnished is not None:
        if listing_furnished == group_wants_furnished:
            pref_score += 10
        pref_count += 1
    
    # Utilities match (10 points)
    listing_utilities = listing.get('utilities_included', False)
    group_wants_utilities = group.get('target_utilities_included', None)
    if group_wants_utilities is not None:
        if listing_utilities == group_wants_utilities:
            pref_score += 10
        pref_count += 1
    
    # House rules compatibility (10 points)
    listing_rules = listing.get('house_rules', {})
    group_rules = group.get('target_house_rules', {})
    
    if isinstance(listing_rules, dict) and isinstance(group_rules, dict):
        conflicts = 0
        rules_to_check = ['smoking_allowed', 'pets_allowed', 'parties_allowed']
        
        for rule in rules_to_check:
            listing_allows = listing_rules.get(rule, True)
            group_wants = group_rules.get(rule, False)
            
            # Conflict: group wants something listing doesn't allow
            if group_wants and not listing_allows:
                conflicts += 1
        
        # Perfect match = 10, each conflict = -3.33
        pref_score += max(0, 10 - (conflicts * 3.33))
        pref_count += 1
    
    # Add preference score (max 30 points)
    score += pref_score
    
    logger.debug(f"Listing {listing.get('id', 'unknown')} scores group {group.get('id', 'unknown')}: "
                f"budget={budget_ratio:.2f}x, deposit={deposit_ratio:.2f}x, total={score:.1f}")
    
    return round(score, 1)


# =============================================================================
# Ranking & Preference Lists
# =============================================================================

def rank_listings_for_group(
    group: Dict[str, Any],
    feasible_listings: List[Dict[str, Any]]
) -> List[Tuple[str, int, float]]:
    """
    Rank all feasible listings for a group.
    
    Args:
        group: Group data dictionary
        feasible_listings: List of listings that passed hard constraints
        
    Returns:
        List of tuples: (listing_id, rank, score)
        Sorted by score descending (rank 1 = best)
    """
    # Score each listing
    scored_listings = []
    for listing in feasible_listings:
        score = calculate_group_score(group, listing)
        if score > 0:  # Only include if score is positive
            scored_listings.append({
                'listing_id': listing['id'],
                'score': score,
                'created_at': listing.get('created_at', ''),
                'price': listing.get('price_per_month', 0)
            })
    
    # Sort by: score (desc), created_at (desc), price (asc), id (alpha)
    scored_listings.sort(
        key=lambda x: (-x['score'], -ord(x['created_at'][0]) if x['created_at'] else 0, x['price'], x['listing_id'])
    )
    
    # Assign ranks
    ranked_listings = []
    for rank, item in enumerate(scored_listings, start=1):
        ranked_listings.append((item['listing_id'], rank, item['score']))
    
    logger.info(f"Group {group.get('id')} ranked {len(ranked_listings)} listings")
    return ranked_listings


def rank_groups_for_listing(
    listing: Dict[str, Any],
    feasible_groups: List[Dict[str, Any]]
) -> List[Tuple[str, int, float]]:
    """
    Rank all feasible groups for a listing.
    
    Args:
        listing: Listing data dictionary
        feasible_groups: List of groups that passed hard constraints
        
    Returns:
        List of tuples: (group_id, rank, score)
        Sorted by score descending (rank 1 = best)
    """
    # Score each group
    scored_groups = []
    for group in feasible_groups:
        score = calculate_listing_score(listing, group)
        if score > 0:  # Only include if score is positive
            scored_groups.append({
                'group_id': group['id'],
                'score': score,
                'created_at': group.get('created_at', '')
            })
    
    # Sort by: score (desc), created_at (desc), id (alpha)
    scored_groups.sort(
        key=lambda x: (-x['score'], -ord(x['created_at'][0]) if x['created_at'] else 0, x['group_id'])
    )
    
    # Assign ranks
    ranked_groups = []
    for rank, item in enumerate(scored_groups, start=1):
        ranked_groups.append((item['group_id'], rank, item['score']))
    
    logger.info(f"Listing {listing.get('id')} ranked {len(ranked_groups)} groups")
    return ranked_groups


def build_preference_lists(
    feasible_pairs: List[Tuple[str, str]],
    groups: List[Dict[str, Any]],
    listings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Build preference lists for all groups and listings.
    
    Args:
        feasible_pairs: List of (group_id, listing_id) tuples that passed hard constraints
        groups: List of all eligible group dictionaries
        listings: List of all eligible listing dictionaries
        
    Returns:
        Dictionary with:
        - 'group_preferences': Dict[group_id, List[(listing_id, rank, score)]]
        - 'listing_preferences': Dict[listing_id, List[(group_id, rank, score)]]
        - 'metadata': Dict with statistics
    """
    logger.info(f"Building preference lists from {len(feasible_pairs)} feasible pairs...")
    
    # Build lookup dictionaries
    groups_dict = {g['id']: g for g in groups}
    listings_dict = {l['id']: l for l in listings}
    
    # Build compatibility map
    group_compatible_listings = {}
    listing_compatible_groups = {}
    
    for group_id, listing_id in feasible_pairs:
        if group_id not in group_compatible_listings:
            group_compatible_listings[group_id] = []
        group_compatible_listings[group_id].append(listing_id)
        
        if listing_id not in listing_compatible_groups:
            listing_compatible_groups[listing_id] = []
        listing_compatible_groups[listing_id].append(group_id)
    
    # Build group preferences
    group_preferences = {}
    for group_id in group_compatible_listings.keys():
        group = groups_dict.get(group_id)
        if not group:
            continue
            
        # Get all listings this group is compatible with
        compatible_listing_ids = group_compatible_listings[group_id]
        compatible_listings = [listings_dict[lid] for lid in compatible_listing_ids if lid in listings_dict]
        
        # Rank them
        ranked = rank_listings_for_group(group, compatible_listings)
        group_preferences[group_id] = ranked
    
    # Build listing preferences
    listing_preferences = {}
    for listing_id in listing_compatible_groups.keys():
        listing = listings_dict.get(listing_id)
        if not listing:
            continue
            
        # Get all groups this listing is compatible with
        compatible_group_ids = listing_compatible_groups[listing_id]
        compatible_groups = [groups_dict[gid] for gid in compatible_group_ids if gid in groups_dict]
        
        # Rank them
        ranked = rank_groups_for_listing(listing, compatible_groups)
        listing_preferences[listing_id] = ranked
    
    metadata = {
        'total_groups': len(group_preferences),
        'total_listings': len(listing_preferences),
        'feasible_pairs': len(feasible_pairs),
        'avg_listings_per_group': len(feasible_pairs) / len(group_preferences) if group_preferences else 0,
        'avg_groups_per_listing': len(feasible_pairs) / len(listing_preferences) if listing_preferences else 0
    }
    
    logger.info(f"Built preferences for {len(group_preferences)} groups and {len(listing_preferences)} listings")
    logger.info(f"Avg listings per group: {metadata['avg_listings_per_group']:.2f}")
    logger.info(f"Avg groups per listing: {metadata['avg_groups_per_listing']:.2f}")
    
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
