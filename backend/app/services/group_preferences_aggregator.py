"""
Group Preferences Aggregator

Aggregates preferences from group members into collective group preferences.
"""

from typing import List, Dict, Any, Optional
from datetime import date, datetime
from collections import Counter
from decimal import Decimal


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _most_common_non_empty(values: List[Any]) -> Optional[Any]:
    cleaned = [v for v in values if v not in (None, "", [])]
    if not cleaned:
        return None
    return Counter(cleaned).most_common(1)[0][0]


def _dedupe_strings(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def calculate_aggregate_group_preferences(group_id: str) -> Dict[str, Any]:
    """Aggregate preferences from all accepted group members."""
    from app.dependencies.supabase import get_admin_client

    supabase = get_admin_client()

    # Get accepted member IDs
    members_response = (
        supabase.table("group_members")
        .select("user_id")
        .eq("group_id", group_id)
        .eq("status", "accepted")
        .execute()
    )

    if not members_response.data:
        return get_group_level_preferences(group_id)

    member_ids = [m["user_id"] for m in members_response.data]

    # Get each member's preferences
    all_member_prefs: List[Dict[str, Any]] = []
    for user_id in member_ids:
        prefs_response = (
            supabase.table("personal_preferences")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        if prefs_response.data:
            all_member_prefs.append(prefs_response.data[0])

    if not all_member_prefs:
        return get_group_level_preferences(group_id)

    group_prefs = get_group_level_preferences(group_id)
    aggregated: Dict[str, Any] = {}

    # Location fields: majority vote with group-level fallback.
    for key in ("target_country", "target_state_province", "target_city"):
        voted = _most_common_non_empty([p.get(key) for p in all_member_prefs])
        aggregated[key] = voted if voted is not None else group_prefs.get(key)

    # Budget: OVERLAP (highest min, lowest max)
    budget_mins = [_to_float(p.get("budget_min")) for p in all_member_prefs]
    budget_mins = [v for v in budget_mins if v is not None]
    budget_maxs = [_to_float(p.get("budget_max")) for p in all_member_prefs]
    budget_maxs = [v for v in budget_maxs if v is not None]

    if budget_mins and budget_maxs:
        agg_min, agg_max = max(budget_mins), min(budget_maxs)
        if agg_min <= agg_max:
            aggregated["budget_min"] = agg_min
            aggregated["budget_max"] = agg_max
        else:
            aggregated["budget_min"] = _to_float(group_prefs.get("budget_min"))
            aggregated["budget_max"] = _to_float(group_prefs.get("budget_max"))
    else:
        aggregated["budget_min"] = _to_float(group_prefs.get("budget_min"))
        aggregated["budget_max"] = _to_float(group_prefs.get("budget_max"))

    # Keep legacy aliases in sync.
    aggregated["budget_per_person_min"] = aggregated.get("budget_min")
    aggregated["budget_per_person_max"] = aggregated.get("budget_max")

    # Move-in date: MEDIAN
    all_dates = [_to_date(p.get("move_in_date")) for p in all_member_prefs]
    all_dates = [d for d in all_dates if d is not None]
    if all_dates:
        sorted_dates = sorted(all_dates)
        median_date = sorted_dates[len(sorted_dates) // 2]
    else:
        median_date = _to_date(group_prefs.get("move_in_date"))

    aggregated["move_in_date"] = median_date
    aggregated["target_move_in_date"] = median_date

    # Bedrooms/Bathrooms: keep existing behavior based on active member count.
    target_bedrooms = max(1, int(len(member_ids) or 1))
    aggregated["target_bedrooms"] = target_bedrooms
    aggregated["required_bedrooms"] = target_bedrooms

    if len(member_ids) <= 2:
        target_bathrooms = 1.0
    elif len(member_ids) <= 4:
        target_bathrooms = 1.5
    else:
        target_bathrooms = 2.0
    aggregated["target_bathrooms"] = target_bathrooms

    # Lifestyle: blended values for group compatibility/ranking.
    aggregated["lifestyle_preferences"] = aggregate_lifestyle_preferences(all_member_prefs)

    # Preferred neighborhoods: union of member picks, de-duplicated.
    all_neighborhoods: List[str] = []
    for prefs in all_member_prefs:
        neighborhoods = prefs.get("preferred_neighborhoods") or []
        if isinstance(neighborhoods, list):
            all_neighborhoods.extend(neighborhoods)
    merged_neighborhoods = _dedupe_strings(all_neighborhoods)
    if merged_neighborhoods:
        aggregated["preferred_neighborhoods"] = merged_neighborhoods
    else:
        aggregated["preferred_neighborhoods"] = group_prefs.get("preferred_neighborhoods") or []

    # Furnished preference:
    # - required if any member marks required
    # - preferred if anyone marks preferred and no one requires
    # - no_preference otherwise
    furnished_pref_values = [
        p.get("furnished_preference")
        for p in all_member_prefs
        if p.get("furnished_preference") is not None
    ]
    if "required" in furnished_pref_values:
        aggregated["furnished_preference"] = "required"
        aggregated["target_furnished"] = True
        aggregated["furnished_is_hard"] = True
    elif "preferred" in furnished_pref_values:
        aggregated["furnished_preference"] = "preferred"
        aggregated["target_furnished"] = True
        aggregated["furnished_is_hard"] = False
    elif furnished_pref_values:
        aggregated["furnished_preference"] = "no_preference"
        aggregated["target_furnished"] = None
        aggregated["furnished_is_hard"] = False
    else:
        # Backward-compat fallback to legacy boolean field.
        furnished_prefs = [
            p.get("target_furnished")
            for p in all_member_prefs
            if p.get("target_furnished") is not None
        ]
        if furnished_prefs:
            aggregated["furnished_preference"] = "required"
            aggregated["target_furnished"] = any(furnished_prefs)
            aggregated["furnished_is_hard"] = any(furnished_prefs)
        else:
            aggregated["furnished_preference"] = group_prefs.get("furnished_preference")
            aggregated["target_furnished"] = group_prefs.get("target_furnished")
            aggregated["furnished_is_hard"] = bool(group_prefs.get("furnished_is_hard") or False)

    # Utilities: ANY wants it -> group wants it.
    utilities_prefs = [
        p.get("target_utilities_included")
        for p in all_member_prefs
        if p.get("target_utilities_included") is not None
    ]
    if utilities_prefs:
        aggregated["target_utilities_included"] = any(utilities_prefs)
    else:
        aggregated["target_utilities_included"] = group_prefs.get("target_utilities_included")

    # Deposit: use the tightest max-deposit cap (minimum among members).
    deposit_caps = [_to_float(p.get("target_deposit_amount")) for p in all_member_prefs]
    deposit_caps = [v for v in deposit_caps if v is not None]
    if deposit_caps:
        aggregated["target_deposit_amount"] = min(deposit_caps)
    else:
        aggregated["target_deposit_amount"] = _to_float(group_prefs.get("target_deposit_amount"))

    # Lease Type: MOST COMMON (excluding 'any')
    lease_types = [
        p.get("target_lease_type")
        for p in all_member_prefs
        if p.get("target_lease_type") and p.get("target_lease_type") != "any"
    ]
    if lease_types:
        aggregated["target_lease_type"] = Counter(lease_types).most_common(1)[0][0]
    else:
        aggregated["target_lease_type"] = group_prefs.get("target_lease_type")

    # Lease Duration: MEDIAN
    durations: List[int] = []
    for prefs in all_member_prefs:
        try:
            value = prefs.get("target_lease_duration_months")
            if value is not None:
                durations.append(int(value))
        except (TypeError, ValueError):
            continue

    if durations:
        aggregated["target_lease_duration_months"] = sorted(durations)[len(durations) // 2]
    else:
        aggregated["target_lease_duration_months"] = group_prefs.get("target_lease_duration_months")

    # Gender policy: if any member asks same-gender-only, use restrictive policy.
    gender_policies = [p.get("gender_policy") for p in all_member_prefs if p.get("gender_policy")]
    if "same_gender_only" in gender_policies:
        aggregated["gender_policy"] = "same_gender_only"
    elif gender_policies:
        aggregated["gender_policy"] = "mixed_ok"
    else:
        aggregated["gender_policy"] = group_prefs.get("gender_policy")

    # House rules: most common non-empty note.
    house_rules = _most_common_non_empty([p.get("target_house_rules") for p in all_member_prefs])
    if house_rules is not None:
        aggregated["target_house_rules"] = house_rules
    else:
        aggregated["target_house_rules"] = group_prefs.get("target_house_rules")

    return aggregated


def get_group_level_preferences(group_id: str) -> Dict[str, Any]:
    """Get preferences from the group record (fallback)."""
    from app.dependencies.supabase import get_admin_client

    supabase = get_admin_client()
    group_response = (
        supabase.table("roommate_groups")
        .select("*")
        .eq("id", group_id)
        .single()
        .execute()
    )

    if not group_response.data:
        return {}

    g = group_response.data
    budget_min = g.get("budget_min")
    if budget_min is None:
        budget_min = g.get("budget_per_person_min")
    budget_max = g.get("budget_max")
    if budget_max is None:
        budget_max = g.get("budget_per_person_max")

    move_in_date = g.get("move_in_date")
    if move_in_date is None:
        move_in_date = g.get("target_move_in_date")

    required_bedrooms = g.get("required_bedrooms")
    if required_bedrooms is None:
        required_bedrooms = g.get("target_bedrooms")

    return {
        "target_country": g.get("target_country"),
        "target_state_province": g.get("target_state_province"),
        "target_city": g.get("target_city"),
        "budget_min": budget_min,
        "budget_max": budget_max,
        "budget_per_person_min": g.get("budget_per_person_min", budget_min),
        "budget_per_person_max": g.get("budget_per_person_max", budget_max),
        "move_in_date": move_in_date,
        "target_move_in_date": g.get("target_move_in_date", move_in_date),
        "required_bedrooms": required_bedrooms,
        "target_bedrooms": g.get("target_bedrooms", required_bedrooms),
        "target_bathrooms": g.get("target_bathrooms"),
        "target_furnished": g.get("target_furnished"),
        "furnished_preference": g.get("furnished_preference"),
        "furnished_is_hard": g.get("furnished_is_hard"),
        "target_utilities_included": g.get("target_utilities_included"),
        "target_deposit_amount": g.get("target_deposit_amount"),
        "target_lease_type": g.get("target_lease_type"),
        "target_lease_duration_months": g.get("target_lease_duration_months"),
        "gender_policy": g.get("gender_policy"),
        "target_house_rules": g.get("target_house_rules"),
        "preferred_neighborhoods": g.get("preferred_neighborhoods") or [],
        "lifestyle_preferences": g.get("lifestyle_preferences") or {},
    }


def aggregate_lifestyle_preferences(all_member_prefs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate lifestyle preferences using majority vote + merged list fields."""
    all_lifestyles = [
        p.get("lifestyle_preferences", {})
        for p in all_member_prefs
        if isinstance(p.get("lifestyle_preferences"), dict)
    ]

    if not all_lifestyles:
        return {}

    aggregated: Dict[str, Any] = {}

    # Current personal-preferences keys (v2 UI).
    for key in ("cleanliness_level", "social_preference", "cooking_frequency", "gender_identity"):
        values = [lp.get(key) for lp in all_lifestyles if lp.get(key)]
        if values:
            aggregated[key] = Counter(values).most_common(1)[0][0]

    for key in ("amenity_priorities", "building_type_preferences"):
        merged: List[str] = []
        for lp in all_lifestyles:
            values = lp.get(key)
            if isinstance(values, list):
                merged.extend([str(v).strip() for v in values if str(v).strip()])
        merged = _dedupe_strings(merged)
        if merged:
            aggregated[key] = merged

    # Backward compatibility for older saved keys.
    legacy_orders = {
        "cleanliness": ["messy", "moderate", "clean", "very_clean"],
        "noise_level": ["loud", "moderate", "quiet"],
        "smoking": ["smoking_ok", "outdoor_only", "no_smoking"],
        "pets": ["pets_ok", "no_pets"],
        "guests_frequency": ["frequently", "occasionally", "rarely"],
    }

    for attr, order in legacy_orders.items():
        values = [lp.get(attr) for lp in all_lifestyles if lp.get(attr)]
        if not values:
            continue
        try:
            aggregated[attr] = max(values, key=lambda x: order.index(x) if x in order else -1)
        except ValueError:
            continue

    return aggregated


__all__ = ["calculate_aggregate_group_preferences", "aggregate_lifestyle_preferences"]
