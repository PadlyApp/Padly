"""Unit tests for stable matching group->listing scoring."""

from app.services.stable_matching.scoring import calculate_group_score


def _base_group():
    return {
        "id": "g1",
        "target_city": "Toronto",
        "target_state_province": "ON",
        "target_group_size": 2,
        "budget_per_person_min": 900,
        "budget_per_person_max": 1500,
        "target_move_in_date": "2026-04-01",
        "target_lease_type": "fixed",
        "target_lease_duration_months": 12,
    }


def _base_listing():
    return {
        "id": "l1",
        "city": "Toronto",
        "state_province": "ON",
        "price_per_month": 2400,
        "number_of_bedrooms": 2,
        "available_from": "2026-04-15",
        "lease_type": "fixed",
        "lease_duration_months": 12,
        "property_type": "apartment",
        "amenities": {"gym": True, "parking": True},
        "house_rules": "No smoking. Quiet hours after 10pm.",
        "neighborhood": "Downtown",
    }


def test_group_score_uses_new_frontend_soft_fields():
    group = {
        **_base_group(),
        "preferred_neighborhoods": ["Downtown"],
        "target_house_rules": "no smoking, quiet hours",
        "lifestyle_preferences": {
            "amenity_priorities": ["gym", "parking"],
            "building_type_preferences": ["apartment", "condo"],
        },
    }
    listing = _base_listing()

    score = calculate_group_score(group, listing)
    assert score >= 95.0


def test_group_score_penalizes_soft_mismatch():
    group = {
        **_base_group(),
        "preferred_neighborhoods": ["Downtown"],
        "target_house_rules": "no smoking, quiet hours",
        "lifestyle_preferences": {
            "amenity_priorities": ["gym", "parking"],
            "building_type_preferences": ["apartment"],
        },
    }
    listing = {
        **_base_listing(),
        "property_type": "house",
        "amenities": {"laundry": True},
        "house_rules": "Parties allowed. Smoking allowed.",
        "neighborhood": "Suburbs",
    }

    score = calculate_group_score(group, listing)
    assert score < 50.0


def test_group_score_neutral_without_soft_preferences():
    group = _base_group()
    listing = _base_listing()

    score = calculate_group_score(group, listing)
    assert score == 50.0

