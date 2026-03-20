"""
Group Preferences Aggregator

Aggregates preferences from group members into collective group preferences.

Aggregation Rules:
- Budget: OVERLAP (most restrictive range)
- Dates: MEDIAN (middle value)
- Lifestyle: MOST RESTRICTIVE (highest standards)
- Furnished/Utilities: ANY (if anyone wants it, group wants it)
- Lease Type: MOST COMMON
- Lease Duration: MEDIAN
"""

from typing import List, Dict, Any
from datetime import date, datetime
from collections import Counter


def calculate_aggregate_group_preferences(group_id: str) -> Dict[str, Any]:
    """Aggregate preferences from all accepted group members."""
    from app.dependencies.supabase import get_admin_client
    
    supabase = get_admin_client()
    
    # Get accepted member IDs
    members_response = supabase.table('group_members')\
        .select('user_id')\
        .eq('group_id', group_id)\
        .eq('status', 'accepted')\
        .execute()
    
    if not members_response.data:
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
        return get_group_level_preferences(group_id)
    
    aggregated = {}
    
    # Budget: OVERLAP (highest min, lowest max)
    budget_mins = [float(p.get('budget_min', 0)) for p in all_member_prefs if p.get('budget_min')]
    budget_maxs = [float(p.get('budget_max', float('inf'))) for p in all_member_prefs if p.get('budget_max')]
    
    if budget_mins and budget_maxs:
        agg_min, agg_max = max(budget_mins), min(budget_maxs)
        if agg_min <= agg_max:
            aggregated['budget_per_person_min'] = agg_min
            aggregated['budget_per_person_max'] = agg_max
        else:
            # No overlap - use group-level
            group_prefs = get_group_level_preferences(group_id)
            aggregated['budget_per_person_min'] = group_prefs.get('budget_per_person_min')
            aggregated['budget_per_person_max'] = group_prefs.get('budget_per_person_max')
    else:
        group_prefs = get_group_level_preferences(group_id)
        aggregated['budget_per_person_min'] = group_prefs.get('budget_per_person_min')
        aggregated['budget_per_person_max'] = group_prefs.get('budget_per_person_max')
    
    # Move-in Date: MEDIAN
    all_dates = []
    for p in all_member_prefs:
        move_in = p.get('move_in_date')
        if move_in:
            if isinstance(move_in, str):
                try:
                    move_in = datetime.fromisoformat(move_in.replace('Z', '+00:00')).date()
                except:
                    continue
            if isinstance(move_in, date):
                all_dates.append(move_in)
    
    if all_dates:
        sorted_dates = sorted(all_dates)
        aggregated['target_move_in_date'] = sorted_dates[len(sorted_dates) // 2]
    else:
        aggregated['target_move_in_date'] = get_group_level_preferences(group_id).get('target_move_in_date')
    
    # Bedrooms/Bathrooms: Based on group size
    aggregated['target_bedrooms'] = len(member_ids)
    aggregated['target_bathrooms'] = 1.0 if len(member_ids) <= 2 else (1.5 if len(member_ids) <= 4 else 2.0)
    
    # Lifestyle: MOST RESTRICTIVE
    aggregated['lifestyle_preferences'] = aggregate_lifestyle_preferences(all_member_prefs)
    
    # Furnished preference:
    # - required if any member marks required
    # - preferred if anyone marks preferred and no one requires
    # - no_preference otherwise
    furnished_pref_values = [
        p.get('furnished_preference')
        for p in all_member_prefs
        if p.get('furnished_preference') is not None
    ]
    if "required" in furnished_pref_values:
        aggregated['furnished_preference'] = 'required'
        aggregated['target_furnished'] = True
        aggregated['furnished_is_hard'] = True
    elif "preferred" in furnished_pref_values:
        aggregated['furnished_preference'] = 'preferred'
        aggregated['target_furnished'] = True
        aggregated['furnished_is_hard'] = False
    elif furnished_pref_values:
        aggregated['furnished_preference'] = 'no_preference'
        aggregated['target_furnished'] = None
        aggregated['furnished_is_hard'] = False
    else:
        # Backward-compat fallback to legacy boolean field.
        furnished_prefs = [p.get('target_furnished') for p in all_member_prefs if p.get('target_furnished') is not None]
        if furnished_prefs:
            aggregated['furnished_preference'] = 'required'
            aggregated['target_furnished'] = any(furnished_prefs)
            aggregated['furnished_is_hard'] = any(furnished_prefs)
    
    # Utilities: ANY wants it → group wants it
    utilities_prefs = [p.get('target_utilities_included') for p in all_member_prefs if p.get('target_utilities_included') is not None]
    if utilities_prefs:
        aggregated['target_utilities_included'] = any(utilities_prefs)
    
    # Lease Type: MOST COMMON
    lease_types = [p.get('target_lease_type') for p in all_member_prefs if p.get('target_lease_type') and p.get('target_lease_type') != 'any']
    if lease_types:
        most_common = Counter(lease_types).most_common(1)
        if most_common:
            aggregated['target_lease_type'] = most_common[0][0]
    
    # Lease Duration: MEDIAN
    durations = [int(p.get('target_lease_duration_months')) for p in all_member_prefs if p.get('target_lease_duration_months')]
    if durations:
        aggregated['target_lease_duration_months'] = sorted(durations)[len(durations) // 2]

    # Gender policy: if any member asks same-gender-only, group policy is restrictive.
    gender_policies = [p.get('gender_policy') for p in all_member_prefs if p.get('gender_policy')]
    if 'same_gender_only' in gender_policies:
        aggregated['gender_policy'] = 'same_gender_only'
    elif gender_policies:
        aggregated['gender_policy'] = 'mixed_ok'
    
    return aggregated


def get_group_level_preferences(group_id: str) -> Dict[str, Any]:
    """Get preferences from the group record (fallback)."""
    from app.dependencies.supabase import get_admin_client
    
    supabase = get_admin_client()
    group_response = supabase.table('roommate_groups')\
        .select('*')\
        .eq('id', group_id)\
        .single()\
        .execute()
    
    if not group_response.data:
        return {}
    
    g = group_response.data
    return {
        'budget_per_person_min': g.get('budget_per_person_min'),
        'budget_per_person_max': g.get('budget_per_person_max'),
        'target_move_in_date': g.get('target_move_in_date'),
        'target_bedrooms': g.get('target_bedrooms'),
        'target_bathrooms': g.get('target_bathrooms'),
        'target_furnished': g.get('target_furnished'),
        'furnished_preference': g.get('furnished_preference'),
        'furnished_is_hard': g.get('furnished_is_hard'),
        'target_utilities_included': g.get('target_utilities_included'),
        'target_lease_type': g.get('target_lease_type'),
        'target_lease_duration_months': g.get('target_lease_duration_months'),
        'gender_policy': g.get('gender_policy'),
        'lifestyle_preferences': {}
    }


def aggregate_lifestyle_preferences(all_member_prefs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate lifestyle using MOST RESTRICTIVE approach (highest index wins)."""
    all_lifestyles = [p.get('lifestyle_preferences', {}) for p in all_member_prefs if p.get('lifestyle_preferences')]
    
    if not all_lifestyles:
        return {}
    
    # Order from least to most restrictive
    preference_orders = {
        'cleanliness': ['messy', 'moderate', 'clean', 'very_clean'],
        'noise_level': ['loud', 'moderate', 'quiet'],
        'smoking': ['smoking_ok', 'outdoor_only', 'no_smoking'],
        'pets': ['pets_ok', 'no_pets'],
        'guests_frequency': ['frequently', 'occasionally', 'rarely']
    }
    
    aggregated = {}
    for attr, order in preference_orders.items():
        all_values = [lp.get(attr) for lp in all_lifestyles if lp.get(attr)]
        if all_values:
            try:
                aggregated[attr] = max(all_values, key=lambda x: order.index(x) if x in order else -1)
            except ValueError:
                pass
    
    return aggregated


__all__ = ['calculate_aggregate_group_preferences', 'aggregate_lifestyle_preferences']
