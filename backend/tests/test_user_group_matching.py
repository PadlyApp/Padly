"""Unit tests for user-group compatibility scoring."""

from app.services.user_group_matching import calculate_user_group_compatibility


def _base_user():
    return {
        "company_name": "",
        "school_name": "",
        "verification_status": "unverified",
    }


def _base_user_prefs():
    return {
        "target_city": "Toronto",
        "budget_min": 1000,
        "budget_max": 1600,
        "move_in_date": "2026-04-01",
        "target_lease_type": "fixed",
        "target_lease_duration_months": 12,
        "gender_policy": "mixed_ok",
        "preferred_neighborhoods": ["Downtown"],
        "target_house_rules": "no smoking",
        "lifestyle_preferences": {
            "cleanliness_level": "high",
            "social_preference": "balanced",
            "cooking_frequency": "often",
            "gender_identity": "woman",
            "amenity_priorities": ["gym"],
            "building_type_preferences": ["apartment"],
        },
    }


def _base_group():
    return {
        "target_city": "Toronto",
        "budget_per_person_min": 1100,
        "budget_per_person_max": 1500,
        "target_move_in_date": "2026-04-01",
        "target_lease_type": "fixed",
        "target_lease_duration_months": 12,
        "current_member_count": 1,
        "target_group_size": 3,
        "_preferred_neighborhoods": ["Downtown"],
        "target_house_rules": "no smoking",
        "lifestyle_preferences": {
            "cleanliness_level": "high",
            "social_preference": "balanced",
            "cooking_frequency": "often",
            "gender_identity": "woman",
            "amenity_priorities": ["gym"],
            "building_type_preferences": ["apartment"],
        },
    }


def test_user_group_score_ignores_legacy_furnished_utilities_soft_points():
    user = _base_user()
    prefs = _base_user_prefs()
    base = _base_group()

    group_a = {**base, "target_furnished": True, "target_utilities_included": True}
    group_b = {**base, "target_furnished": False, "target_utilities_included": False}

    score_a = calculate_user_group_compatibility(user, prefs, group_a)
    score_b = calculate_user_group_compatibility(user, prefs, group_b)

    assert score_a["eligible"] is True
    assert score_b["eligible"] is True
    assert score_a["score"] == score_b["score"]


def test_user_group_lifestyle_now_carries_30_points():
    score = calculate_user_group_compatibility(_base_user(), _base_user_prefs(), _base_group())
    assert score["eligible"] is True
    # With perfect hard and lifestyle alignment this should include the 30-pt lifestyle weight.
    assert score["score"] >= 80
