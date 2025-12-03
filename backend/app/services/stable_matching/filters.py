"""
Stable Matching - Phase 1: Data Filtering & Eligibility
Filters listings and groups for stable matching algorithm.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import re


# =============================================================================
# 1.1 Listing Eligibility Filters
# =============================================================================

def is_listing_pair_eligible(listing: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Check if a listing is eligible for pair (2-person group) matching.
    
    Args:
        listing: Parsed listing dictionary
        
    Returns:
        Tuple of (is_eligible, rejection_reason)
        - (True, None) if eligible
        - (False, reason_string) if not eligible
    """
    # Check property type - must be entire place, not private room
    property_type = listing.get('property_type', '').lower()
    if property_type == 'private_room':
        return False, "property_type_private_room"
    
    # Check number of bedrooms - must have at least 2
    bedrooms = listing.get('number_of_bedrooms')
    if bedrooms is None or bedrooms < 2:
        return False, "insufficient_bedrooms"
    
    # Check status - must be active/published
    status = listing.get('status', '').lower()
    if status in ('draft', 'archived', 'inactive'):
        return False, f"status_{status}"
    
    # Check accepts_groups flag (if exists)
    accepts_groups = listing.get('accepts_groups')
    if accepts_groups is False:  # Explicitly set to False
        return False, "groups_not_accepted"
    
    # Validate required location data
    if not listing.get('city'):
        return False, "missing_city"
    
    # Validate price
    price = listing.get('price_per_month')
    if price is None or price <= 0:
        return False, "invalid_price"
    
    # Validate coordinates if present (optional but should be reasonable)
    lat = listing.get('latitude')
    lon = listing.get('longitude')
    if lat is not None and (lat < -90 or lat > 90):
        return False, "invalid_latitude"
    if lon is not None and (lon < -180 or lon > 180):
        return False, "invalid_longitude"
    
    return True, None


def deduplicate_listings(listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate listings (same address + host + price).
    Keep the most recently created listing.
    
    Args:
        listings: List of listings
        
    Returns:
        Deduplicated list of listings
    """
    # Create a key for each listing
    seen = {}
    
    for listing in listings:
        # Create dedup key from address + host + price
        address = (listing.get('address_line_1') or '').lower().strip()
        host = listing.get('host_user_id', '')
        price = listing.get('price_per_month', 0)
        
        key = f"{host}:{address}:{price}"
        
        # If we've seen this key before, keep the newer listing
        if key in seen:
            existing = seen[key]
            existing_date = existing.get('created_at', '')
            new_date = listing.get('created_at', '')
            
            # Keep the newer one
            if new_date > existing_date:
                seen[key] = listing
        else:
            seen[key] = listing
    
    return list(seen.values())


def get_eligible_listings(
    all_listings: List[Dict[str, Any]], 
    city: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Filter listings to only eligible ones for stable matching.
    
    Args:
        all_listings: All listings from database
        city: Optional city filter
        
    Returns:
        Tuple of (eligible_listings, rejection_stats)
        - eligible_listings: List of eligible listings
        - rejection_stats: Dict counting rejection reasons
    """
    eligible = []
    rejection_stats = {}
    
    for listing in all_listings:
        # Optional city filter
        if city and listing.get('city', '').lower() != city.lower():
            continue
        
        # Check eligibility
        is_eligible, reason = is_listing_pair_eligible(listing)
        
        if is_eligible:
            eligible.append(listing)
        else:
            rejection_stats[reason] = rejection_stats.get(reason, 0) + 1
    
    # Deduplicate
    eligible = deduplicate_listings(eligible)
    
    return eligible, rejection_stats


# =============================================================================
# 1.2 Group Eligibility Filters
# =============================================================================

def is_group_eligible(group: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Check if a roommate group is eligible for stable matching.
    
    Args:
        group: Parsed group dictionary with members
        
    Returns:
        Tuple of (is_eligible, rejection_reason)
    """
    # Check target_group_size - MUST be exactly 2
    target_size = group.get('target_group_size')
    if target_size != 2:
        return False, f"group_size_{target_size}_not_2"
    
    # Check status - must be active
    status = group.get('status', '').lower()
    if status != 'active':
        return False, f"status_{status}"
    
    # Check has target_city
    if not group.get('target_city'):
        return False, "missing_target_city"
    
    # Check has budget range
    budget_min = group.get('budget_per_person_min')
    budget_max = group.get('budget_per_person_max')
    
    if budget_min is None or budget_max is None:
        return False, "missing_budget"
    
    # Validate budget range
    if budget_min > budget_max:
        return False, "invalid_budget_range"
    
    if budget_min <= 0 or budget_max <= 0:
        return False, "invalid_budget_values"
    
    # Check has target_move_in_date
    move_in_date = group.get('target_move_in_date')
    if not move_in_date:
        return False, "missing_move_in_date"
    
    # Validate move_in_date is not in the past (allow some grace period)
    if isinstance(move_in_date, str):
        try:
            move_in_date = datetime.fromisoformat(move_in_date.replace('Z', '+00:00')).date()
        except:
            return False, "invalid_move_in_date_format"
    
    # Allow up to 30 days in the past (might be updating old group)
    grace_period = date.today() - timedelta(days=30)
    if move_in_date < grace_period:
        return False, "move_in_date_too_old"
    
    return True, None


def get_eligible_groups(
    all_groups: List[Dict[str, Any]], 
    city: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Filter groups to only eligible ones for stable matching.
    
    Args:
        all_groups: All groups from database
        city: Optional city filter
        
    Returns:
        Tuple of (eligible_groups, rejection_stats)
    """
    eligible = []
    rejection_stats = {}
    
    for group in all_groups:
        # Optional city filter
        if city and group.get('target_city', '').lower() != city.lower():
            continue
        
        # Check eligibility
        is_eligible, reason = is_group_eligible(group)
        
        if is_eligible:
            eligible.append(group)
        else:
            rejection_stats[reason] = rejection_stats.get(reason, 0) + 1
    
    return eligible, rejection_stats


# =============================================================================
# 1.3 Date Window Partitioning
# =============================================================================

class DateWindow:
    """Represents a date window for matching."""
    
    def __init__(self, city: str, start_date: date, end_date: date):
        self.city = city
        self.start_date = start_date
        self.end_date = end_date
        self.groups = []
    
    def add_group(self, group: Dict[str, Any]):
        """Add a group to this window."""
        self.groups.append(group)
    
    def overlaps_with(self, other: 'DateWindow') -> bool:
        """Check if this window overlaps with another window."""
        if self.city.lower() != other.city.lower():
            return False
        return not (self.end_date < other.start_date or self.start_date > other.end_date)
    
    def merge_with(self, other: 'DateWindow') -> 'DateWindow':
        """Merge this window with another overlapping window."""
        merged = DateWindow(
            city=self.city,
            start_date=min(self.start_date, other.start_date),
            end_date=max(self.end_date, other.end_date)
        )
        merged.groups = self.groups + other.groups
        return merged
    
    def __repr__(self):
        return f"DateWindow({self.city}, {self.start_date} to {self.end_date}, {len(self.groups)} groups)"


def get_move_in_windows(
    groups: List[Dict[str, Any]], 
    window_days: int = 60
) -> List[DateWindow]:
    """
    Partition groups into date windows for batched matching.
    
    Args:
        groups: List of eligible groups
        window_days: Size of window around each target date (±days)
        
    Returns:
        List of DateWindow objects with non-overlapping windows per city
    """
    # Group by city first
    city_groups = {}
    for group in groups:
        city = group.get('target_city', '').lower()
        if city not in city_groups:
            city_groups[city] = []
        city_groups[city].append(group)
    
    all_windows = []
    
    # For each city, create windows
    for city, city_group_list in city_groups.items():
        windows = []
        
        for group in city_group_list:
            # Parse target date
            move_in_date = group.get('target_move_in_date')
            if isinstance(move_in_date, str):
                try:
                    move_in_date = datetime.fromisoformat(move_in_date.replace('Z', '+00:00')).date()
                except:
                    continue
            
            # Create window around this date
            start_date = move_in_date - timedelta(days=window_days)
            end_date = move_in_date + timedelta(days=window_days)
            
            # Create new window
            new_window = DateWindow(city=city, start_date=start_date, end_date=end_date)
            new_window.add_group(group)
            
            # Try to merge with existing windows
            merged = False
            for i, existing_window in enumerate(windows):
                if existing_window.overlaps_with(new_window):
                    windows[i] = existing_window.merge_with(new_window)
                    merged = True
                    break
            
            if not merged:
                windows.append(new_window)
        
        # Continue merging until no more overlaps (transitive merging)
        changed = True
        while changed:
            changed = False
            for i in range(len(windows)):
                for j in range(i + 1, len(windows)):
                    if windows[i].overlaps_with(windows[j]):
                        windows[i] = windows[i].merge_with(windows[j])
                        windows.pop(j)
                        changed = True
                        break
                if changed:
                    break
        
        all_windows.extend(windows)
    
    return all_windows


# =============================================================================
# Helper Functions
# =============================================================================

def normalize_city_name(city: str) -> str:
    """
    Normalize city name for comparison.
    
    Args:
        city: City name
        
    Returns:
        Normalized city name
    """
    if not city:
        return ""
    
    # Convert to lowercase
    normalized = city.lower().strip()
    
    # Handle common aliases
    aliases = {
        'sf': 'san francisco',
        'san fran': 'san francisco',
        'nyc': 'new york',
        'new york city': 'new york',
        'la': 'los angeles',
    }
    
    return aliases.get(normalized, normalized)


def validate_listing_data_quality(listing: Dict[str, Any]) -> List[str]:
    """
    Check for data quality issues in a listing.
    
    Args:
        listing: Listing dictionary
        
    Returns:
        List of warning messages (empty if no issues)
    """
    warnings = []
    
    # Check for outlier prices
    price = listing.get('price_per_month', 0)
    if price < 100:
        warnings.append(f"Suspiciously low price: ${price}")
    elif price > 50000:
        warnings.append(f"Suspiciously high price: ${price}")
    
    # Check for stale listings
    created_at = listing.get('created_at')
    if created_at:
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                pass
        
        if isinstance(created_at, datetime):
            age_days = (datetime.now(created_at.tzinfo) - created_at).days
            if age_days > 365:
                warnings.append(f"Listing is {age_days} days old")
    
    # Check for missing important fields
    if not listing.get('amenities'):
        warnings.append("Missing amenities data")
    
    if not listing.get('description'):
        warnings.append("Missing description")
    
    return warnings


def validate_group_data_quality(group: Dict[str, Any]) -> List[str]:
    """
    Check for data quality issues in a group.
    
    Args:
        group: Group dictionary
        
    Returns:
        List of warning messages (empty if no issues)
    """
    warnings = []
    
    # Check if group has members
    members = group.get('group_members', [])
    current_size = len(members) if members else group.get('current_size', 0)
    target_size = group.get('target_group_size', 2)
    
    if current_size < target_size:
        warnings.append(f"Group not full: {current_size}/{target_size} members")
    
    # Check budget range reasonableness
    budget_min = group.get('budget_per_person_min', 0)
    budget_max = group.get('budget_per_person_max', 0)
    
    if budget_max - budget_min > 5000:
        warnings.append(f"Very wide budget range: ${budget_min}-${budget_max}")
    
    # Check for missing description
    if not group.get('description'):
        warnings.append("Missing group description")
    
    return warnings
