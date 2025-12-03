"""
User-to-Group Matching Service

This module provides compatibility scoring between individual users and existing
roommate groups, enabling users to discover groups that match their preferences.

Scoring Algorithm:
- Hard Constraints (Binary): City, budget overlap, date proximity, open spots
- Soft Preferences (0-100 points): Budget fit, date fit, company match, 
  verification, lifestyle compatibility
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal


# =============================================================================
# Constants
# =============================================================================

# Scoring weights (total: 100 points)
# Updated to include new preference fields from personal_preferences
SCORING_WEIGHTS = {
    'budget_fit': 20,           # How close are budget midpoints
    'date_fit': 15,             # How close are move-in dates
    'lease_preferences': 15,    # NEW: Lease type & duration match
    'amenity_preferences': 10,  # NEW: Furnished, utilities included
    'company_school_match': 10, # Same company/school bonus
    'verification': 10,         # User verification status
    'lifestyle': 20             # Lifestyle compatibility (smoking, pets, etc.)
}

# Date flexibility for hard constraint (days)
DATE_FLEXIBILITY_DAYS = 60


# =============================================================================
# Main Compatibility Function
# =============================================================================

def calculate_user_group_compatibility(
    user: Dict[str, Any],
    user_prefs: Dict[str, Any],
    group: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate compatibility score between a user and a group.
    
    Args:
        user: User data dict (from users table)
        user_prefs: User preferences dict (from personal_preferences table)
        group: Group data dict (from roommate_groups table)
        
    Returns:
        Dict with keys:
        - score: float (0-100)
        - eligible: bool (passed hard constraints)
        - reasons: List[str] (explanation of score)
        - compatibility_level: str (Excellent/Great/Good/Fair/Poor Match)
    """
    
    score = 0
    reasons = []
    
    # =========================================================================
    # HARD CONSTRAINTS (Must ALL pass or return score=0)
    # =========================================================================
    
    # 1. City Match (REQUIRED)
    user_city = str(user_prefs.get('target_city') or '').lower().strip()
    group_city = str(group.get('target_city') or '').lower().strip()
    
    if not user_city or not group_city or user_city != group_city:
        return {
            'score': 0,
            'eligible': False,
            'reasons': [f'City mismatch: user wants {user_city}, group in {group_city}'],
            'compatibility_level': 'Not Compatible'
        }
    
    # 2. Budget Overlap (REQUIRED)
    user_budget_min = float(user_prefs.get('budget_min') or 0)
    user_budget_max = float(user_prefs.get('budget_max') or float('inf'))
    group_budget_min = float(group.get('budget_per_person_min') or 0)
    group_budget_max = float(group.get('budget_per_person_max') or float('inf'))
    
    # Check if ranges overlap
    overlaps = user_budget_max >= group_budget_min and user_budget_min <= group_budget_max
    
    if not overlaps:
        return {
            'score': 0,
            'eligible': False,
            'reasons': [f'Budget ranges don\'t overlap: user ${user_budget_min}-${user_budget_max}, group ${group_budget_min}-${group_budget_max}'],
            'compatibility_level': 'Not Compatible'
        }
    
    # 3. Move-in Date Proximity (REQUIRED - within ±60 days)
    user_date = user_prefs.get('move_in_date')
    group_date = group.get('target_move_in_date')
    
    if user_date and group_date:
        # Convert to date objects if strings
        if isinstance(user_date, str):
            user_date = datetime.fromisoformat(user_date.replace('Z', '+00:00')).date()
        if isinstance(group_date, str):
            group_date = datetime.fromisoformat(group_date.replace('Z', '+00:00')).date()
        
        date_diff = abs((user_date - group_date).days)
        
        if date_diff > DATE_FLEXIBILITY_DAYS:
            return {
                'score': 0,
                'eligible': False,
                'reasons': [f'Move-in dates too far apart: {date_diff} days (max {DATE_FLEXIBILITY_DAYS})'],
                'compatibility_level': 'Not Compatible'
            }
    
    # 4. Group has space (REQUIRED)
    current_count = int(group.get('current_member_count') or 0)
    target_size = group.get('target_group_size')
    
    if target_size is not None:
        target_size = int(target_size)
        if current_count >= target_size:
            return {
                'score': 0,
                'eligible': False,
                'reasons': [f'Group is full: {current_count}/{target_size} members'],
                'compatibility_level': 'Not Compatible'
            }
    
    # If we made it here, all hard constraints passed!
    
    # =========================================================================
    # SOFT PREFERENCES (Scoring 0-100)
    # Using new personal_preferences fields from PR #7
    # =========================================================================
    
    # 1. Budget Fit (20 points)
    # Handle infinity for max budgets
    user_max_for_calc = user_budget_max if user_budget_max != float('inf') else user_budget_min + 2000
    group_max_for_calc = group_budget_max if group_budget_max != float('inf') else group_budget_min + 2000
    user_budget_mid = (user_budget_min + user_max_for_calc) / 2
    group_budget_mid = (group_budget_min + group_max_for_calc) / 2
    budget_diff = abs(user_budget_mid - group_budget_mid)
    
    if budget_diff <= 100:
        budget_score = 20
        reasons.append('Budget perfectly aligned')
    elif budget_diff <= 300:
        budget_score = 16
        reasons.append('Budget well aligned')
    elif budget_diff <= 500:
        budget_score = 12
        reasons.append('Budget reasonably aligned')
    else:
        budget_score = 8
        reasons.append('Budget somewhat aligned')
    
    score += budget_score
    
    # 2. Move-in Date Fit (15 points)
    if user_date and group_date:
        if date_diff <= 7:
            date_score = 15
            reasons.append('Move-in dates very close (within 1 week)')
        elif date_diff <= 14:
            date_score = 12
            reasons.append('Move-in dates close (within 2 weeks)')
        elif date_diff <= 30:
            date_score = 9
            reasons.append('Move-in dates aligned (within 1 month)')
        else:
            date_score = 6
    else:
        # No date data, give neutral score
        date_score = 8
    
    score += date_score
    
    # 3. Lease Preferences Match (15 points) - NEW from personal_preferences
    lease_score = 0
    
    # Lease type match (e.g., "month-to-month", "fixed", "sublet")
    user_lease_type = user_prefs.get('target_lease_type')
    group_lease_type = group.get('target_lease_type')
    
    if user_lease_type and group_lease_type:
        if user_lease_type.lower() == group_lease_type.lower():
            lease_score += 8
            reasons.append(f'Lease type match: {user_lease_type}')
        else:
            lease_score += 3
    else:
        lease_score += 4  # Neutral if not specified
    
    # Lease duration match
    user_lease_duration = user_prefs.get('target_lease_duration_months')
    group_lease_duration = group.get('target_lease_duration_months')
    
    if user_lease_duration and group_lease_duration:
        duration_diff = abs(int(user_lease_duration) - int(group_lease_duration))
        if duration_diff == 0:
            lease_score += 7
            reasons.append(f'Lease duration match: {user_lease_duration} months')
        elif duration_diff <= 3:
            lease_score += 5
            reasons.append('Lease duration close')
        else:
            lease_score += 2
    else:
        lease_score += 3  # Neutral if not specified
    
    score += lease_score
    
    # 4. Amenity Preferences Match (10 points) - NEW from personal_preferences
    amenity_score = 0
    
    # Furnished preference
    user_furnished = user_prefs.get('target_furnished')
    group_furnished = group.get('target_furnished')
    
    if user_furnished is not None and group_furnished is not None:
        if user_furnished == group_furnished:
            amenity_score += 5
            if user_furnished:
                reasons.append('Both prefer furnished')
            else:
                reasons.append('Both prefer unfurnished')
        else:
            amenity_score += 1  # Mismatch
    else:
        amenity_score += 2  # Neutral if not specified
    
    # Utilities included preference
    user_utilities = user_prefs.get('target_utilities_included')
    group_utilities = group.get('target_utilities_included')
    
    if user_utilities is not None and group_utilities is not None:
        if user_utilities == group_utilities:
            amenity_score += 5
            if user_utilities:
                reasons.append('Both prefer utilities included')
        else:
            amenity_score += 1  # Mismatch
    else:
        amenity_score += 2  # Neutral if not specified
    
    score += amenity_score
    
    # 5. Company/School Match (10 points)
    user_company = (user.get('company_name') or '').lower().strip()
    user_school = (user.get('school_name') or '').lower().strip()
    
    company_school_score = 0
    
    if user_company:
        company_school_score = 7
        reasons.append(f'Professional affiliation: {user.get("company_name")}')
    elif user_school:
        company_school_score = 7
        reasons.append(f'Academic affiliation: {user.get("school_name")}')
    else:
        company_school_score = 3
    
    # TODO: Bonus points if same company/school as group members
    
    score += company_school_score
    
    # 6. Verification Status (10 points)
    verification_status = user.get('verification_status') or 'unverified'
    
    if verification_status == 'admin_verified':
        verification_score = 10
        reasons.append('Admin verified user')
    elif verification_status == 'email_verified':
        verification_score = 7
        reasons.append('Email verified user')
    else:
        verification_score = 3
    
    score += verification_score
    
    # 7. Lifestyle Compatibility (20 points)
    user_lifestyle = user_prefs.get('lifestyle_preferences') or {}
    # Group lifestyle would need to be aggregated from members
    group_lifestyle = group.get('lifestyle_preferences') or {}
    
    lifestyle_score = calculate_lifestyle_compatibility(user_lifestyle, group_lifestyle)
    # Scale from 0-25 to 0-20
    lifestyle_score = int(lifestyle_score * 0.8)
    score += lifestyle_score
    
    if lifestyle_score >= 16:
        reasons.append('Excellent lifestyle match')
    elif lifestyle_score >= 12:
        reasons.append('Good lifestyle match')
    elif lifestyle_score >= 8:
        reasons.append('Moderate lifestyle match')
    
    # =========================================================================
    # FINAL RESULT
    # =========================================================================
    
    final_score = min(score, 100)  # Cap at 100
    compatibility_level = get_compatibility_level(final_score)
    
    return {
        'score': round(final_score, 2),
        'eligible': True,
        'reasons': reasons,
        'compatibility_level': compatibility_level
    }


# =============================================================================
# Helper Functions
# =============================================================================

def get_compatibility_level(score: float) -> str:
    """Convert numeric score to human-readable level."""
    if score >= 80:
        return 'Excellent Match'
    elif score >= 65:
        return 'Great Match'
    elif score >= 50:
        return 'Good Match'
    elif score >= 35:
        return 'Fair Match'
    else:
        return 'Poor Match'


def calculate_lifestyle_compatibility(
    user_lifestyle: Dict[str, Any],
    group_lifestyle: Dict[str, Any]
) -> float:
    """
    Compare lifestyle preferences between user and group.
    
    Returns score 0-25 based on compatibility of lifestyle attributes:
    - cleanliness, noise_level, smoking, pets, guests_frequency
    
    Args:
        user_lifestyle: User's lifestyle_preferences JSONB
        group_lifestyle: Aggregated group lifestyle preferences
        
    Returns:
        float: Score from 0-25
    """
    
    if not user_lifestyle or not group_lifestyle:
        return 12.5  # Neutral score if no data
    
    score = 0
    max_points = 25
    
    # Define compatibility rules for each attribute
    compatibility_rules = {
        'cleanliness': {
            ('very_clean', 'very_clean'): 5,
            ('very_clean', 'clean'): 4,
            ('clean', 'clean'): 5,
            ('clean', 'moderate'): 3,
            ('moderate', 'moderate'): 5,
            ('moderate', 'messy'): 2,
            ('messy', 'messy'): 5,
            # Opposite extremes = low score
            ('very_clean', 'messy'): 1,
        },
        'noise_level': {
            ('quiet', 'quiet'): 5,
            ('quiet', 'moderate'): 3,
            ('moderate', 'moderate'): 5,
            ('moderate', 'loud'): 3,
            ('loud', 'loud'): 5,
            ('quiet', 'loud'): 0,  # Incompatible
        },
        'smoking': {
            ('no_smoking', 'no_smoking'): 5,
            ('no_smoking', 'outdoor_only'): 3,
            ('outdoor_only', 'outdoor_only'): 5,
            ('smoking_ok', 'smoking_ok'): 5,
            ('no_smoking', 'smoking_ok'): 0,  # Deal-breaker
        },
        'pets': {
            ('no_pets', 'no_pets'): 5,
            ('no_pets', 'pets_ok'): 2,
            ('pets_ok', 'pets_ok'): 5,
        },
        'guests_frequency': {
            ('rarely', 'rarely'): 3,
            ('rarely', 'occasionally'): 2,
            ('occasionally', 'occasionally'): 3,
            ('occasionally', 'frequently'): 2,
            ('frequently', 'frequently'): 3,
            ('rarely', 'frequently'): 1,
        }
    }
    
    # Calculate compatibility for each attribute
    for attribute, rules in compatibility_rules.items():
        user_val = user_lifestyle.get(attribute)
        group_val = group_lifestyle.get(attribute)
        
        if user_val and group_val:
            pair = (user_val, group_val)
            if pair in rules:
                score += rules[pair]
            elif (group_val, user_val) in rules:  # Check reverse pair
                score += rules[(group_val, user_val)]
    
    # Normalize to 0-25
    return min(score, max_points)


def aggregate_group_lifestyle(members_preferences: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate lifestyle preferences from multiple group members.
    Uses MOST RESTRICTIVE approach (highest standards win).
    
    Args:
        members_preferences: List of lifestyle_preferences dicts from each member
        
    Returns:
        Dict with aggregated lifestyle preferences
    """
    
    if not members_preferences:
        return {}
    
    aggregated = {}
    
    # Cleanliness: Take highest standard
    cleanliness_order = ['messy', 'moderate', 'clean', 'very_clean']
    all_cleanliness = [
        lp.get('cleanliness') 
        for lp in members_preferences 
        if lp.get('cleanliness')
    ]
    if all_cleanliness:
        aggregated['cleanliness'] = max(
            all_cleanliness, 
            key=lambda x: cleanliness_order.index(x) if x in cleanliness_order else 0
        )
    
    # Noise level: Take quietest
    noise_order = ['loud', 'moderate', 'quiet']
    all_noise = [
        lp.get('noise_level') 
        for lp in members_preferences 
        if lp.get('noise_level')
    ]
    if all_noise:
        aggregated['noise_level'] = max(
            all_noise, 
            key=lambda x: noise_order.index(x) if x in noise_order else 0
        )
    
    # Smoking: If anyone says no_smoking, group is no_smoking
    all_smoking = [lp.get('smoking') for lp in members_preferences if lp.get('smoking')]
    if 'no_smoking' in all_smoking:
        aggregated['smoking'] = 'no_smoking'
    elif 'outdoor_only' in all_smoking:
        aggregated['smoking'] = 'outdoor_only'
    elif all_smoking:
        aggregated['smoking'] = all_smoking[0]
    
    # Pets: If anyone says no_pets, group is no_pets
    all_pets = [lp.get('pets') for lp in members_preferences if lp.get('pets')]
    if 'no_pets' in all_pets:
        aggregated['pets'] = 'no_pets'
    elif all_pets:
        aggregated['pets'] = 'pets_ok'
    
    # Guests: Take most restrictive
    guests_order = ['frequently', 'occasionally', 'rarely']
    all_guests = [
        lp.get('guests_frequency') 
        for lp in members_preferences 
        if lp.get('guests_frequency')
    ]
    if all_guests:
        aggregated['guests_frequency'] = max(
            all_guests, 
            key=lambda x: guests_order.index(x) if x in guests_order else 0
        )
    
    return aggregated


# =============================================================================
# Database Integration Functions
# =============================================================================

async def find_compatible_groups(
    user_id: str,
    user_prefs: Dict[str, Any],
    min_score: int = 50,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Find groups compatible with a user's preferences.
    
    This function fetches open groups from the database, scores them,
    and returns the top matches above the minimum score threshold.
    
    Args:
        user_id: User's ID
        user_prefs: User's preferences dict
        min_score: Minimum compatibility score (0-100)
        limit: Max results to return
        
    Returns:
        List of groups with compatibility scores, sorted by score DESC
    """
    
    from app.dependencies.supabase import get_admin_client
    
    supabase = get_admin_client()
    
    # 1. Get user details
    user_response = supabase.table("users").select("*").eq("id", user_id).execute()
    if not user_response.data:
        raise ValueError(f"User not found: {user_id}")
    user = user_response.data[0]
    
    target_city = user_prefs.get('target_city')
    if not target_city:
        return []
    
    # 2. Get open groups in target city (exclude solo groups)
    # Open = status='active' AND (is_solo IS NULL OR is_solo=false)
    groups_response = supabase.table("roommate_groups")\
        .select("*, group_members(user_id, status)")\
        .eq("status", "active")\
        .ilike("target_city", target_city)\
        .execute()
    
    # Filter out solo groups (is_solo = True)
    if groups_response.data:
        groups_response.data = [g for g in groups_response.data if g.get('is_solo') != True]
    
    if not groups_response.data:
        return []
    
    # 3. Filter to groups with open spots and not already a member
    open_groups = []
    for group in groups_response.data:
        # Check if user is already a member
        members = group.get('group_members', []) or []
        member_ids = [m['user_id'] for m in members if m.get('status') == 'accepted']
        if user_id in member_ids:
            continue  # Skip groups user is already in
        
        # Check if group has space
        current_count = group.get('current_member_count', len(member_ids))
        target_size = group.get('target_group_size')
        
        if target_size is None or current_count < target_size:
            open_groups.append(group)
    
    # 4. Score each group
    scored_groups = []
    for group in open_groups:
        compatibility = calculate_user_group_compatibility(user, user_prefs, group)
        
        if compatibility['eligible'] and compatibility['score'] >= min_score:
            group['compatibility'] = compatibility
            scored_groups.append(group)
    
    # 5. Sort by score (highest first)
    scored_groups.sort(key=lambda g: g['compatibility']['score'], reverse=True)
    
    # 6. Return top results
    return scored_groups[:limit]


# Export public API
__all__ = [
    'calculate_user_group_compatibility',
    'calculate_lifestyle_compatibility',
    'aggregate_group_lifestyle',
    'find_compatible_groups',
    'SCORING_WEIGHTS',
    'DATE_FLEXIBILITY_DAYS'
]
