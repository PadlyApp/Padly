"""
Stable Matching - Phase 3: Two-Sided Scoring
Calculates scores and rankings for both groups and listings.
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
import math


# =============================================================================
# Configuration - Scoring Weights
# =============================================================================

# Group → Listing scoring weights (total should be ~1.0)
GROUP_SCORING_WEIGHTS = {
    'price_fit': 0.30,        # How well price fits budget
    'date_fit': 0.25,         # How close move-in dates are
    'amenities_fit': 0.25,    # How well amenities match
    'listing_quality': 0.20,  # Listing freshness and completeness
}

# Listing → Group scoring weights (total should be ~1.0)
LISTING_SCORING_WEIGHTS = {
    'verification_trust': 0.35,  # How verified the group members are
    'group_readiness': 0.30,     # Is group full and active
    'date_alignment': 0.20,      # Date compatibility
    'house_rules_fit': 0.15,     # Future: rules compatibility
}

# Amenity importance weights (for amenities_fit calculation)
AMENITY_WEIGHTS = {
    'wifi': 20,
    'laundry': 20,
    'furnished': 20,
    'air_conditioning': 15,
    'parking': 15,
    'dishwasher': 10,
}


# =============================================================================
# 3.1 Group → Listing Score (S_g(l))
# =============================================================================

def calculate_price_fit_score(
    listing_price: float,
    budget_min: float,
    budget_max: float
) -> float:
    """
    Calculate how well the listing price fits the group's budget.
    Score is highest when price is near the midpoint of budget range.
    
    Args:
        listing_price: Price per month for the listing
        budget_min: Group's minimum budget per person
        budget_max: Group's maximum budget per person
        
    Returns:
        Score from 0-100
    """
    # Calculate per-person price (for 2-person group)
    per_person_price = listing_price / 2
    
    # If price is outside budget range, score is 0
    if per_person_price < budget_min or per_person_price > budget_max:
        return 0.0
    
    # Calculate budget midpoint
    budget_midpoint = (budget_min + budget_max) / 2
    budget_range = budget_max - budget_min
    
    # Calculate distance from midpoint as percentage of range
    if budget_range > 0:
        distance_pct = abs(per_person_price - budget_midpoint) / (budget_range / 2)
    else:
        distance_pct = 0.0
    
    # Score is higher when closer to midpoint (inverse of distance)
    # Max score of 100 at midpoint, min score of 50 at edges
    score = 100 - (distance_pct * 50)
    
    return max(0, min(100, score))


def calculate_date_fit_score(
    listing_available_from: date,
    listing_available_to: Optional[date],
    group_target_date: date
) -> float:
    """
    Calculate how well the listing's availability matches the group's target date.
    
    Args:
        listing_available_from: When listing becomes available
        listing_available_to: When listing availability ends (None = open-ended)
        group_target_date: Group's target move-in date
        
    Returns:
        Score from 0-100
    """
    # Convert strings to dates if needed
    if isinstance(listing_available_from, str):
        listing_available_from = datetime.fromisoformat(listing_available_from.replace('Z', '+00:00')).date()
    if isinstance(listing_available_to, str):
        listing_available_to = datetime.fromisoformat(listing_available_to.replace('Z', '+00:00')).date()
    if isinstance(group_target_date, str):
        group_target_date = datetime.fromisoformat(group_target_date.replace('Z', '+00:00')).date()
    
    # Calculate days difference
    days_diff = abs((group_target_date - listing_available_from).days)
    
    # Bonus if within ±7 days
    if days_diff <= 7:
        return 100.0
    
    # Score decreases with distance
    # 100 at 0 days, ~75 at 14 days, ~50 at 30 days, ~25 at 60 days
    score = max(0, 100 - (days_diff / 60 * 75))
    
    return score


def calculate_amenities_fit_score(
    listing_amenities: Dict[str, Any],
    group_preferences: Optional[Dict[str, Any]] = None
) -> float:
    """
    Calculate how well listing amenities match group preferences.
    
    Args:
        listing_amenities: Dictionary of listing amenities
        group_preferences: Group's target preferences (optional)
        
    Returns:
        Score from 0-100
    """
    if not listing_amenities:
        return 50.0  # Neutral score if no amenity data
    
    total_weight = sum(AMENITY_WEIGHTS.values())
    score = 0
    
    # Score each amenity
    for amenity, weight in AMENITY_WEIGHTS.items():
        # Check if listing has this amenity
        has_amenity = False
        
        if amenity == 'laundry':
            # Special handling for laundry (can be "in_unit", "on_site", "none", or boolean)
            laundry = listing_amenities.get('laundry', False)
            has_amenity = laundry and laundry != 'none'
        elif amenity == 'furnished':
            # This might be top-level or in amenities
            has_amenity = listing_amenities.get('furnished', False)
        else:
            # Standard boolean amenity
            has_amenity = listing_amenities.get(amenity, False) is True
        
        # Add weighted score
        if has_amenity:
            score += weight
    
    # Convert to 0-100 scale
    return (score / total_weight) * 100


def calculate_listing_quality_score(
    listing: Dict[str, Any]
) -> float:
    """
    Calculate listing quality score based on freshness and completeness.
    
    Args:
        listing: Full listing dictionary
        
    Returns:
        Score from 0-100
    """
    score = 0
    
    # Freshness score (40 points max)
    created_at = listing.get('created_at')
    if created_at:
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                created_at = datetime.now()
        
        days_old = (datetime.now(created_at.tzinfo) - created_at).days
        
        # Newer is better: 40 pts if <30 days, 30 pts if <90 days, 20 pts if <180 days
        if days_old < 30:
            score += 40
        elif days_old < 90:
            score += 30
        elif days_old < 180:
            score += 20
        else:
            score += 10
    else:
        score += 20  # Neutral if no date
    
    # Completeness score (60 points max)
    completeness_points = 0
    
    # Has description (15 pts)
    if listing.get('description'):
        completeness_points += 15
    
    # Has amenities data (15 pts)
    if listing.get('amenities'):
        completeness_points += 15
    
    # Has house rules (10 pts)
    if listing.get('house_rules'):
        completeness_points += 10
    
    # Has photos (future - 10 pts)
    # For now, give partial credit if listing looks complete
    completeness_points += 5
    
    # Has address details (10 pts)
    if listing.get('address_line_1') and listing.get('postal_code'):
        completeness_points += 10
    
    # Has coordinates (5 pts)
    if listing.get('latitude') and listing.get('longitude'):
        completeness_points += 5
    
    score += completeness_points
    
    return min(100, score)


def calculate_group_score(
    group: Dict[str, Any],
    listing: Dict[str, Any]
) -> float:
    """
    Calculate overall score for this (group, listing) pair from group's perspective.
    
    Args:
        group: Group dictionary
        listing: Listing dictionary
        
    Returns:
        Weighted score from 0-1000
    """
    # Calculate component scores (each 0-100)
    price_score = calculate_price_fit_score(
        listing.get('price_per_month', 0),
        group.get('budget_per_person_min', 0),
        group.get('budget_per_person_max', 0)
    )
    
    date_score = calculate_date_fit_score(
        listing.get('available_from'),
        listing.get('available_to'),
        group.get('target_move_in_date')
    )
    
    amenities_score = calculate_amenities_fit_score(
        listing.get('amenities', {}),
        group.get('target_preferences', {})
    )
    
    quality_score = calculate_listing_quality_score(listing)
    
    # Apply weights and sum (scale to 0-1000)
    total_score = (
        price_score * GROUP_SCORING_WEIGHTS['price_fit'] +
        date_score * GROUP_SCORING_WEIGHTS['date_fit'] +
        amenities_score * GROUP_SCORING_WEIGHTS['amenities_fit'] +
        quality_score * GROUP_SCORING_WEIGHTS['listing_quality']
    ) * 10  # Scale to 0-1000
    
    return total_score


# =============================================================================
# 3.2 Listing → Group Score (S_l(g))
# =============================================================================

def calculate_verification_trust_score(
    group_members: List[Dict[str, Any]],
    users_data: Optional[Dict[str, Dict[str, Any]]] = None
) -> float:
    """
    Calculate trust score based on member verification.
    
    Args:
        group_members: List of group member dictionaries
        users_data: Optional dictionary of user_id -> user data
        
    Returns:
        Score from 0-100
    """
    if not group_members:
        return 0.0
    
    verified_count = 0
    total_count = len(group_members)
    
    for member in group_members:
        user_id = member.get('user_id')
        
        # Check if we have user data
        if users_data and user_id in users_data:
            user = users_data[user_id]
            verification_status = user.get('verification_status', 'unverified')
            
            if verification_status == 'verified':
                verified_count += 1
        # If no user data, assume unverified
    
    # Calculate percentage
    if total_count > 0:
        verification_rate = verified_count / total_count
        return verification_rate * 100
    
    return 0.0


def calculate_group_readiness_score(
    group: Dict[str, Any]
) -> float:
    """
    Calculate readiness score based on group completeness and status.
    
    Args:
        group: Group dictionary with members
        
    Returns:
        Score from 0-100
    """
    score = 0
    
    # Check if group is active (50 points)
    if group.get('status', '').lower() == 'active':
        score += 50
    
    # Check if group is full (50 points)
    current_size = len(group.get('members', []))
    target_size = group.get('target_group_size', 2)
    
    if current_size >= target_size:
        score += 50
    else:
        # Partial credit based on how close to full
        score += (current_size / target_size) * 50
    
    return score


def calculate_date_alignment_score(
    listing_available_from: date,
    group_target_date: date
) -> float:
    """
    Calculate date alignment from listing's perspective.
    (Same as date_fit but from host's view)
    
    Args:
        listing_available_from: When listing becomes available
        group_target_date: Group's target move-in date
        
    Returns:
        Score from 0-100
    """
    return calculate_date_fit_score(listing_available_from, None, group_target_date)


def calculate_house_rules_fit_score(
    listing: Dict[str, Any],
    group: Dict[str, Any]
) -> float:
    """
    Calculate how well group fits listing's house rules (future implementation).
    
    Args:
        listing: Listing dictionary
        group: Group dictionary
        
    Returns:
        Score from 0-100 (currently returns neutral 50)
    """
    # Future: Parse house_rules and match with group preferences
    # For now, return neutral score
    return 50.0


def calculate_listing_score(
    listing: Dict[str, Any],
    group: Dict[str, Any],
    users_data: Optional[Dict[str, Dict[str, Any]]] = None
) -> float:
    """
    Calculate overall score for this (listing, group) pair from listing's perspective.
    
    Args:
        listing: Listing dictionary
        group: Group dictionary
        users_data: Optional dictionary of user data for verification checks
        
    Returns:
        Weighted score from 0-1000
    """
    # Calculate component scores (each 0-100)
    verification_score = calculate_verification_trust_score(
        group.get('members', []),
        users_data
    )
    
    readiness_score = calculate_group_readiness_score(group)
    
    date_score = calculate_date_alignment_score(
        listing.get('available_from'),
        group.get('target_move_in_date')
    )
    
    rules_score = calculate_house_rules_fit_score(listing, group)
    
    # Apply weights and sum (scale to 0-1000)
    total_score = (
        verification_score * LISTING_SCORING_WEIGHTS['verification_trust'] +
        readiness_score * LISTING_SCORING_WEIGHTS['group_readiness'] +
        date_score * LISTING_SCORING_WEIGHTS['date_alignment'] +
        rules_score * LISTING_SCORING_WEIGHTS['house_rules_fit']
    ) * 10  # Scale to 0-1000
    
    return total_score


# =============================================================================
# 3.3 Ranking & Tie-Breaking
# =============================================================================

def rank_listings_for_group(
    group: Dict[str, Any],
    feasible_listings: List[Dict[str, Any]]
) -> List[Tuple[str, int, float]]:
    """
    Rank all feasible listings for this group and assign ranks.
    
    Args:
        group: Group dictionary
        feasible_listings: List of listings that passed hard constraints
        
    Returns:
        List of (listing_id, rank, score) tuples, sorted by rank (1 = best)
    """
    # Calculate scores for all listings
    scored_listings = []
    for listing in feasible_listings:
        score = calculate_group_score(group, listing)
        scored_listings.append({
            'listing_id': listing['id'],
            'score': score,
            'created_at': listing.get('created_at', ''),
            'price': listing.get('price_per_month', 0)
        })
    
    # Sort by score (descending), then by tie-breaks
    # Note: created_at is ISO string, so reverse=True for newest first
    scored_listings.sort(
        key=lambda x: (
            x['score'],                     # For reverse=True, lower values come first, so we keep positive
            x['created_at'],                # Older dates (earlier strings) with reverse=True = newer first
            x['price'],                     # Lower price first
            x['listing_id']                 # UUID as final tie-break
        ),
        reverse=True                        # Reverse to get highest score first
    )
    
    # Assign ranks
    ranked = []
    for rank, item in enumerate(scored_listings, start=1):
        ranked.append((item['listing_id'], rank, item['score']))
    
    return ranked


def rank_groups_for_listing(
    listing: Dict[str, Any],
    feasible_groups: List[Dict[str, Any]],
    users_data: Optional[Dict[str, Dict[str, Any]]] = None
) -> List[Tuple[str, int, float]]:
    """
    Rank all feasible groups for this listing and assign ranks.
    
    Args:
        listing: Listing dictionary
        feasible_groups: List of groups that passed hard constraints
        users_data: Optional dictionary of user data for verification
        
    Returns:
        List of (group_id, rank, score) tuples, sorted by rank (1 = best)
    """
    # Calculate scores for all groups
    scored_groups = []
    for group in feasible_groups:
        score = calculate_listing_score(listing, group, users_data)
        
        # Calculate verification rate for tie-break
        members = group.get('members', [])
        verified_count = 0
        if users_data:
            for member in members:
                user_id = member.get('user_id')
                if user_id in users_data:
                    if users_data[user_id].get('verification_status') == 'verified':
                        verified_count += 1
        
        verification_rate = verified_count / len(members) if members else 0
        
        scored_groups.append({
            'group_id': group['id'],
            'score': score,
            'verification_rate': verification_rate,
            'target_date': group.get('target_move_in_date', ''),
        })
    
    # Sort by score (descending), then by tie-breaks
    scored_groups.sort(
        key=lambda x: (
            x['score'],                      # For reverse=True, this gets highest first
            x['verification_rate'],          # Higher verification first
            x['target_date'],                # Earlier date (earlier string) first with normal comparison
            x['group_id']                    # UUID as final tie-break
        ),
        reverse=True                         # Reverse to get highest score and verification first
    )
    
    # Assign ranks
    ranked = []
    for rank, item in enumerate(scored_groups, start=1):
        ranked.append((item['group_id'], rank, item['score']))
    
    return ranked


# =============================================================================
# 3.4 Build Preference Lists
# =============================================================================

def build_preference_lists(
    feasible_pairs: List[Tuple[str, str]],
    groups: List[Dict[str, Any]],
    listings: List[Dict[str, Any]],
    users_data: Optional[Dict[str, Dict[str, Any]]] = None
) -> Tuple[Dict[str, List[Tuple[str, int, float]]], Dict[str, List[Tuple[str, int, float]]]]:
    """
    Build preference lists for all groups and listings.
    
    Args:
        feasible_pairs: List of (group_id, listing_id) tuples that passed hard constraints
        groups: List of all eligible groups
        listings: List of all eligible listings
        users_data: Optional dictionary of user data
        
    Returns:
        Tuple of (group_preferences, listing_preferences)
        - group_preferences: Dict[group_id] = [(listing_id, rank, score), ...]
        - listing_preferences: Dict[listing_id] = [(group_id, rank, score), ...]
    """
    # Create lookup dictionaries
    groups_dict = {g['id']: g for g in groups}
    listings_dict = {l['id']: l for l in listings}
    
    # Build adjacency lists
    group_to_listings = {}  # group_id -> [listing_id, ...]
    listing_to_groups = {}  # listing_id -> [group_id, ...]
    
    for group_id, listing_id in feasible_pairs:
        if group_id not in group_to_listings:
            group_to_listings[group_id] = []
        group_to_listings[group_id].append(listing_id)
        
        if listing_id not in listing_to_groups:
            listing_to_groups[listing_id] = []
        listing_to_groups[listing_id].append(group_id)
    
    # Build preference lists for each group
    group_preferences = {}
    for group in groups:
        group_id = group['id']
        feasible_listing_ids = group_to_listings.get(group_id, [])
        feasible_listing_objs = [listings_dict[lid] for lid in feasible_listing_ids if lid in listings_dict]
        
        if feasible_listing_objs:
            group_preferences[group_id] = rank_listings_for_group(group, feasible_listing_objs)
        else:
            group_preferences[group_id] = []
    
    # Build preference lists for each listing
    listing_preferences = {}
    for listing in listings:
        listing_id = listing['id']
        feasible_group_ids = listing_to_groups.get(listing_id, [])
        feasible_group_objs = [groups_dict[gid] for gid in feasible_group_ids if gid in groups_dict]
        
        if feasible_group_objs:
            listing_preferences[listing_id] = rank_groups_for_listing(listing, feasible_group_objs, users_data)
        else:
            listing_preferences[listing_id] = []
    
    return group_preferences, listing_preferences
