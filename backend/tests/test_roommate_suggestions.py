"""Unit tests for roommate suggestions (Phase 2) helpers."""

import pytest

from app.services.roommate_suggestions import (
    EMBEDDING_IN_LIFESTYLE_WEIGHT,
    blend_lifestyle_with_embedding,
    budgets_overlap_user,
    build_top_reasons,
    candidate_excluded_for_incompatible_group,
    cities_compatible_if_both_set,
    countries_compatible_if_both_set,
    fuse_final_score,
    lease_duration_compatible_if_both_set,
    lease_types_compatible_if_both_set,
    lifestyle_similarity_user_user,
    move_in_dates_compatible_if_both_set,
    passes_all_hard_gates_user_user,
    passes_same_gender_gate,
    required_bedrooms_compatible_if_both_set,
    seeker_compatible_with_group_hard,
    states_compatible_if_both_set,
    target_bathrooms_compatible_if_both_set,
    target_deposit_compatible_if_both_set,
)


def test_budgets_overlap_open_bounds():
    assert budgets_overlap_user(0, None, 100, 200) is True
    assert budgets_overlap_user(100, 200, 300, 400) is False
    assert budgets_overlap_user(100, 300, 200, 400) is True
    assert budgets_overlap_user(None, None, 0, 500) is True


def test_states_compatible_when_either_missing():
    s = {"target_state_province": "CA"}
    c = {"target_state_province": None}
    assert states_compatible_if_both_set(s, c) is True
    assert states_compatible_if_both_set(c, s) is True


def test_states_incompatible_when_both_set_differ():
    assert (
        states_compatible_if_both_set(
            {"target_state_province": "CA"}, {"target_state_province": "NY"}
        )
        is False
    )


def test_countries_compatible_when_either_missing():
    assert countries_compatible_if_both_set({"target_country": "US"}, {"target_country": None}) is True
    assert countries_compatible_if_both_set({"target_country": None}, {"target_country": "CA"}) is True


def test_countries_incompatible_when_both_set_differ():
    assert countries_compatible_if_both_set({"target_country": "US"}, {"target_country": "CA"}) is False


def test_cities_compatible_when_matching():
    assert cities_compatible_if_both_set({"target_city": "Boston"}, {"target_city": "boston"}) is True


def test_cities_incompatible_when_different():
    assert cities_compatible_if_both_set({"target_city": "Boston"}, {"target_city": "Cambridge"}) is False


def test_same_gender_gate_mixed_ok():
    seeker = {"lifestyle_preferences": {"gender_identity": "woman"}, "gender_policy": "mixed_ok"}
    cand = {"lifestyle_preferences": {"gender_identity": "man"}}
    assert passes_same_gender_gate(seeker, cand) is True


def test_same_gender_gate_requires_match():
    seeker = {
        "gender_policy": "same_gender_only",
        "lifestyle_preferences": {"gender_identity": "woman"},
    }
    ok_cand = {"lifestyle_preferences": {"gender_identity": "woman"}}
    bad_cand = {"lifestyle_preferences": {"gender_identity": "man"}}
    missing_cand = {"lifestyle_preferences": {}}
    assert passes_same_gender_gate(seeker, ok_cand) is True
    assert passes_same_gender_gate(seeker, bad_cand) is False
    assert passes_same_gender_gate(seeker, missing_cand) is False


def test_move_in_dates_compatible_if_both_set():
    seeker = {"move_in_date": "2026-05-01"}
    cand_ok = {"move_in_date": "2026-06-15"}  # 45 days
    cand_bad = {"move_in_date": "2026-08-15"}  # > 60 days
    assert move_in_dates_compatible_if_both_set(seeker, cand_ok) is True
    assert move_in_dates_compatible_if_both_set(seeker, cand_bad) is False


def test_lease_types_compatible_if_both_set():
    assert lease_types_compatible_if_both_set(
        {"target_lease_type": "month_to_month"},
        {"target_lease_type": "sublet"},
    ) is True
    assert lease_types_compatible_if_both_set(
        {"target_lease_type": "fixed"},
        {"target_lease_type": "sublet"},
    ) is False


def test_lease_duration_compatible_if_both_set():
    assert lease_duration_compatible_if_both_set(
        {"target_lease_duration_months": 12},
        {"target_lease_duration_months": 12},
    ) is True
    assert lease_duration_compatible_if_both_set(
        {"target_lease_duration_months": 12},
        {"target_lease_duration_months": 6},
    ) is False


def test_required_bedrooms_compatible_if_both_set():
    assert required_bedrooms_compatible_if_both_set(
        {"required_bedrooms": 2},
        {"required_bedrooms": 2},
    ) is True
    assert required_bedrooms_compatible_if_both_set(
        {"required_bedrooms": 2},
        {"required_bedrooms": 3},
    ) is False


def test_target_bathrooms_compatible_if_both_set():
    assert target_bathrooms_compatible_if_both_set(
        {"target_bathrooms": 1.5},
        {"target_bathrooms": 1.5},
    ) is True
    assert target_bathrooms_compatible_if_both_set(
        {"target_bathrooms": 1.5},
        {"target_bathrooms": 2.0},
    ) is False


def test_target_deposit_compatible_if_both_set():
    assert target_deposit_compatible_if_both_set(
        {"target_deposit_amount": 1500},
        {"target_deposit_amount": 1200},
    ) is True
    assert target_deposit_compatible_if_both_set(
        {"target_deposit_amount": 1000},
        {"target_deposit_amount": 1200},
    ) is False


def test_passes_all_hard_gates_user_user_happy_path():
    seeker = {
        "target_country": "US",
        "target_state_province": "CA",
        "budget_min": 1000,
        "budget_max": 2000,
        "required_bedrooms": 2,
        "target_bathrooms": 1.5,
        "target_deposit_amount": 1500,
        "move_in_date": "2026-05-01",
        "target_lease_type": "fixed",
        "target_lease_duration_months": 12,
        "gender_policy": "same_gender_only",
        "lifestyle_preferences": {"gender_identity": "woman"},
    }
    cand = {
        "target_country": "US",
        "target_state_province": "CA",
        "budget_min": 1200,
        "budget_max": 1800,
        "required_bedrooms": 2,
        "target_bathrooms": 1.5,
        "target_deposit_amount": 1200,
        "move_in_date": "2026-05-20",
        "target_lease_type": "fixed",
        "target_lease_duration_months": 12,
        "gender_policy": "same_gender_only",
        "lifestyle_preferences": {"gender_identity": "woman"},
    }
    assert passes_all_hard_gates_user_user(seeker, cand) is True


def test_fuse_final_score_lifestyle_only_when_behavior_none():
    assert fuse_final_score(None, 0.75, 0.6, 0.4) == pytest.approx(0.75)


def test_fuse_final_score_blend():
    assert fuse_final_score(1.0, 0.0, 0.6, 0.4) == pytest.approx(0.6)
    assert fuse_final_score(0.0, 1.0, 0.6, 0.4) == pytest.approx(0.4)


def test_blend_lifestyle_with_embedding_no_embedding():
    assert blend_lifestyle_with_embedding(0.8, None) == pytest.approx(0.8)


def test_blend_lifestyle_with_embedding_mix():
    d = EMBEDDING_IN_LIFESTYLE_WEIGHT
    out = blend_lifestyle_with_embedding(0.5, 1.0, delta=d)
    assert out == pytest.approx((1.0 - d) * 0.5 + d * 1.0)


def test_seeker_compatible_with_group_hard():
    prefs = {
        "target_country": "US",
        "target_city": "Boston",
        "target_state_province": "MA",
        "budget_min": 1000,
        "budget_max": 2000,
        "target_lease_type": "fixed",
        "target_lease_duration_months": 12,
        "move_in_date": "2026-05-01",
    }
    good = {
        "id": "g1",
        "status": "active",
        "target_country": "US",
        "target_city": "Boston",
        "target_state_province": "MA",
        "budget_per_person_min": 1200,
        "budget_per_person_max": 1800,
        "target_lease_type": "fixed",
        "target_lease_duration_months": 12,
        "target_move_in_date": "2026-05-20",
    }
    bad_city = {**good, "target_city": "Cambridge"}
    bad_budget = {**good, "budget_per_person_min": 3000, "budget_per_person_max": 4000}
    bad_lease = {**good, "target_lease_type": "sublet"}
    assert seeker_compatible_with_group_hard(prefs, good) is True
    assert seeker_compatible_with_group_hard(prefs, bad_city) is False
    assert seeker_compatible_with_group_hard(prefs, bad_budget) is False
    assert seeker_compatible_with_group_hard(prefs, bad_lease) is False


def test_candidate_excluded_for_incompatible_group():
    seeker = {"target_city": "Boston", "budget_min": 1000, "budget_max": 2000}
    memberships = [
        {
            "roommate_groups": {
                "id": "g1",
                "status": "active",
                "target_city": "NYC",
                "budget_per_person_min": 1000,
                "budget_per_person_max": 2000,
            }
        }
    ]
    assert candidate_excluded_for_incompatible_group(seeker, memberships) is True

    ok_memberships = [
        {
            "roommate_groups": {
                "id": "g2",
                "status": "active",
                "target_city": "Boston",
                "budget_per_person_min": 1000,
                "budget_per_person_max": 2000,
            }
        }
    ]
    assert candidate_excluded_for_incompatible_group(seeker, ok_memberships) is False

    inactive = [
        {
            "roommate_groups": {
                "id": "g3",
                "status": "archived",
                "target_city": "NYC",
                "budget_per_person_min": 1000,
                "budget_per_person_max": 2000,
            }
        }
    ]
    assert candidate_excluded_for_incompatible_group(seeker, inactive) is False


def test_lifestyle_similarity_user_user_neutral_when_empty():
    s = {"lifestyle_preferences": {}, "preferred_neighborhoods": []}
    c = {"lifestyle_preferences": {}, "preferred_neighborhoods": []}
    v = lifestyle_similarity_user_user(s, c)
    assert 0.0 <= v <= 1.0


def test_build_top_reasons_smoke():
    sp = {
        "lifestyle_preferences": {
            "cleanliness_level": "high",
            "social_preference": "quiet",
            "amenity_priorities": ["gym"],
        },
        "preferred_neighborhoods": ["Downtown"],
    }
    cp = {
        "lifestyle_preferences": {
            "cleanliness_level": "high",
            "social_preference": "quiet",
            "amenity_priorities": ["gym"],
        },
        "preferred_neighborhoods": ["Downtown"],
    }
    ms = {"liked_mean_price": 2000, "liked_mean_beds": 2.0, "category_counts": [0, 0, 2, 0, 0, 0]}
    mc = {"liked_mean_price": 2050, "liked_mean_beds": 2.0, "category_counts": [0, 0, 2, 0, 0, 0]}
    r = build_top_reasons(sp, cp, ms, mc)
    assert 1 <= len(r) <= 3
    assert any(
        k in " ".join(r).lower()
        for k in (
            "cleanliness",
            "social",
            "cooking",
            "gender",
            "neighborhood",
            "amenity",
            "building",
            "house rules",
        )
    )
