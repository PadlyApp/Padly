"""
Stable Matching - Data Filtering & Eligibility
Filters listings and groups for stable matching algorithm.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from app.services.location_matching import cities_match, normalize_city_name


# --- LISTING ELIGIBILITY ---

def is_listing_pair_eligible(listing: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Check if listing is eligible for 2-person group matching."""
    # Must not be private room
    if listing.get('property_type', '').lower() == 'private_room':
        return False, "property_type_private_room"
    
    # Must have 2+ bedrooms
    if (listing.get('number_of_bedrooms') or 0) < 2:
        return False, "insufficient_bedrooms"
    
    # Must be active
    status = listing.get('status', '').lower()
    if status in ('draft', 'archived', 'inactive'):
        return False, f"status_{status}"
    
    # Must accept groups
    if listing.get('accepts_groups') is False:
        return False, "groups_not_accepted"
    
    # Must have location and valid price
    if not listing.get('city'):
        return False, "missing_city"
    if not listing.get('price_per_month') or listing.get('price_per_month') <= 0:
        return False, "invalid_price"
    
    # Validate coordinates if present
    lat, lon = listing.get('latitude'), listing.get('longitude')
    if lat is not None and (lat < -90 or lat > 90):
        return False, "invalid_latitude"
    if lon is not None and (lon < -180 or lon > 180):
        return False, "invalid_longitude"
    
    return True, None


def deduplicate_listings(listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate listings (same address + host + price). Keep most recent."""
    seen = {}
    for listing in listings:
        address = (listing.get('address_line_1') or '').lower().strip()
        key = f"{listing.get('host_user_id', '')}:{address}:{listing.get('price_per_month', 0)}"
        
        if key not in seen or listing.get('created_at', '') > seen[key].get('created_at', ''):
            seen[key] = listing
    
    return list(seen.values())


def get_eligible_listings(all_listings: List[Dict[str, Any]], city: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Filter listings to eligible ones. Returns (eligible_listings, rejection_stats)."""
    eligible = []
    rejection_stats = {}
    
    for listing in all_listings:
        if city and not cities_match(city, listing.get('city')):
            continue
        
        is_eligible, reason = is_listing_pair_eligible(listing)
        if is_eligible:
            eligible.append(listing)
        else:
            rejection_stats[reason] = rejection_stats.get(reason, 0) + 1
    
    return deduplicate_listings(eligible), rejection_stats


# --- GROUP ELIGIBILITY ---

def is_group_eligible(group: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Check if roommate group is eligible for stable matching."""
    # Must be exactly 2-person group
    if group.get('target_group_size') != 2:
        return False, f"group_size_{group.get('target_group_size')}_not_2"
    
    # Must be active
    if group.get('status', '').lower() != 'active':
        return False, f"status_{group.get('status')}"
    
    # Must have target city
    if not group.get('target_city'):
        return False, "missing_target_city"
    
    # Must have valid budget
    budget_min = group.get('budget_per_person_min')
    budget_max = group.get('budget_per_person_max')
    if budget_min is None or budget_max is None:
        return False, "missing_budget"
    if budget_min > budget_max or budget_min <= 0 or budget_max <= 0:
        return False, "invalid_budget_range"
    
    # Must have valid move-in date
    move_in_date = group.get('target_move_in_date')
    if not move_in_date:
        return False, "missing_move_in_date"
    
    if isinstance(move_in_date, str):
        try:
            move_in_date = datetime.fromisoformat(move_in_date.replace('Z', '+00:00')).date()
        except:
            return False, "invalid_move_in_date_format"
    
    # Allow up to 30 days in past
    if move_in_date < date.today() - timedelta(days=30):
        return False, "move_in_date_too_old"
    
    return True, None


def get_eligible_groups(all_groups: List[Dict[str, Any]], city: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Filter groups to eligible ones. Returns (eligible_groups, rejection_stats)."""
    eligible = []
    rejection_stats = {}
    
    for group in all_groups:
        if city and not cities_match(city, group.get('target_city')):
            continue
        
        is_eligible, reason = is_group_eligible(group)
        if is_eligible:
            eligible.append(group)
        else:
            rejection_stats[reason] = rejection_stats.get(reason, 0) + 1
    
    return eligible, rejection_stats


# --- DATE WINDOW PARTITIONING ---

class DateWindow:
    """Represents a date window for batched matching."""
    
    def __init__(self, city: str, start_date: date, end_date: date):
        self.city = city
        self.start_date = start_date
        self.end_date = end_date
        self.groups = []
    
    def add_group(self, group: Dict[str, Any]):
        self.groups.append(group)
    
    def overlaps_with(self, other: 'DateWindow') -> bool:
        if self.city.lower() != other.city.lower():
            return False
        return not (self.end_date < other.start_date or self.start_date > other.end_date)
    
    def merge_with(self, other: 'DateWindow') -> 'DateWindow':
        merged = DateWindow(
            city=self.city,
            start_date=min(self.start_date, other.start_date),
            end_date=max(self.end_date, other.end_date)
        )
        merged.groups = self.groups + other.groups
        return merged


def get_move_in_windows(groups: List[Dict[str, Any]], window_days: int = 60) -> List[DateWindow]:
    """Partition groups into date windows for batched matching (±window_days)."""
    city_groups = {}
    for group in groups:
        city = group.get('target_city', '').lower()
        city_groups.setdefault(city, []).append(group)
    
    all_windows = []
    
    for city, city_group_list in city_groups.items():
        windows = []
        
        for group in city_group_list:
            move_in_date = group.get('target_move_in_date')
            if isinstance(move_in_date, str):
                try:
                    move_in_date = datetime.fromisoformat(move_in_date.replace('Z', '+00:00')).date()
                except:
                    continue
            
            new_window = DateWindow(
                city=city,
                start_date=move_in_date - timedelta(days=window_days),
                end_date=move_in_date + timedelta(days=window_days)
            )
            new_window.add_group(group)
            
            # Merge with existing overlapping window
            merged = False
            for i, existing in enumerate(windows):
                if existing.overlaps_with(new_window):
                    windows[i] = existing.merge_with(new_window)
                    merged = True
                    break
            
            if not merged:
                windows.append(new_window)
        
        # Transitive merging
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


# --- HELPERS ---

def validate_listing_data_quality(listing: Dict[str, Any]) -> List[str]:
    """Check for data quality issues in a listing."""
    warnings = []
    
    price = listing.get('price_per_month', 0)
    if price < 100:
        warnings.append(f"Suspiciously low price: ${price}")
    elif price > 50000:
        warnings.append(f"Suspiciously high price: ${price}")
    
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
    
    if not listing.get('amenities'):
        warnings.append("Missing amenities data")
    if not listing.get('description'):
        warnings.append("Missing description")
    
    return warnings


def validate_group_data_quality(group: Dict[str, Any]) -> List[str]:
    """Check for data quality issues in a group."""
    warnings = []
    
    members = group.get('group_members', [])
    current_size = len(members) if members else group.get('current_size', 0)
    target_size = group.get('target_group_size', 2)
    
    if current_size < target_size:
        warnings.append(f"Group not full: {current_size}/{target_size} members")
    
    budget_min = group.get('budget_per_person_min', 0)
    budget_max = group.get('budget_per_person_max', 0)
    if budget_max - budget_min > 5000:
        warnings.append(f"Very wide budget range: ${budget_min}-${budget_max}")
    
    if not group.get('description'):
        warnings.append("Missing group description")
    
    return warnings
