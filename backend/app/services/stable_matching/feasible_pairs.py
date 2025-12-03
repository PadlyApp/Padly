"""
Stable Matching - Phase 2: Feasible Pair Building
Builds pairs of (group, listing) that satisfy all hard constraints.
"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
from .scoring import check_hard_constraints


# =============================================================================
# 2.1 Location Matching
# =============================================================================

def location_matches(group: Dict, listing: Dict) -> bool:
    """
    Check if group and listing are in compatible locations.
    
    Args:
        group: Group data with target_city, target_state_province, target_country
        listing: Listing data with city, state_province, country
        
    Returns:
        True if locations match, False otherwise
    """
    # Normalize city names (lowercase, strip whitespace)
    group_city = str(group.get('target_city', '')).lower().strip()
    listing_city = str(listing.get('city', '')).lower().strip()
    
    if not group_city or not listing_city:
        return False
    
    # Primary check: city must match
    if group_city != listing_city:
        return False
    
    # Secondary check: country (if specified)
    group_country = str(group.get('target_country', 'USA')).lower().strip()
    listing_country = str(listing.get('country', 'USA')).lower().strip()
    
    if group_country != listing_country:
        return False
    
    # Optional tertiary check: state/province
    # Only enforce if both are specified
    group_state = str(group.get('target_state_province', '')).lower().strip()
    listing_state = str(listing.get('state_province', '')).lower().strip()
    
    if group_state and listing_state and group_state != listing_state:
        return False
    
    return True


# =============================================================================
# 2.2 Date Matching
# =============================================================================

def parse_date(date_value) -> Optional[date]:
    """
    Parse various date formats into date object.
    
    Args:
        date_value: Can be date, datetime, string (ISO format), or None
        
    Returns:
        date object or None
    """
    if date_value is None:
        return None
    
    if isinstance(date_value, date):
        return date_value
    
    if isinstance(date_value, datetime):
        return date_value.date()
    
    if isinstance(date_value, str):
        try:
            # Try ISO format: YYYY-MM-DD
            return datetime.fromisoformat(date_value.replace('Z', '+00:00')).date()
        except (ValueError, AttributeError):
            return None
    
    return None


def date_matches(
    group: Dict,
    listing: Dict,
    delta_days: int = 30
) -> bool:
    """
    Check if group's target move-in date is compatible with listing availability.
    
    Args:
        group: Group data with target_move_in_date
        listing: Listing data with available_from, available_to (optional)
        delta_days: Flexibility window (default ±30 days)
        
    Returns:
        True if dates are compatible, False otherwise
    """
    target_date = parse_date(group.get('target_move_in_date'))
    available_from = parse_date(listing.get('available_from'))
    available_to = parse_date(listing.get('available_to'))
    
    if not target_date or not available_from:
        return False
    
    # Calculate acceptable window for group
    earliest_acceptable = target_date - timedelta(days=delta_days)
    latest_acceptable = target_date + timedelta(days=delta_days)
    
    # Check if available_from is within acceptable window
    if available_from < earliest_acceptable:
        # Listing available too early (might not wait)
        return False
    
    # If listing has an available_to date, check it
    if available_to:
        # Listing must be available through at least the earliest acceptable date
        if available_to < earliest_acceptable:
            return False
        
        # Also check that available_from is before latest_acceptable
        if available_from > latest_acceptable:
            return False
    else:
        # No end date means available indefinitely
        # Just check that available_from is not too late
        if available_from > latest_acceptable:
            return False
    
    return True


# =============================================================================
# 2.3 Price Matching
# =============================================================================

def price_matches(group: Dict, listing: Dict) -> bool:
    """
    Check if listing price is within group's per-person budget.
    
    Args:
        group: Group data with budget_per_person_min, budget_per_person_max
        listing: Listing data with price_per_month
        
    Returns:
        True if price is affordable, False otherwise
    """
    listing_price = listing.get('price_per_month')
    budget_min = group.get('budget_per_person_min')
    budget_max = group.get('budget_per_person_max')
    
    # Validate all required fields present
    if listing_price is None or budget_min is None or budget_max is None:
        return False
    
    # Convert to float for comparison
    try:
        listing_price = float(listing_price)
        budget_min = float(budget_min)
        budget_max = float(budget_max)
    except (ValueError, TypeError):
        return False
    
    # Calculate per-person price (2-person groups)
    per_person_price = listing_price / 2
    
    # Add $100 buffer to budget max for flexibility
    BUDGET_BUFFER = 100.0
    budget_max_with_buffer = budget_max + BUDGET_BUFFER
    
    # Check if within budget range (with buffer on max)
    return budget_min <= per_person_price <= budget_max_with_buffer


# =============================================================================
# 2.4 Hard Attributes Matching
# =============================================================================

def hard_attributes_match(group: Dict, listing: Dict) -> bool:
    """
    Check if listing meets group's non-negotiable attribute requirements.
    
    Hard requirements (if group specifies them as required):
    - Furnished
    - Utilities included
    - Specific amenities (pets, parking, etc.)
    
    Args:
        group: Group data with target_* preferences
        listing: Listing data with amenities
        
    Returns:
        True if all hard requirements met, False otherwise
    """
    # Check furnished requirement
    if group.get('target_furnished') is True:
        if listing.get('furnished') is not True:
            return False
    
    # Check utilities included requirement
    if group.get('target_utilities_included') is True:
        if listing.get('utilities_included') is not True:
            return False
    
    # Check amenity requirements
    # Note: Currently treating these as preferences, not hard requirements
    # Future: Could add group.required_amenities list
    
    # Pets allowed (if group needs it)
    if group.get('needs_pets_allowed') is True:
        if listing.get('pets_allowed') is not True:
            return False
    
    # Parking (if group needs it)
    if group.get('needs_parking') is True:
        if listing.get('parking') is not True:
            return False
    
    # Air conditioning (if group needs it)
    if group.get('needs_air_conditioning') is True:
        if listing.get('air_conditioning') is not True:
            return False
    
    # All hard requirements met
    return True


# =============================================================================
# 2.5 Feasible Pairs Builder
# =============================================================================

def build_feasible_pairs(
    groups: List[Dict],
    listings: List[Dict],
    date_delta_days: int = 30,
    include_rejection_reasons: bool = False
) -> Tuple[List[Tuple[str, str]], Optional[Dict]]:
    """
    Build list of feasible (group_id, listing_id) pairs that pass all hard constraints.
    
    Args:
        groups: List of eligible group dictionaries
        listings: List of eligible listing dictionaries
        date_delta_days: Flexibility for date matching (default ±30 days)
        include_rejection_reasons: If True, return rejection reasons for diagnostics
        
    Returns:
        Tuple of:
        - List of (group_id, listing_id) feasible pairs
        - Dict of rejection reasons (if include_rejection_reasons=True), else None
    """
    feasible_pairs = []
    rejection_reasons = {} if include_rejection_reasons else None
    
    for group in groups:
        group_id = group.get('id')
        if not group_id:
            continue
        
        group_rejections = [] if include_rejection_reasons else None
        
        for listing in listings:
            listing_id = listing.get('id')
            if not listing_id:
                continue
            
            # Check all hard constraints using the unified scoring function
            passes, rejection_reason = check_hard_constraints(group, listing)
            
            # If all constraints passed, add to feasible pairs
            if passes:
                feasible_pairs.append((group_id, listing_id))
            elif include_rejection_reasons:
                group_rejections.append({
                    'listing_id': listing_id,
                    'reasons': [rejection_reason]
                })
        
        # Store rejection reasons for this group
        if include_rejection_reasons and group_rejections:
            rejection_reasons[group_id] = group_rejections
    
    return feasible_pairs, rejection_reasons


# =============================================================================
# 2.6 Statistics & Diagnostics
# =============================================================================

def get_feasibility_statistics(
    groups: List[Dict],
    listings: List[Dict],
    feasible_pairs: List[Tuple[str, str]]
) -> Dict:
    """
    Calculate statistics about feasibility rates.
    
    Args:
        groups: List of eligible groups
        listings: List of eligible listings
        feasible_pairs: List of feasible pairs
        
    Returns:
        Dict with statistics
    """
    total_groups = len(groups)
    total_listings = len(listings)
    total_pairs = len(feasible_pairs)
    
    # Count unique groups and listings in feasible pairs
    groups_with_options = len(set(g_id for g_id, _ in feasible_pairs))
    listings_with_options = len(set(l_id for _, l_id in feasible_pairs))
    
    # Calculate average options per entity
    avg_listings_per_group = total_pairs / total_groups if total_groups > 0 else 0
    avg_groups_per_listing = total_pairs / total_listings if total_listings > 0 else 0
    
    return {
        'total_groups': total_groups,
        'total_listings': total_listings,
        'total_feasible_pairs': total_pairs,
        'groups_with_options': groups_with_options,
        'groups_with_no_options': total_groups - groups_with_options,
        'listings_with_options': listings_with_options,
        'listings_with_no_options': total_listings - listings_with_options,
        'avg_listings_per_group': round(avg_listings_per_group, 2),
        'avg_groups_per_listing': round(avg_groups_per_listing, 2),
        'feasibility_rate': round(total_pairs / (total_groups * total_listings) * 100, 2) if total_groups * total_listings > 0 else 0
    }


def analyze_rejection_reasons(rejection_reasons: Dict) -> Dict:
    """
    Analyze rejection reasons to identify common bottlenecks.
    
    Args:
        rejection_reasons: Dict from build_feasible_pairs with rejection data
        
    Returns:
        Dict with counts of each rejection reason
    """
    reason_counts = {
        'location_mismatch': 0,
        'date_incompatible': 0,
        'price_unaffordable': 0,
        'required_attributes_missing': 0
    }
    
    total_rejections = 0
    
    for group_id, rejections in rejection_reasons.items():
        for rejection in rejections:
            total_rejections += 1
            for reason in rejection['reasons']:
                if reason in reason_counts:
                    reason_counts[reason] += 1
    
    # Calculate percentages
    reason_percentages = {}
    if total_rejections > 0:
        for reason, count in reason_counts.items():
            reason_percentages[reason] = round(count / total_rejections * 100, 2)
    
    return {
        'total_rejections': total_rejections,
        'reason_counts': reason_counts,
        'reason_percentages': reason_percentages
    }
