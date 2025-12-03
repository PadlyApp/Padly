"""
Group Re-Matching Service

Handles automatic re-matching when groups change composition or preferences.

Triggers:
- Member joins (status → 'accepted')
- Member leaves (deleted from group_members)
- Group preferences updated

Process:
1. Delete old matches for the group
2. Calculate new aggregate preferences
3. Find eligible listings for new group size
4. Run matching algorithm
5. Save new matches
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime


async def trigger_group_rematching(group_id: str) -> Dict[str, Any]:
    """
    Re-run matching for a specific group after composition/preference changes.
    
    This is the main entry point for dynamic re-matching. Call this whenever:
    - A member is approved
    - A member is removed
    - Group preferences are updated
    
    Args:
        group_id: UUID of the group to re-match
        
    Returns:
        Dict with results:
        {
            'status': 'success' | 'no_matches' | 'skipped' | 'error',
            'group_id': str,
            'matches_found': int,
            'old_matches_deleted': int,
            'message': str,
            'execution_time_ms': int
        }
    """
    
    start_time = datetime.now()
    
    from app.services.supabase_client import get_supabase_admin_client
    from app.services.group_preferences_aggregator import calculate_aggregate_group_preferences
    from app.services.stable_matching.filters import get_eligible_listings
    from app.services.stable_matching.feasible_pairs import (
        location_matches,
        date_matches,
        price_matches,
        hard_attributes_match
    )
    from app.services.stable_matching.scoring import (
        calculate_group_score,
        calculate_listing_score
    )
    
    supabase = get_supabase_admin_client()
    
    # Step 1: Get current group state
    try:
        group_response = supabase.table('roommate_groups')\
            .select('*')\
            .eq('id', group_id)\
            .single()\
            .execute()
    except Exception as e:
        return {
            'status': 'error',
            'group_id': group_id,
            'message': f'Group not found: {str(e)}',
            'matches_found': 0,
            'old_matches_deleted': 0
        }
    
    if not group_response.data:
        return {
            'status': 'error',
            'group_id': group_id,
            'message': 'Group not found',
            'matches_found': 0,
            'old_matches_deleted': 0
        }
    
    group = group_response.data
    
    # Check if group is eligible for matching
    if group.get('status') != 'active':
        return {
            'status': 'skipped',
            'group_id': group_id,
            'message': 'Group is not active',
            'matches_found': 0,
            'old_matches_deleted': 0
        }
    
    current_member_count = group.get('current_member_count', 0)
    if current_member_count == 0:
        return {
            'status': 'skipped',
            'group_id': group_id,
            'message': 'Group has no members yet',
            'matches_found': 0,
            'old_matches_deleted': 0
        }
    
    # Step 2: Delete old matches
    try:
        delete_response = supabase.table('stable_matches')\
            .delete()\
            .eq('group_id', group_id)\
            .execute()
        
        old_count = len(delete_response.data) if delete_response.data else 0
    except Exception as e:
        old_count = 0  # Continue even if deletion fails
    
    # Step 3: Calculate aggregate preferences
    try:
        aggregate_prefs = calculate_aggregate_group_preferences(group_id)
    except Exception as e:
        return {
            'status': 'error',
            'group_id': group_id,
            'message': f'Failed to aggregate preferences: {str(e)}',
            'matches_found': 0,
            'old_matches_deleted': old_count
        }
    
    # Check for budget overlap validity
    budget_min = aggregate_prefs.get('budget_per_person_min')
    budget_max = aggregate_prefs.get('budget_per_person_max')
    
    if budget_min and budget_max and budget_min > budget_max:
        return {
            'status': 'no_matches',
            'group_id': group_id,
            'message': 'Members have incompatible budgets (no overlap)',
            'matches_found': 0,
            'old_matches_deleted': old_count
        }
    
    # Step 4: Update group with aggregated preferences (for easier querying)
    try:
        update_data = {
            'target_bedrooms': aggregate_prefs.get('target_bedrooms'),
            'target_bathrooms': aggregate_prefs.get('target_bathrooms')
        }
        
        # Only update budget if we have valid values
        if budget_min:
            update_data['budget_per_person_min'] = budget_min
        if budget_max:
            update_data['budget_per_person_max'] = budget_max
        
        # Only update date if we have a valid value
        if aggregate_prefs.get('target_move_in_date'):
            update_data['target_move_in_date'] = str(aggregate_prefs['target_move_in_date'])
        
        supabase.table('roommate_groups')\
            .update(update_data)\
            .eq('id', group_id)\
            .execute()
    except Exception as e:
        # Non-critical - continue even if update fails
        pass
    
    # Step 5: Find eligible listings
    city = group.get('target_city')
    if not city:
        return {
            'status': 'error',
            'group_id': group_id,
            'message': 'Group has no target city',
            'matches_found': 0,
            'old_matches_deleted': old_count
        }
    
    # Get listings with enough bedrooms for group
    min_bedrooms = aggregate_prefs.get('target_bedrooms', current_member_count)
    
    try:
        listings_response = supabase.table('listings')\
            .select('*')\
            .eq('status', 'active')\
            .ilike('city', city)\
            .gte('number_of_bedrooms', min_bedrooms)\
            .execute()
        
        listings = listings_response.data
    except Exception as e:
        return {
            'status': 'error',
            'group_id': group_id,
            'message': f'Failed to fetch listings: {str(e)}',
            'matches_found': 0,
            'old_matches_deleted': old_count
        }
    
    if not listings:
        return {
            'status': 'no_matches',
            'group_id': group_id,
            'message': f'No active listings found in {city} with {min_bedrooms}+ bedrooms',
            'matches_found': 0,
            'old_matches_deleted': old_count
        }
    
    # Step 6: Build feasible pairs (check hard constraints)
    feasible_pairs = []
    
    # Update group dict with aggregate preferences for constraint checking
    group_with_agg = {**group, **aggregate_prefs}
    
    for listing in listings:
        # Check all hard constraints
        if not location_matches(group_with_agg, listing):
            continue
        
        if not date_matches(group_with_agg, listing, delta_days=30):
            continue
        
        if not price_matches(group_with_agg, listing):
            continue
        
        # Hard attributes (furnished, utilities, etc.)
        if not hard_attributes_match(group_with_agg, listing):
            continue
        
        feasible_pairs.append(listing)
    
    if not feasible_pairs:
        return {
            'status': 'no_matches',
            'group_id': group_id,
            'message': 'No feasible matches after applying constraints',
            'matches_found': 0,
            'old_matches_deleted': old_count
        }
    
    # Step 7: Score each feasible listing
    scored_matches = []
    
    for listing in feasible_pairs:
        group_score = calculate_group_score(group_with_agg, listing)
        listing_score = calculate_listing_score(listing, group_with_agg)
        
        scored_matches.append({
            'listing': listing,
            'group_score': group_score,
            'listing_score': listing_score
        })
    
    # Sort by group score (most important for user experience)
    scored_matches.sort(key=lambda x: x['group_score'], reverse=True)
    
    # Step 8: Save top matches (limit to 10)
    matches_to_save = []
    
    for rank, match in enumerate(scored_matches[:10], 1):
        matches_to_save.append({
            'group_id': group_id,
            'listing_id': match['listing']['id'],
            'group_score': float(match['group_score']),
            'listing_score': float(match['listing_score']),
            'group_rank': rank,
            'status': 'active',
            'is_stable': True,  # Mark as stable (single-sided matching)
            'created_at': datetime.utcnow().isoformat()
        })
    
    if matches_to_save:
        try:
            supabase.table('stable_matches').insert(matches_to_save).execute()
        except Exception as e:
            return {
                'status': 'error',
                'group_id': group_id,
                'message': f'Failed to save matches: {str(e)}',
                'matches_found': 0,
                'old_matches_deleted': old_count
            }
    
    # Calculate execution time
    execution_time = (datetime.now() - start_time).total_seconds() * 1000
    
    return {
        'status': 'success',
        'group_id': group_id,
        'matches_found': len(matches_to_save),
        'old_matches_deleted': old_count,
        'message': f'Re-matched successfully: found {len(matches_to_save)} matches (deleted {old_count} old matches)',
        'execution_time_ms': int(execution_time)
    }


# Export public API
__all__ = ['trigger_group_rematching']
