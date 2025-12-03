"""
Group Preferences Aggregator

Aggregates preferences from all accepted group members to determine
the group's collective preferences for housing matching.

Key Principles:
- Budget: OVERLAP (most restrictive range that works for all)
- Dates: MEDIAN (middle value)
- Lifestyle: MOST RESTRICTIVE (highest standards)
- Bedrooms: Group size (minimum needed)
- Bathrooms: Scale with group size
"""

from typing import List, Dict, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from statistics import median


def calculate_aggregate_group_preferences(group_id: str) -> Dict[str, Any]:
    """
    Calculate aggregate preferences from all accepted group members.
    
    This combines individual member preferences into a single set of
    group-level preferences suitable for matching with listings.
    
    Args:
        group_id: UUID of the group
        
    Returns:
        Dict with aggregated preferences:
        {
            'budget_per_person_min': float,
            'budget_per_person_max': float,
            'target_move_in_date': date,
            'target_bedrooms': int,
            'target_bathrooms': float,
            'lifestyle_preferences': dict
        }
    """
    
    from app.dependencies.supabase import get_admin_client
    
    supabase = get_admin_client()
    
    # Get all accepted members
    members_response = supabase.table('group_members')\
        .select('user_id')\
        .eq('group_id', group_id)\
        .eq('status', 'accepted')\
        .execute()
    
    if not members_response.data:
        # No members yet, fall back to group-level preferences
        return get_group_level_preferences(group_id)
    
    member_ids = [m['user_id'] for m in members_response.data]
    
    # Get each member's preferences
    all_member_prefs = []
    for user_id in member_ids:
        prefs_response = supabase.table('personal_preferences')\
            .select('*')\
            .eq('user_id', user_id)\
            .execute()
        
        if prefs_response.data:
            all_member_prefs.append(prefs_response.data[0])
    
    if not all_member_prefs:
        # No member preferences, use group-level
        return get_group_level_preferences(group_id)
    
    # Aggregate preferences
    aggregated = {}
    
    # 1. Budget: Find OVERLAP of all ranges
    budget_mins = [
        float(p.get('budget_min', 0)) 
        for p in all_member_prefs 
        if p.get('budget_min') is not None
    ]
    budget_maxs = [
        float(p.get('budget_max', float('inf'))) 
        for p in all_member_prefs 
        if p.get('budget_max') is not None
    ]
    
    if budget_mins and budget_maxs:
        # Overlap = highest min, lowest max
        aggregated['budget_per_person_min'] = max(budget_mins)
        aggregated['budget_per_person_max'] = min(budget_maxs)
        
        # If no overlap, use group-level budget
        if aggregated['budget_per_person_min'] > aggregated['budget_per_person_max']:
            group_prefs = get_group_level_preferences(group_id)
            aggregated['budget_per_person_min'] = group_prefs.get('budget_per_person_min')
            aggregated['budget_per_person_max'] = group_prefs.get('budget_per_person_max')
    else:
        # Use group-level budget
        group_prefs = get_group_level_preferences(group_id)
        aggregated['budget_per_person_min'] = group_prefs.get('budget_per_person_min')
        aggregated['budget_per_person_max'] = group_prefs.get('budget_per_person_max')
    
    # 2. Move-in Date: Use MEDIAN
    all_dates = []
    for p in all_member_prefs:
        move_in_date = p.get('move_in_date')
        if move_in_date:
            if isinstance(move_in_date, str):
                try:
                    move_in_date = datetime.fromisoformat(move_in_date.replace('Z', '+00:00')).date()
                except:
                    continue
            if isinstance(move_in_date, date):
                all_dates.append(move_in_date)
    
    if all_dates:
        # Sort and take median
        sorted_dates = sorted(all_dates)
        median_index = len(sorted_dates) // 2
        aggregated['target_move_in_date'] = sorted_dates[median_index]
    else:
        # Use group-level date
        group_prefs = get_group_level_preferences(group_id)
        aggregated['target_move_in_date'] = group_prefs.get('target_move_in_date')
    
    # 3. Bedrooms: At least as many as group size
    aggregated['target_bedrooms'] = len(member_ids)
    
    # 4. Bathrooms: Scale with group size
    aggregated['target_bathrooms'] = calculate_bathroom_needs(len(member_ids))
    
    # 5. Lifestyle: Aggregate with MOST RESTRICTIVE
    aggregated['lifestyle_preferences'] = aggregate_lifestyle_preferences(all_member_prefs)
    
    return aggregated


def get_group_level_preferences(group_id: str) -> Dict[str, Any]:
    """
    Get preferences from the group record itself (fallback).
    
    Used when members don't have individual preferences set.
    """
    
    from app.dependencies.supabase import get_admin_client
    
    supabase = get_admin_client()
    
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        return {}
    
    group = group_response.data
    
    return {
        'budget_per_person_min': group.get('budget_per_person_min'),
        'budget_per_person_max': group.get('budget_per_person_max'),
        'target_move_in_date': group.get('target_move_in_date'),
        'target_bedrooms': group.get('target_bedrooms'),
        'target_bathrooms': group.get('target_bathrooms'),
        'lifestyle_preferences': {}
    }


def calculate_bathroom_needs(group_size: int) -> float:
    """
    Calculate recommended bathrooms based on group size.
    
    Rules:
    - 1-2 people: 1 bathroom OK
    - 3-4 people: 1.5 bathrooms preferred
    - 5+ people: 2+ bathrooms preferred
    
    Args:
        group_size: Number of people in group
        
    Returns:
        Recommended minimum bathrooms
    """
    
    if group_size <= 2:
        return 1.0
    elif group_size <= 4:
        return 1.5
    else:
        return 2.0


def aggregate_lifestyle_preferences(all_member_prefs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate lifestyle preferences using MOST RESTRICTIVE approach.
    
    Logic:
    - If anyone wants "very_clean", group requires "very_clean"
    - If anyone wants "quiet", group requires "quiet"
    - If anyone wants "no_smoking", group requires "no_smoking"
    - If anyone wants "no_pets", group requires "no_pets"
    
    This ensures all members' requirements are met.
    
    Args:
        all_member_prefs: List of personal_preferences dicts
        
    Returns:
        Aggregated lifestyle_preferences dict
    """
    
    # Extract all lifestyle preferences
    all_lifestyles = [
        p.get('lifestyle_preferences', {}) 
        for p in all_member_prefs 
        if p.get('lifestyle_preferences')
    ]
    
    if not all_lifestyles:
        return {}
    
    aggregated = {}
    
    # Define order from least to most restrictive
    preference_orders = {
        'cleanliness': ['messy', 'moderate', 'clean', 'very_clean'],
        'noise_level': ['loud', 'moderate', 'quiet'],
        'smoking': ['smoking_ok', 'outdoor_only', 'no_smoking'],
        'pets': ['pets_ok', 'no_pets'],
        'guests_frequency': ['frequently', 'occasionally', 'rarely']
    }
    
    # For each attribute, take the MOST restrictive value
    for attribute, order in preference_orders.items():
        all_values = [
            lp.get(attribute) 
            for lp in all_lifestyles 
            if lp.get(attribute)
        ]
        
        if all_values:
            # Most restrictive = highest index in order list
            try:
                aggregated[attribute] = max(
                    all_values, 
                    key=lambda x: order.index(x) if x in order else -1
                )
            except ValueError:
                # If value not in order list, skip
                pass
    
    return aggregated


# Export public API
__all__ = [
    'calculate_aggregate_group_preferences',
    'aggregate_lifestyle_preferences',
    'calculate_bathroom_needs'
]
