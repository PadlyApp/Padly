"""
Stable Matching - Feasible Pair Building
Builds (group, listing) pairs that satisfy hard constraints.
"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime, date, timedelta
from app.services.location_matching import locations_match
from .scoring import check_hard_constraints


# --- LOCATION MATCHING ---

def location_matches(group: Dict, listing: Dict) -> bool:
    """Check if group and listing locations are compatible."""
    return locations_match(
        target_city=group.get("target_city"),
        listing_city=listing.get("city"),
        target_state=group.get("target_state_province"),
        listing_state=listing.get("state_province"),
        target_country=group.get("target_country", "USA"),
        listing_country=listing.get("country", "USA"),
    )


# --- DATE MATCHING ---

def parse_date(date_value) -> Optional[date]:
    """Parse various date formats into date object."""
    if date_value is None:
        return None
    if isinstance(date_value, date):
        return date_value
    if isinstance(date_value, datetime):
        return date_value.date()
    if isinstance(date_value, str):
        try:
            return datetime.fromisoformat(date_value.replace('Z', '+00:00')).date()
        except (ValueError, AttributeError):
            return None
    return None


def date_matches(group: Dict, listing: Dict, delta_days: int = 30) -> bool:
    """Check if group's move-in date is compatible with listing availability (±delta_days)."""
    target_date = parse_date(group.get('target_move_in_date'))
    available_from = parse_date(listing.get('available_from'))
    available_to = parse_date(listing.get('available_to'))
    
    if not target_date or not available_from:
        return False
    
    earliest = target_date - timedelta(days=delta_days)
    latest = target_date + timedelta(days=delta_days)
    
    if available_from < earliest:
        return False
    
    if available_to:
        if available_to < earliest or available_from > latest:
            return False
    elif available_from > latest:
        return False
    
    return True


# --- PRICE MATCHING ---

def price_matches(group: Dict, listing: Dict) -> bool:
    """Check if listing price is within group's per-person budget (+$100 buffer)."""
    listing_price = listing.get('price_per_month')
    budget_min = group.get('budget_per_person_min')
    budget_max = group.get('budget_per_person_max')
    
    if listing_price is None or budget_min is None or budget_max is None:
        return False
    
    try:
        listing_price = float(listing_price)
        budget_min = float(budget_min)
        budget_max = float(budget_max)
    except (ValueError, TypeError):
        return False
    
    per_person = listing_price / 2
    return budget_min <= per_person <= (budget_max + 100.0)


# --- HARD ATTRIBUTES ---

def hard_attributes_match(group: Dict, listing: Dict) -> bool:
    """Check non-negotiable requirements (furnished required, pets, parking, AC)."""
    # Furnished is hard only when explicitly marked as hard requirement.
    if (group.get('furnished_is_hard') or (group.get('furnished_preference') == 'required')) and group.get('target_furnished') is True:
        if listing.get('furnished') is not True:
            return False

    checks = [
        ('needs_pets_allowed', 'pets_allowed'),
        ('needs_parking', 'parking'),
        ('needs_air_conditioning', 'air_conditioning'),
    ]

    for group_key, listing_key in checks:
        if group.get(group_key) is True and listing.get(listing_key) is not True:
            return False
    return True


# --- FEASIBLE PAIRS BUILDER ---

def build_feasible_pairs(
    groups: List[Dict],
    listings: List[Dict],
    date_delta_days: int = 30,
    include_rejection_reasons: bool = False
) -> Tuple[List[Tuple[str, str]], Optional[Dict]]:
    """Build list of feasible (group_id, listing_id) pairs that pass all hard constraints."""
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
            
            passes, reason = check_hard_constraints(group, listing)
            
            if passes:
                feasible_pairs.append((group_id, listing_id))
            elif include_rejection_reasons:
                group_rejections.append({'listing_id': listing_id, 'reasons': [reason]})
        
        if include_rejection_reasons and group_rejections:
            rejection_reasons[group_id] = group_rejections
    
    return feasible_pairs, rejection_reasons


# --- STATISTICS ---

def get_feasibility_statistics(
    groups: List[Dict],
    listings: List[Dict],
    feasible_pairs: List[Tuple[str, str]]
) -> Dict:
    """Calculate statistics about feasibility rates."""
    total_groups = len(groups)
    total_listings = len(listings)
    total_pairs = len(feasible_pairs)
    
    groups_with_options = len(set(g_id for g_id, _ in feasible_pairs))
    listings_with_options = len(set(l_id for _, l_id in feasible_pairs))
    
    return {
        'total_groups': total_groups,
        'total_listings': total_listings,
        'total_feasible_pairs': total_pairs,
        'groups_with_options': groups_with_options,
        'groups_with_no_options': total_groups - groups_with_options,
        'listings_with_options': listings_with_options,
        'listings_with_no_options': total_listings - listings_with_options,
        'avg_listings_per_group': round(total_pairs / total_groups, 2) if total_groups else 0,
        'avg_groups_per_listing': round(total_pairs / total_listings, 2) if total_listings else 0,
        'feasibility_rate': round(total_pairs / (total_groups * total_listings) * 100, 2) if total_groups * total_listings else 0
    }


def analyze_rejection_reasons(rejection_reasons: Dict) -> Dict:
    """Analyze rejection reasons to identify bottlenecks."""
    reason_counts = {
        'location_mismatch': 0,
        'date_incompatible': 0,
        'price_unaffordable': 0,
        'required_attributes_missing': 0
    }
    
    total = 0
    for group_id, rejections in rejection_reasons.items():
        for rejection in rejections:
            total += 1
            for reason in rejection['reasons']:
                if reason in reason_counts:
                    reason_counts[reason] += 1
    
    percentages = {r: round(c / total * 100, 2) for r, c in reason_counts.items()} if total else {}
    
    return {
        'total_rejections': total,
        'reason_counts': reason_counts,
        'reason_percentages': percentages
    }
