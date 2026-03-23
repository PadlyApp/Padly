"""Unit tests for roommate suggestions (Phase 2) helpers."""

import pytest

from app.services.roommate_suggestions import (
    budgets_overlap_user,
    build_top_reasons,
    candidate_excluded_for_incompatible_group,
    fuse_final_score,
    lifestyle_similarity_user_user,
    passes_same_gender_gate,
    seeker_compatible_with_group_hard,
    states_compatible_if_both_set,
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


def test_fuse_final_score_lifestyle_only_when_behavior_none():
    assert fuse_final_score(None, 0.75, 0.6, 0.4) == pytest.approx(0.75)


def test_fuse_final_score_blend():
    assert fuse_final_score(1.0, 0.0, 0.6, 0.4) == pytest.approx(0.6)
    assert fuse_final_score(0.0, 1.0, 0.6, 0.4) == pytest.approx(0.4)


def test_seeker_compatible_with_group_hard():
    prefs = {
        "target_city": "Boston",
        "target_state_province": "MA",
        "budget_min": 1000,
        "budget_max": 2000,
    }
    good = {
        "id": "g1",
        "status": "active",
        "target_city": "Boston",
        "target_state_province": "MA",
        "budget_per_person_min": 1200,
        "budget_per_person_max": 1800,
    }
    bad_city = {**good, "target_city": "Cambridge"}
    bad_budget = {**good, "budget_per_person_min": 3000, "budget_per_person_max": 4000}
    assert seeker_compatible_with_group_hard(prefs, good) is True
    assert seeker_compatible_with_group_hard(prefs, bad_city) is False
    assert seeker_compatible_with_group_hard(prefs, bad_budget) is False


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
        for k in ("cleanliness", "price", "bedroom", "neighborhood", "amenity", "pet-friendly", "listings")
    )
