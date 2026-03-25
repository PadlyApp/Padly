"""
Preferences contract helpers.

Frontend Preferences page is the source-of-truth for:
- furnished_preference: required | preferred | no_preference
- gender_policy: same_gender_only | mixed_ok
- target_lease_type: fixed | month_to_month | sublet | any
"""

from __future__ import annotations

from typing import Any, Optional

FRONTEND_FURNISHED_PREFERENCES = {"required", "preferred", "no_preference"}
FRONTEND_GENDER_POLICIES = {"same_gender_only", "mixed_ok"}
FRONTEND_LEASE_TYPES = {"fixed", "month_to_month", "sublet", "any"}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_furnished_preference(value: Any) -> Optional[str]:
    raw = _norm(value)
    if not raw:
        return None
    if raw in FRONTEND_FURNISHED_PREFERENCES:
        return raw
    # Legacy booleans and loose aliases.
    if raw in {"true", "1", "yes"}:
        return "preferred"
    if raw in {"false", "0", "no"}:
        return "no_preference"
    return None


def target_furnished_from_preference(preference: Optional[str]) -> Optional[bool]:
    pref = normalize_furnished_preference(preference)
    if pref in {"required", "preferred"}:
        return True
    if pref == "no_preference":
        return None
    return None


def resolve_furnished_preference(
    explicit_preference: Any,
    legacy_target_furnished: Any,
) -> Optional[str]:
    """
    Resolve tri-state preference from explicit value first, then legacy bool.
    Legacy bool=True maps to "preferred" (non-hard) for backward compatibility.
    """
    pref = normalize_furnished_preference(explicit_preference)
    if pref is not None:
        return pref

    legacy = legacy_target_furnished
    if isinstance(legacy, str):
        legacy = _norm(legacy) in {"true", "t", "1", "yes"}
    if legacy is True:
        return "preferred"
    if legacy is False:
        return "no_preference"
    return None


def normalize_gender_policy(value: Any) -> Optional[str]:
    raw = _norm(value)
    if not raw:
        return None
    if raw in FRONTEND_GENDER_POLICIES:
        return raw
    return None


def normalize_lease_type(value: Any) -> Optional[str]:
    """
    Normalize lease type to frontend canonical values:
    fixed | month_to_month | sublet | any
    """
    raw = _norm(value)
    if not raw:
        return None
    if raw in FRONTEND_LEASE_TYPES:
        return raw
    if raw in {"fixed_term", "fixed-term", "fixedterm"}:
        return "fixed"
    if raw in {"open_ended", "open-ended", "month-to-month", "month to month"}:
        return "month_to_month"
    if raw in {"sublease"}:
        return "sublet"
    if raw in {"no_preference", "no preference"}:
        return "any"
    return None


def lease_types_compatible(preference_value: Any, candidate_value: Any) -> bool:
    """
    Compare lease types with canonicalized values.
    Treat month_to_month and sublet as compatible flexible terms.
    """
    pref = normalize_lease_type(preference_value)
    cand = normalize_lease_type(candidate_value)

    if pref in {None, "any"} or cand in {None, "any"}:
        return True
    if pref == cand:
        return True

    flexible = {"month_to_month", "sublet"}
    if pref in flexible and cand in flexible:
        return True
    return False
