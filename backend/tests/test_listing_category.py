"""Unit tests for Padly listing category cascade (roommate fingerprint Phase 1)."""

from app.services.listing_category import categorize_padly_listing


def test_category_5_accessible_wheelchair():
    listing = {
        "price_per_month": 2000,
        "number_of_bedrooms": 2,
        "area_sqft": 900,
        "furnished": False,
        "amenities": {"wheelchair_access": 1},
    }
    assert categorize_padly_listing(listing) == 5


def test_category_5_electric_vehicle():
    listing = {
        "price_per_month": 1200,
        "number_of_bedrooms": 2,
        "area_sqft": 950,
        "amenities": {"electric_vehicle_charge": True},
    }
    assert categorize_padly_listing(listing) == 5


def test_category_3_premium_price_furnished():
    listing = {
        "price_per_month": 1600,
        "number_of_bedrooms": 2,
        "area_sqft": 900,
        "furnished": True,
        "amenities": {},
    }
    assert categorize_padly_listing(listing) == 3


def test_category_3_premium_laundry_string():
    listing = {
        "price_per_month": 2000,
        "number_of_bedrooms": 2,
        "area_sqft": 900,
        "furnished": False,
        "amenities": {"laundry_options": "w/d in unit"},
    }
    assert categorize_padly_listing(listing) == 3


def test_category_1_spacious_family():
    listing = {
        "price_per_month": 2500,
        "number_of_bedrooms": 3,
        "area_sqft": 1200,
        "furnished": False,
        "amenities": {},
    }
    assert categorize_padly_listing(listing) == 1


def test_category_0_budget_compact():
    listing = {
        "price_per_month": 800,
        "number_of_bedrooms": 1,
        "area_sqft": 700,
        "amenities": {},
    }
    assert categorize_padly_listing(listing) == 0


def test_category_2_pet_friendly():
    listing = {
        "price_per_month": 1100,
        "number_of_bedrooms": 2,
        "area_sqft": 950,
        "amenities": {"cats_allowed": 1, "dogs_allowed": 1},
    }
    assert categorize_padly_listing(listing) == 2


def test_category_4_urban_default():
    listing = {
        "price_per_month": 1100,
        "number_of_bedrooms": 2,
        "area_sqft": 950,
        "amenities": {"cats_allowed": 1, "dogs_allowed": 0},
    }
    assert categorize_padly_listing(listing) == 4
