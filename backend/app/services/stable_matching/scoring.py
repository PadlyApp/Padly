"""
Scoring & Preference Lists for Group↔Listing matching.
Hard constraints: city, state, budget, bedrooms, date (±60d), lease type/duration,
bathrooms minimum, deposit cap, furnished(required).
Soft preferences (frontend UI contract): preferred_neighborhoods, amenity_priorities,
building_type_preferences, target_house_rules.
"""

from typing import Dict, List, Tuple, Any, Optional, Set
from datetime import datetime
import re
import logging
from app.services.location_matching import locations_match, normalize_city_name, normalize_state
from app.services.preferences_contract import lease_types_compatible

logger = logging.getLogger(__name__)

# Weights (100 pts total)
GROUP_SCORING_WEIGHTS = {
    "preferred_neighborhoods": 25,
    "amenity_priorities": 25,
    "building_type_preferences": 25,
    "target_house_rules": 25,
}
LISTING_SCORING_WEIGHTS = {"budget": 40, "deposit": 30, "preference_match": 30}
MAX_SCORE = 100

# --- HARD CONSTRAINTS ---

def check_hard_constraints(group: Dict, listing: Dict) -> Tuple[bool, Optional[str]]:
    """Check all hard constraints. Returns (passes, rejection_reason)."""

    group_city = normalize_city_name(group.get("target_city"))
    listing_city = normalize_city_name(listing.get("city"))
    group_state = normalize_state(group.get("target_state_province"))
    listing_state = normalize_state(listing.get("state_province"))
    if not locations_match(
        target_city=group.get("target_city"),
        listing_city=listing.get("city"),
        target_state=group.get("target_state_province"),
        listing_state=listing.get("state_province"),
        target_country=group.get("target_country", "USA"),
        listing_country=listing.get("country", "USA"),
    ):
        if group_city != listing_city:
            return False, f"city_mismatch_{group_city}_vs_{listing_city}"
        return False, f"state_mismatch_{group_state}_vs_{listing_state}"
    
    # Budget range — compare per-person budget against price per room
    min_budget = group.get("budget_per_person_min")
    max_budget = group.get("budget_per_person_max")
    if min_budget is None:
        min_budget = group.get("budget_min", 0)
    if max_budget is None:
        max_budget = group.get("budget_max", 0)
    # Use price_per_room if available, otherwise derive from total / bedrooms
    price_per_room = listing.get('price_per_room')
    if not price_per_room:
        bedrooms = listing.get('number_of_bedrooms') or 1
        price_per_room = listing.get('price_per_month', 0) / bedrooms
    if not (min_budget <= price_per_room <= max_budget + 100):
        return False, f"budget_mismatch_${price_per_room:.0f}_per_room_not_in_[${min_budget},${max_budget}]"
    
    # Bedroom count — listing must have at least 1 bedroom
    if listing.get('number_of_bedrooms', 0) < 1:
        return False, f"insufficient_bedrooms"
    
    # Move-in date (±60 days)
    group_date = group.get("target_move_in_date") or group.get("move_in_date")
    listing_date = listing.get('available_from')
    if group_date and listing_date:
        if isinstance(group_date, str):
            group_date = datetime.fromisoformat(group_date.replace('Z', '+00:00')).date()
        if isinstance(listing_date, str):
            listing_date = datetime.fromisoformat(listing_date.replace('Z', '+00:00')).date()
        if abs((listing_date - group_date).days) > 60:
            return False, f"date_mismatch"
    
    # Lease type/duration (if specified)
    group_lease_type = group.get('target_lease_type')
    listing_lease_type = listing.get('lease_type')
    if not lease_types_compatible(group_lease_type, listing_lease_type):
        return False, f"lease_type_mismatch"
    
    group_duration = group.get('target_lease_duration_months')
    listing_duration = listing.get('lease_duration_months')
    if group_duration is not None and listing_duration is not None and group_duration != listing_duration:
        return False, f"lease_duration_mismatch"

    # Bathroom preference as hard requirement when present.
    group_bathrooms = group.get('target_bathrooms')
    listing_bathrooms = listing.get('number_of_bathrooms')
    if group_bathrooms is not None and listing_bathrooms is not None:
        try:
            if float(listing_bathrooms) < float(group_bathrooms):
                return False, "bathroom_requirement_not_met"
        except (TypeError, ValueError):
            return False, "invalid_bathroom_data"

    # Maximum deposit as hard requirement when present.
    max_deposit = group.get('target_deposit_amount')
    listing_deposit = listing.get('deposit_amount')
    if max_deposit is not None and listing_deposit is not None:
        try:
            if float(listing_deposit) > float(max_deposit):
                return False, "deposit_requirement_not_met"
        except (TypeError, ValueError):
            return False, "invalid_deposit_data"

    # Furnished requirement: only hard when explicitly required.
    furnished_pref = (group.get('furnished_preference') or '').strip().lower()
    furnished_is_hard = bool(group.get('furnished_is_hard')) or furnished_pref == 'required'
    if furnished_is_hard and group.get('target_furnished') is True:
        listing_furnished = listing.get('furnished')
        if isinstance(listing_furnished, str):
            listing_furnished = listing_furnished.lower() in ['true', 't', '1', 'yes']
        if listing_furnished is not True:
            return False, "furnished_requirement_not_met"
    
    return True, None


# --- SOFT PREFERENCE SCORING (frontend UI fields) ---

def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return _norm(value) in {"1", "true", "t", "yes", "y", "on"}


def _build_norm_set(values: Any) -> Set[str]:
    if not isinstance(values, list):
        return set()
    out: Set[str] = set()
    for value in values:
        token = _norm(value)
        if token:
            out.add(token)
    return out


def _extract_listing_neighborhood_tokens(listing: Dict[str, Any]) -> Set[str]:
    tokens: Set[str] = set()
    for key in ("neighborhood", "neighbourhood", "district", "area", "address_line_2"):
        token = _norm(listing.get(key))
        if token:
            tokens.add(token)
    return tokens


_AMENITY_ALIASES = {
    "laundry": "laundry",
    "parking": "parking",
    "gym": "gym",
    "fitness_center": "gym",
    "air_conditioning": "ac",
    "airconditioner": "ac",
    "a_c": "ac",
    "ac": "ac",
    "dishwasher": "dishwasher",
    "elevator": "elevator",
    "doorman": "doorman",
    "bike_storage": "bike_storage",
    "bike_room": "bike_storage",
    "bike_parking": "bike_storage",
}


def _amenity_alias(value: Any) -> Optional[str]:
    token = _norm(value).replace("-", "_").replace(" ", "_").replace("/", "_")
    if not token:
        return None
    return _AMENITY_ALIASES.get(token, token if token in _AMENITY_ALIASES.values() else None)


def _extract_listing_amenity_tokens(listing: Dict[str, Any]) -> Set[str]:
    tokens: Set[str] = set()
    amenities = listing.get("amenities")
    if isinstance(amenities, dict):
        for raw_key, raw_val in amenities.items():
            alias = _amenity_alias(raw_key)
            if alias and _is_truthy(raw_val):
                tokens.add(alias)
    elif isinstance(amenities, list):
        for item in amenities:
            alias = _amenity_alias(item)
            if alias:
                tokens.add(alias)
    elif isinstance(amenities, str):
        for part in re.split(r"[^a-zA-Z0-9_]+", amenities):
            alias = _amenity_alias(part)
            if alias:
                tokens.add(alias)

    # Fallback for common top-level booleans when amenities blob is sparse.
    if _is_truthy(listing.get("parking")):
        tokens.add("parking")
    if _is_truthy(listing.get("air_conditioning")) or _is_truthy(listing.get("ac")):
        tokens.add("ac")
    if _is_truthy(listing.get("dishwasher")):
        tokens.add("dishwasher")
    if _is_truthy(listing.get("elevator")):
        tokens.add("elevator")

    return tokens


def _normalize_building_type(value: Any) -> str:
    raw = _norm(value).replace("-", "_").replace(" ", "_")
    aliases = {
        "single_family": "house",
        "single_family_home": "house",
        "condominium": "condo",
        "private_room": "apartment",
        "studio": "apartment",
    }
    return aliases.get(raw, raw)


def calculate_neighborhood_score(group: Dict[str, Any], listing: Dict[str, Any]) -> float:
    """Score preferred_neighborhoods vs listing neighborhood metadata."""
    weight = float(GROUP_SCORING_WEIGHTS["preferred_neighborhoods"])
    preferred = _build_norm_set(group.get("preferred_neighborhoods") or [])
    if not preferred:
        return weight / 2.0

    listing_tokens = _extract_listing_neighborhood_tokens(listing)
    if not listing_tokens:
        return weight / 2.0

    if preferred.intersection(listing_tokens):
        return weight

    # Loose partial match to handle formatting differences.
    for pref in preferred:
        for token in listing_tokens:
            if pref in token or token in pref:
                return weight * 0.75
    return weight * 0.25


def calculate_amenity_score(group: Dict[str, Any], listing: Dict[str, Any]) -> float:
    """Score overlap of lifestyle.amenity_priorities against listing amenities."""
    weight = float(GROUP_SCORING_WEIGHTS["amenity_priorities"])
    lifestyle = group.get("lifestyle_preferences") or {}
    desired = _build_norm_set(lifestyle.get("amenity_priorities") or [])
    if not desired:
        return weight / 2.0

    offered = _extract_listing_amenity_tokens(listing)
    if not offered:
        return weight / 2.0

    overlap = len(desired.intersection(offered))
    if overlap <= 0:
        return 0.0
    return round(weight * (overlap / max(1, len(desired))), 2)


def calculate_building_type_score(group: Dict[str, Any], listing: Dict[str, Any]) -> float:
    """Score lifestyle.building_type_preferences against listing.property_type."""
    weight = float(GROUP_SCORING_WEIGHTS["building_type_preferences"])
    lifestyle = group.get("lifestyle_preferences") or {}
    desired = {
        _normalize_building_type(v)
        for v in (lifestyle.get("building_type_preferences") or [])
        if _normalize_building_type(v)
    }
    if not desired:
        return weight / 2.0

    listing_type = _normalize_building_type(listing.get("property_type"))
    if not listing_type:
        return weight / 2.0
    if listing_type in desired:
        return weight
    return weight * 0.2


def calculate_house_rules_score(group: Dict, listing: Dict) -> float:
    """Score target_house_rules note vs listing house_rules note."""
    weight = float(GROUP_SCORING_WEIGHTS["target_house_rules"])
    group_rules = _norm(group.get("target_house_rules"))
    listing_rules = _norm(listing.get("house_rules"))
    
    if not group_rules or not listing_rules:
        return weight / 2.0
    if group_rules == listing_rules:
        return weight
    
    conflicts = 0
    if ("no smoking" in listing_rules or "smoke free" in listing_rules) and (
        "smoking allowed" in group_rules or "smoking ok" in group_rules
    ):
        conflicts += 1
    if ("no pets" in listing_rules or "pet free" in listing_rules) and (
        "pets allowed" in group_rules or "pets ok" in group_rules
    ):
        conflicts += 1
    if ("no parties" in listing_rules or "quiet hours" in listing_rules) and (
        "parties allowed" in group_rules or "party friendly" in group_rules
    ):
        conflicts += 1
    
    if conflicts > 0:
        return 0.0

    # No explicit conflict but text differs.
    shared_keywords = 0
    for kw in ("smoking", "pet", "party", "quiet", "guest", "clean"):
        if kw in group_rules and kw in listing_rules:
            shared_keywords += 1
    if shared_keywords > 0:
        return weight
    return weight * 0.75


# --- OVERALL SCORING ---

def calculate_group_score(group: Dict[str, Any], listing: Dict[str, Any]) -> float:
    """Calculate how much a group likes a listing (0-100)."""
    # Check hard constraints first
    passes, reason = check_hard_constraints(group, listing)
    if not passes:
        logger.debug(f"Group {group.get('id')} rejected listing {listing.get('id')}: {reason}")
        return 0.0
    
    # Soft preference scoring from frontend UI soft fields only.
    score = (
        calculate_neighborhood_score(group, listing) +
        calculate_amenity_score(group, listing) +
        calculate_building_type_score(group, listing) +
        calculate_house_rules_score(group, listing)
    )
    
    score = max(0.0, min(MAX_SCORE, score))
    logger.debug(f"Group {group.get('id')} scores listing {listing.get('id')}: {score:.2f}/100")
    return score


def calculate_listing_score(listing: Dict[str, Any], group: Dict[str, Any]) -> float:
    """Calculate how much a listing likes a group (0-100)."""
    score = 0.0
    
    # Budget score (40 pts) - prefer groups with higher budgets
    price_per_room = listing.get('price_per_room')
    if not price_per_room:
        bedrooms = listing.get('number_of_bedrooms') or 1
        price_per_room = listing.get('price_per_month', 0) / bedrooms
    group_budget = group.get('budget_per_person_max', 0)
    budget_ratio = group_budget / price_per_room if price_per_room > 0 and group_budget > 0 else 1.0
    
    if budget_ratio >= 1.5: score += 40
    elif budget_ratio >= 1.3: score += 35
    elif budget_ratio >= 1.15: score += 30
    elif budget_ratio >= 1.05: score += 25
    elif budget_ratio >= 1.0: score += 20
    elif budget_ratio >= 0.95: score += 15
    else: score += 5
    
    # Deposit score (30 pts) - prefer groups willing to pay higher deposits
    listing_deposit = listing.get('deposit_amount', 0)
    group_deposit = group.get('target_deposit_amount', 0)
    deposit_ratio = 1.0
    
    if listing_deposit and group_deposit:
        deposit_ratio = group_deposit / listing_deposit
        if deposit_ratio >= 1.5: score += 30
        elif deposit_ratio >= 1.2: score += 25
        elif deposit_ratio >= 1.0: score += 20
        elif deposit_ratio >= 0.8: score += 15
        else: score += 10
    else:
        score += 20 if not listing_deposit else 15
    
    # Preference match (30 pts) - groups that want what listing offers
    if group.get('target_furnished') is not None:
        if listing.get('furnished') == group.get('target_furnished'):
            score += 10
    
    if group.get('target_utilities_included') is not None:
        if listing.get('utilities_included') == group.get('target_utilities_included'):
            score += 10
    
    # House rules compatibility (10 pts)
    listing_rules = listing.get('house_rules', {})
    group_rules = group.get('target_house_rules', {})
    if isinstance(listing_rules, dict) and isinstance(group_rules, dict):
        conflicts = sum(1 for rule in ['smoking_allowed', 'pets_allowed', 'parties_allowed']
                       if group_rules.get(rule) and not listing_rules.get(rule, True))
        score += max(0, 10 - (conflicts * 3.33))
    
    logger.debug(f"Listing {listing.get('id')} scores group {group.get('id')}: {score:.1f}")
    return round(score, 1)


# --- RANKING & PREFERENCE LISTS ---

def rank_listings_for_group(group: Dict[str, Any], feasible_listings: List[Dict[str, Any]]) -> List[Tuple[str, int, float]]:
    """Rank all feasible listings for a group. Returns [(listing_id, rank, score)]."""
    scored = []
    for listing in feasible_listings:
        score = calculate_group_score(group, listing)
        if score > 0:
            created_at = listing.get('created_at', '')
            if hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            scored.append({
                'listing_id': listing['id'],
                'score': score,
                'created_at': created_at or '',
                'price': listing.get('price_per_month', 0)
            })
    
    # Sort by: score desc, created_at desc, price asc
    scored.sort(key=lambda x: (-x['score'], -hash(x['created_at']) if x['created_at'] else 0, x['price']))
    
    ranked = [(item['listing_id'], rank, item['score']) for rank, item in enumerate(scored, start=1)]
    logger.info(f"Group {group.get('id')} ranked {len(ranked)} listings")
    return ranked


def rank_groups_for_listing(listing: Dict[str, Any], feasible_groups: List[Dict[str, Any]]) -> List[Tuple[str, int, float]]:
    """Rank all feasible groups for a listing. Returns [(group_id, rank, score)]."""
    scored = []
    for group in feasible_groups:
        score = calculate_listing_score(listing, group)
        if score > 0:
            created_at = group.get('created_at', '')
            if hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            scored.append({
                'group_id': group['id'],
                'score': score,
                'created_at': created_at or ''
            })
    
    # Sort by: score desc, created_at desc
    scored.sort(key=lambda x: (-x['score'], -hash(x['created_at']) if x['created_at'] else 0, x['group_id']))
    
    ranked = [(item['group_id'], rank, item['score']) for rank, item in enumerate(scored, start=1)]
    logger.info(f"Listing {listing.get('id')} ranked {len(ranked)} groups")
    return ranked


def build_preference_lists(
    feasible_pairs: List[Tuple[str, str]],
    groups: List[Dict[str, Any]],
    listings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Build preference lists for all groups and listings from feasible pairs."""
    logger.info(f"Building preference lists from {len(feasible_pairs)} feasible pairs...")
    
    groups_dict = {g['id']: g for g in groups}
    listings_dict = {l['id']: l for l in listings}
    
    # Build compatibility maps
    group_listings = {}  # group_id -> [listing_ids]
    listing_groups = {}  # listing_id -> [group_ids]
    
    for group_id, listing_id in feasible_pairs:
        group_listings.setdefault(group_id, []).append(listing_id)
        listing_groups.setdefault(listing_id, []).append(group_id)
    
    # Build group preferences
    group_preferences = {}
    for group_id, listing_ids in group_listings.items():
        group = groups_dict.get(group_id)
        if group:
            compatible = [listings_dict[lid] for lid in listing_ids if lid in listings_dict]
            group_preferences[group_id] = rank_listings_for_group(group, compatible)
    
    # Build listing preferences
    listing_preferences = {}
    for listing_id, group_ids in listing_groups.items():
        listing = listings_dict.get(listing_id)
        if listing:
            compatible = [groups_dict[gid] for gid in group_ids if gid in groups_dict]
            listing_preferences[listing_id] = rank_groups_for_listing(listing, compatible)
    
    metadata = {
        'total_groups': len(group_preferences),
        'total_listings': len(listing_preferences),
        'feasible_pairs': len(feasible_pairs),
        'avg_listings_per_group': len(feasible_pairs) / len(group_preferences) if group_preferences else 0,
        'avg_groups_per_listing': len(feasible_pairs) / len(listing_preferences) if listing_preferences else 0
    }
    
    logger.info(f"Built preferences for {len(group_preferences)} groups, {len(listing_preferences)} listings")
    
    return {
        'group_preferences': group_preferences,
        'listing_preferences': listing_preferences,
        'metadata': metadata
    }


# Export public API
__all__ = [
    'check_hard_constraints',
    'calculate_group_score',
    'calculate_listing_score',
    'rank_listings_for_group',
    'rank_groups_for_listing',
    'build_preference_lists',
    'GROUP_SCORING_WEIGHTS',
    'LISTING_SCORING_WEIGHTS',
    'MAX_SCORE'
]
