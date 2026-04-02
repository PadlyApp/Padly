"""
User-Group Matching - Compatibility scoring between users and roommate groups.
Score: 0-100 pts. Weights: budget(20), date(15), lease(15),
company(10), verification(10), lifestyle(30).
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
from app.services.preferences_contract import (
    lease_types_compatible,
)

# Scoring weights (100 pts total)
SCORING_WEIGHTS = {
    'budget_fit': 20,           # Budget range alignment
    'date_fit': 15,             # Move-in date proximity
    'lease_preferences': 15,    # Lease type/duration match
    'company_school_match': 10, # Same company/school
    'verification': 10,         # User verification status
    'lifestyle': 30             # UI soft constraints compatibility
}

DATE_FLEXIBILITY_DAYS = 60  # Max days apart for date matching


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def calculate_user_group_compatibility(
    user: Dict[str, Any],
    user_prefs: Dict[str, Any],
    group: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate compatibility between user and group. Returns score 0-100."""
    
    score = 0
    reasons = []
    
    # --- HARD CONSTRAINTS (all must pass) ---
    
    # City must match
    user_city = str(user_prefs.get('target_city') or '').lower().strip()
    group_city = str(group.get('target_city') or '').lower().strip()
    
    if not user_city or not group_city or user_city != group_city:
        return {
            'score': 0,
            'eligible': False,
            'reasons': [f'City mismatch: user wants {user_city}, group in {group_city}'],
            'compatibility_level': 'Not Compatible'
        }

    # Gender policy hard filter.
    user_lifestyle = user_prefs.get('lifestyle_preferences') or {}
    user_gender_policy = _norm(user_prefs.get('gender_policy') or user_lifestyle.get('gender_policy') or 'mixed_ok')
    if user_gender_policy == 'same_gender_only':
        user_gender = _norm(user_lifestyle.get('gender_identity'))
        if not user_gender:
            return {
                'score': 0,
                'eligible': False,
                'reasons': ['Gender policy is same_gender_only but user gender_identity is missing'],
                'compatibility_level': 'Not Compatible'
            }

        group_member_genders = [_norm(g) for g in (group.get('_member_genders') or []) if _norm(g)]
        if any(g != user_gender for g in group_member_genders):
            return {
                'score': 0,
                'eligible': False,
                'reasons': ['Group has mixed gender identities, but your policy is same_gender_only'],
                'compatibility_level': 'Not Compatible'
            }
    
    # Budget must overlap
    user_budget_min = float(user_prefs.get('budget_min') or 0)
    user_budget_max = float(user_prefs.get('budget_max') or float('inf'))
    group_budget_min = float(group.get('budget_per_person_min') or 0)
    group_budget_max = float(group.get('budget_per_person_max') or float('inf'))
    overlaps = user_budget_max >= group_budget_min and user_budget_min <= group_budget_max
    
    if not overlaps:
        return {
            'score': 0,
            'eligible': False,
            'reasons': [f'Budget ranges don\'t overlap: user ${user_budget_min}-${user_budget_max}, group ${group_budget_min}-${group_budget_max}'],
            'compatibility_level': 'Not Compatible'
        }
    
    # Move-in date within ±60 days
    user_date = user_prefs.get('move_in_date')
    group_date = group.get('target_move_in_date')
    
    if user_date and group_date:
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
    
    # Group must have space
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
    
    # --- SOFT PREFERENCES (scoring 0-100) ---
    
    # Budget Fit (20 pts)
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
    
    # Move-in Date Fit (15 pts)
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
        date_score = 8
    score += date_score
    
    # Lease Preferences (15 pts)
    lease_score = 0
    user_lease_type = user_prefs.get('target_lease_type')
    group_lease_type = group.get('target_lease_type')
    
    if user_lease_type and group_lease_type:
        if lease_types_compatible(user_lease_type, group_lease_type):
            lease_score += 8
            reasons.append(f'Lease type compatible: {user_lease_type}')
        else:
            lease_score += 3
    else:
        lease_score += 4
    
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
        lease_score += 3
    score += lease_score
    
    # Company/School Match (10 pts)
    user_company = (user.get('company_name') or '').lower().strip()
    user_school = (user.get('school_name') or '').lower().strip()
    
    if user_company:
        company_school_score = 7
        reasons.append(f'Professional affiliation: {user.get("company_name")}')
    elif user_school:
        company_school_score = 7
        reasons.append(f'Academic affiliation: {user.get("school_name")}')
    else:
        company_school_score = 3
    score += company_school_score
    
    # Verification Status (10 pts)
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
    
    # Lifestyle Compatibility (scaled to 30 pts, using UI soft fields only)
    group_lifestyle = group.get('lifestyle_preferences') or {}

    raw_lifestyle = calculate_lifestyle_compatibility(
        user_lifestyle,
        group_lifestyle,
        user_prefs=user_prefs,
        group=group,
    )  # 0-20
    lifestyle_score = int(round((raw_lifestyle / 20.0) * SCORING_WEIGHTS['lifestyle']))
    score += lifestyle_score
    
    if lifestyle_score >= 24:
        reasons.append('Excellent lifestyle match')
    elif lifestyle_score >= 18:
        reasons.append('Good lifestyle match')
    elif lifestyle_score >= 12:
        reasons.append('Moderate lifestyle match')
    
    # --- FINAL RESULT ---
    final_score = min(score, 100)
    compatibility_level = get_compatibility_level(final_score)
    
    return {
        'score': round(final_score, 2),
        'eligible': True,
        'reasons': reasons,
        'compatibility_level': compatibility_level
    }


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
    return 'Poor Match'


def calculate_lifestyle_compatibility(
    user_lifestyle: Dict,
    group_lifestyle: Dict,
    user_prefs: Optional[Dict[str, Any]] = None,
    group: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Compare lifestyle and group-soft preferences using the UI contract fields:
    preferred_neighborhoods, cleanliness_level, social_preference,
    cooking_frequency, gender_identity, amenity_priorities,
    building_type_preferences, target_house_rules.
    Returns 0-20 score.
    """
    if not user_lifestyle and not group_lifestyle:
        return 10.0  # Neutral score

    score = 0.0

    # Cleanliness (0-3)
    cleanliness_order = ['low', 'moderate', 'high']
    user_clean = _norm(user_lifestyle.get('cleanliness_level'))
    group_clean = _norm(group_lifestyle.get('cleanliness_level'))
    if user_clean and group_clean and user_clean in cleanliness_order and group_clean in cleanliness_order:
        diff = abs(cleanliness_order.index(user_clean) - cleanliness_order.index(group_clean))
        score += 3.0 if diff == 0 else (1.5 if diff == 1 else 0.0)
    else:
        score += 1.5

    # Quiet vs social (0-3)
    social_order = ['quiet', 'balanced', 'social']
    user_social = _norm(user_lifestyle.get('social_preference'))
    group_social = _norm(group_lifestyle.get('social_preference'))
    if user_social and group_social and user_social in social_order and group_social in social_order:
        diff = abs(social_order.index(user_social) - social_order.index(group_social))
        score += 3.0 if diff == 0 else (1.5 if diff == 1 else 0.0)
    else:
        score += 1.5

    # Cooking frequency (0-3)
    cooking_order = ['rarely', 'sometimes', 'often']
    user_cook = _norm(user_lifestyle.get('cooking_frequency'))
    group_cook = _norm(group_lifestyle.get('cooking_frequency'))
    if user_cook and group_cook and user_cook in cooking_order and group_cook in cooking_order:
        diff = abs(cooking_order.index(user_cook) - cooking_order.index(group_cook))
        score += 3.0 if diff == 0 else (1.5 if diff == 1 else 0.0)
    else:
        score += 1.5

    # Gender identity soft alignment (0-2)
    user_gender = _norm(user_lifestyle.get('gender_identity'))
    group_gender = _norm(group_lifestyle.get('gender_identity'))
    if user_gender and group_gender:
        score += 2.0 if user_gender == group_gender else 0.0
    else:
        score += 1.0

    # Neighborhood overlap (0-3)
    user_neighborhoods = { _norm(v) for v in ((user_prefs or {}).get('preferred_neighborhoods') or []) if _norm(v) }
    group_neighborhoods = { _norm(v) for v in ((group or {}).get('_preferred_neighborhoods') or []) if _norm(v) }
    if user_neighborhoods and group_neighborhoods:
        overlap = len(user_neighborhoods.intersection(group_neighborhoods))
        score += 3.0 if overlap >= 2 else (2.0 if overlap == 1 else 0.0)
    else:
        score += 1.5

    # Amenity priorities overlap (0-3)
    user_amenities = { _norm(v) for v in (user_lifestyle.get('amenity_priorities') or []) if _norm(v) }
    group_amenities = { _norm(v) for v in (group_lifestyle.get('amenity_priorities') or []) if _norm(v) }
    if user_amenities and group_amenities:
        overlap = len(user_amenities.intersection(group_amenities))
        score += 3.0 if overlap >= 2 else (1.5 if overlap == 1 else 0.0)
    else:
        score += 1.5

    # Building type preference overlap (0-2)
    user_building_types = { _norm(v) for v in (user_lifestyle.get('building_type_preferences') or []) if _norm(v) }
    group_building_types = { _norm(v) for v in (group_lifestyle.get('building_type_preferences') or []) if _norm(v) }
    if user_building_types and group_building_types:
        score += 2.0 if user_building_types.intersection(group_building_types) else 0.0
    else:
        score += 1.0

    # House rules alignment (0-1)
    user_rules = _norm((user_prefs or {}).get('target_house_rules'))
    group_rules = _norm((group or {}).get('target_house_rules'))
    if user_rules and group_rules:
        if user_rules == group_rules:
            score += 1.0
        else:
            conflicts = 0
            if 'no smoking' in group_rules and 'smoking' in user_rules and 'no smoking' not in user_rules:
                conflicts += 1
            if 'no pets' in group_rules and 'pet' in user_rules and 'no pet' not in user_rules:
                conflicts += 1
            if 'no parties' in group_rules and 'parties' in user_rules and 'no parties' not in user_rules:
                conflicts += 1
            score += 0.0 if conflicts else 0.5
    else:
        score += 0.5

    return min(score, 20.0)


def aggregate_group_lifestyle(members_preferences: List[Dict]) -> Dict:
    """Aggregate UI soft-constraint lifestyle fields from group members."""
    
    if not members_preferences:
        return {}
    
    aggregated = {}
    
    # Cleanliness: median tendency on UI scale.
    cleanliness_order = ['low', 'moderate', 'high']
    all_cleanliness = [
        _norm(lp.get('cleanliness_level') or lp.get('cleanliness'))
        for lp in members_preferences
        if _norm(lp.get('cleanliness_level') or lp.get('cleanliness')) in cleanliness_order
    ]
    if all_cleanliness:
        sorted_vals = sorted(all_cleanliness, key=lambda x: cleanliness_order.index(x))
        median = sorted_vals[len(sorted_vals) // 2]
        aggregated['cleanliness_level'] = median
        # Backward compatibility for older readers.
        aggregated['cleanliness'] = median

    # Social preference: middle-ground consensus (quiet/balanced/social)
    social_order = ['quiet', 'balanced', 'social']
    all_social = [lp.get('social_preference') for lp in members_preferences if lp.get('social_preference')]
    if all_social:
        all_social = [s for s in all_social if s in social_order]
        if all_social:
            all_social_sorted = sorted(all_social, key=lambda x: social_order.index(x))
            aggregated['social_preference'] = all_social_sorted[len(all_social_sorted) // 2]

    # Cooking frequency: median tendency.
    cooking_order = ['rarely', 'sometimes', 'often']
    all_cooking = [lp.get('cooking_frequency') for lp in members_preferences if lp.get('cooking_frequency')]
    if all_cooking:
        all_cooking = [c for c in all_cooking if c in cooking_order]
        if all_cooking:
            all_cooking_sorted = sorted(all_cooking, key=lambda x: cooking_order.index(x))
            aggregated['cooking_frequency'] = all_cooking_sorted[len(all_cooking_sorted) // 2]

    # Gender identity: majority vote when present.
    all_genders = [_norm(lp.get('gender_identity')) for lp in members_preferences if _norm(lp.get('gender_identity'))]
    if all_genders:
        counts: Dict[str, int] = {}
        for g in all_genders:
            counts[g] = counts.get(g, 0) + 1
        aggregated['gender_identity'] = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[0][0]

    # Amenity / building preferences: majority picks.
    amenity_counter: Dict[str, int] = {}
    building_counter: Dict[str, int] = {}
    for lp in members_preferences:
        for amenity in (lp.get('amenity_priorities') or []):
            key = _norm(amenity)
            if key:
                amenity_counter[key] = amenity_counter.get(key, 0) + 1
        for btype in (lp.get('building_type_preferences') or []):
            key = _norm(btype)
            if key:
                building_counter[key] = building_counter.get(key, 0) + 1

    if amenity_counter:
        aggregated['amenity_priorities'] = [
            k for k, _ in sorted(amenity_counter.items(), key=lambda kv: kv[1], reverse=True)[:3]
        ]
    if building_counter:
        aggregated['building_type_preferences'] = [
            k for k, _ in sorted(building_counter.items(), key=lambda kv: kv[1], reverse=True)[:3]
        ]
    
    return aggregated


# --- DATABASE INTEGRATION ---

async def find_compatible_groups(
    user_id: str,
    user_prefs: Dict,
    min_score: int = 50,
    limit: int = 20
) -> List[Dict]:
    """Find groups compatible with user's preferences. Returns top matches sorted by score."""
    
    from app.dependencies.supabase import get_admin_client
    
    supabase = get_admin_client()
    
    # Get user details
    user_response = supabase.table("users").select("*").eq("id", user_id).execute()
    if not user_response.data:
        raise ValueError(f"User not found: {user_id}")
    user = user_response.data[0]
    
    target_city = user_prefs.get('target_city')
    if not target_city:
        return []
    
    # Get open groups in target city (exclude solo groups)
    groups_response = supabase.table("roommate_groups")\
        .select("*, group_members(user_id, status)")\
        .eq("status", "active")\
        .ilike("target_city", target_city)\
        .execute()
    
    if groups_response.data:
        groups_response.data = [g for g in groups_response.data if g.get('is_solo') != True]
    
    if not groups_response.data:
        return []
    
    # Filter to groups with open spots and not already a member
    open_groups = []
    for group in groups_response.data:
        members = group.get('group_members', []) or []
        member_ids = [m['user_id'] for m in members if m.get('status') == 'accepted']
        if user_id in member_ids:
            continue
        
        current_count = group.get('current_member_count', len(member_ids))
        target_size = group.get('target_group_size')
        
        if target_size is None or current_count < target_size:
            open_groups.append(group)
    
    # Score each group
    scored_groups = []
    for group in open_groups:
        members = group.get('group_members', []) or []
        member_ids = [m['user_id'] for m in members if m.get('status') == 'accepted' and m.get('user_id')]

        if member_ids:
            member_prefs_resp = supabase.table("personal_preferences")\
                .select("user_id, lifestyle_preferences, preferred_neighborhoods, gender_policy")\
                .in_("user_id", member_ids)\
                .execute()
            member_prefs_rows = member_prefs_resp.data or []

            member_lifestyles = [row.get('lifestyle_preferences') or {} for row in member_prefs_rows]
            group['lifestyle_preferences'] = aggregate_group_lifestyle(member_lifestyles)

            group['_preferred_neighborhoods'] = list({
                n
                for row in member_prefs_rows
                for n in (row.get('preferred_neighborhoods') or [])
                if _norm(n)
            })
            group['_member_genders'] = [
                (row.get('lifestyle_preferences') or {}).get('gender_identity')
                for row in member_prefs_rows
                if (row.get('lifestyle_preferences') or {}).get('gender_identity')
            ]

            if not group.get('gender_policy'):
                policies = [row.get('gender_policy') for row in member_prefs_rows if row.get('gender_policy')]
                if 'same_gender_only' in policies:
                    group['gender_policy'] = 'same_gender_only'
                elif policies:
                    group['gender_policy'] = 'mixed_ok'

        compatibility = calculate_user_group_compatibility(user, user_prefs, group)
        
        if compatibility['eligible'] and compatibility['score'] >= min_score:
            group['compatibility'] = compatibility
            scored_groups.append(group)
    
    # Sort by score and return
    scored_groups.sort(key=lambda g: g['compatibility']['score'], reverse=True)
    return scored_groups[:limit]


__all__ = [
    'calculate_user_group_compatibility',
    'calculate_lifestyle_compatibility', 
    'aggregate_group_lifestyle',
    'find_compatible_groups',
    'SCORING_WEIGHTS'
]
