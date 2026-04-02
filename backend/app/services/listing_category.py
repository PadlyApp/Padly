"""
Rule-based listing categories for roommate behavior fingerprints.

Mirrors the priority cascade in app.ai.categorize_and_map.categorize_listings,
adapted to Padly listing dicts (price_per_month, number_of_bedrooms, area_sqft, amenities).
"""

from __future__ import annotations

from typing import Any, Dict

NUM_LISTING_CATEGORIES = 6

# Index → name (aligned with categorize_and_map.CATEGORY_NAMES)
LISTING_CATEGORY_NAMES = {
    0: "Budget Compact",
    1: "Spacious Family",
    2: "Pet-Friendly",
    3: "Premium / Luxury",
    4: "Urban Convenience",
    5: "Accessible Modern",
}


def _amenities(listing: Dict[str, Any]) -> Dict[str, Any]:
    raw = listing.get("amenities")
    return raw if isinstance(raw, dict) else {}


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y")
    return bool(value)


def _has_wheelchair_or_ev(amenities: Dict[str, Any]) -> bool:
    return _truthy(amenities.get("wheelchair_access")) or _truthy(
        amenities.get("electric_vehicle_charge")
    )


def _has_washer_in_unit(amenities: Dict[str, Any], listing: Dict[str, Any]) -> bool:
    if _truthy(amenities.get("in_unit_laundry")) or _truthy(amenities.get("washer_dryer_in_unit")):
        return True
    for key in ("laundry_options", "laundry"):
        v = amenities.get(key)
        if isinstance(v, str) and ("in unit" in v.lower() or "w/d" in v.lower()):
            return True
    return bool(listing.get("utilities_included")) and _truthy(amenities.get("laundry"))


def _has_garage_parking(amenities: Dict[str, Any]) -> bool:
    for key in ("parking_options", "parking", "parking_type"):
        v = amenities.get(key)
        if isinstance(v, str) and "garage" in v.lower():
            return True
    return _truthy(amenities.get("garage_parking")) or _truthy(amenities.get("attached_garage"))


def _premium_signals(amenities: Dict[str, Any], listing: Dict[str, Any], price: float) -> bool:
    if price <= 1500:
        return False
    if _truthy(listing.get("furnished")):
        return True
    if _has_washer_in_unit(amenities, listing):
        return True
    if _has_garage_parking(amenities):
        return True
    return False


def _both_pets_allowed(amenities: Dict[str, Any]) -> bool:
    return _truthy(amenities.get("cats_allowed")) and _truthy(amenities.get("dogs_allowed"))


def categorize_padly_listing(listing: Dict[str, Any]) -> int:
    """
    Assign exactly one category id in [0, 5] using the same priority order as
    categorize_and_map (Accessible → Premium → Spacious → Budget → Pet → Urban).
    """
    price = float(listing.get("price_per_month") or 0)
    beds = float(listing.get("number_of_bedrooms") or 0)
    sqft = float(listing.get("area_sqft") or 0)
    am = _amenities(listing)

    if _has_wheelchair_or_ev(am):
        return 5
    if _premium_signals(am, listing, price):
        return 3
    if beds >= 3 and sqft > 1100:
        return 1
    if price < 900 and sqft < 800 and beds <= 1:
        return 0
    if _both_pets_allowed(am):
        return 2
    return 4


__all__ = [
    "NUM_LISTING_CATEGORIES",
    "LISTING_CATEGORY_NAMES",
    "categorize_padly_listing",
]
