"""
Group Re-Matching Service

Auto re-matches groups when members/preferences change.
Triggers: member join/leave, preference updates.
"""

from typing import Dict, Any
from datetime import datetime


async def trigger_group_rematching(group_id: str) -> Dict[str, Any]:
    """Re-run matching for a group after composition/preference changes."""
    start_time = datetime.now()
    
    from app.services.supabase_client import get_supabase_admin_client
    from app.services.group_preferences_aggregator import calculate_aggregate_group_preferences
    from app.services.stable_matching.feasible_pairs import (
        location_matches, date_matches, price_matches, hard_attributes_match
    )
    from app.services.stable_matching.scoring import calculate_group_score, calculate_listing_score
    
    supabase = get_supabase_admin_client()
    
    # Get group
    try:
        group_response = supabase.table('roommate_groups').select('*').eq('id', group_id).single().execute()
    except Exception as e:
        return {'status': 'error', 'group_id': group_id, 'message': f'Group not found: {e}', 'matches_found': 0, 'old_matches_deleted': 0}
    
    if not group_response.data:
        return {'status': 'error', 'group_id': group_id, 'message': 'Group not found', 'matches_found': 0, 'old_matches_deleted': 0}
    
    group = group_response.data
    
    # Check eligibility
    if group.get('status') != 'active':
        return {'status': 'skipped', 'group_id': group_id, 'message': 'Group not active', 'matches_found': 0, 'old_matches_deleted': 0}
    
    if group.get('current_member_count', 0) == 0:
        return {'status': 'skipped', 'group_id': group_id, 'message': 'No members', 'matches_found': 0, 'old_matches_deleted': 0}
    
    # Delete old matches
    try:
        del_resp = supabase.table('stable_matches').delete().eq('group_id', group_id).execute()
        old_count = len(del_resp.data) if del_resp.data else 0
    except:
        old_count = 0
    
    # Aggregate preferences
    try:
        agg_prefs = calculate_aggregate_group_preferences(group_id)
    except Exception as e:
        return {'status': 'error', 'group_id': group_id, 'message': f'Aggregation failed: {e}', 'matches_found': 0, 'old_matches_deleted': old_count}
    
    # Check budget overlap
    budget_min = agg_prefs.get('budget_per_person_min')
    budget_max = agg_prefs.get('budget_per_person_max')
    if budget_min and budget_max and budget_min > budget_max:
        return {'status': 'no_matches', 'group_id': group_id, 'message': 'Incompatible budgets', 'matches_found': 0, 'old_matches_deleted': old_count}
    
    # Update group with aggregated preferences
    try:
        update_data = {
            'target_bedrooms': agg_prefs.get('target_bedrooms'),
            'target_bathrooms': agg_prefs.get('target_bathrooms'),
            'target_furnished': agg_prefs.get('target_furnished'),
            'furnished_preference': agg_prefs.get('furnished_preference'),
            'furnished_is_hard': agg_prefs.get('furnished_is_hard', False),
            'gender_policy': agg_prefs.get('gender_policy'),
        }
        if budget_min: update_data['budget_per_person_min'] = budget_min
        if budget_max: update_data['budget_per_person_max'] = budget_max
        if agg_prefs.get('target_move_in_date'): update_data['target_move_in_date'] = str(agg_prefs['target_move_in_date'])
        supabase.table('roommate_groups').update(update_data).eq('id', group_id).execute()
    except:
        pass
    
    # Get eligible listings
    city = group.get('target_city')
    if not city:
        return {'status': 'error', 'group_id': group_id, 'message': 'No target city', 'matches_found': 0, 'old_matches_deleted': old_count}
    
    min_bedrooms = agg_prefs.get('target_bedrooms', group.get('current_member_count', 2))
    
    try:
        listings = supabase.table('listings').select('*').eq('status', 'active').ilike('city', city).gte('number_of_bedrooms', min_bedrooms).execute().data
    except Exception as e:
        return {'status': 'error', 'group_id': group_id, 'message': f'Fetch listings failed: {e}', 'matches_found': 0, 'old_matches_deleted': old_count}
    
    if not listings:
        return {'status': 'no_matches', 'group_id': group_id, 'message': f'No listings in {city}', 'matches_found': 0, 'old_matches_deleted': old_count}
    
    # Check hard constraints
    group_with_agg = {**group, **agg_prefs}
    feasible = [l for l in listings if (
        location_matches(group_with_agg, l) and
        date_matches(group_with_agg, l, delta_days=30) and
        price_matches(group_with_agg, l) and
        hard_attributes_match(group_with_agg, l)
    )]
    
    if not feasible:
        return {'status': 'no_matches', 'group_id': group_id, 'message': 'No feasible matches', 'matches_found': 0, 'old_matches_deleted': old_count}
    
    # Score and sort
    scored = [{'listing': l, 'group_score': calculate_group_score(group_with_agg, l), 'listing_score': calculate_listing_score(l, group_with_agg)} for l in feasible]
    scored.sort(key=lambda x: x['group_score'], reverse=True)
    
    # Save top 10
    matches_to_save = [{
        'group_id': group_id,
        'listing_id': m['listing']['id'],
        'group_score': float(m['group_score']),
        'listing_score': float(m['listing_score']),
        'group_rank': rank,
        'status': 'active',
        'is_stable': True,
        'created_at': datetime.utcnow().isoformat()
    } for rank, m in enumerate(scored[:10], 1)]
    
    if matches_to_save:
        try:
            supabase.table('stable_matches').insert(matches_to_save).execute()
        except Exception as e:
            return {'status': 'error', 'group_id': group_id, 'message': f'Save failed: {e}', 'matches_found': 0, 'old_matches_deleted': old_count}
    
    exec_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    
    return {
        'status': 'success',
        'group_id': group_id,
        'matches_found': len(matches_to_save),
        'old_matches_deleted': old_count,
        'message': f'Found {len(matches_to_save)} matches',
        'execution_time_ms': exec_ms
    }


__all__ = ['trigger_group_rematching']
