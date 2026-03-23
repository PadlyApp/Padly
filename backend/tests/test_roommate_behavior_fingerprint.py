"""Tests for roommate behavioral fingerprint and similarity (Phase 1)."""

import math

import pytest

from app.services.roommate_behavior_fingerprint import (
    ROOMMATE_BEHAVIOR_MIN_SWIPES,
    VECTOR_DIM,
    build_prefs_proxy_vector,
    build_vector_from_liked_listings,
    neutral_behavior_vector,
    scale_log_price_value,
    similarity_behavior,
)


def _listing(price, beds, sqft, **kwargs):
    row = {
        "id": kwargs.pop("id", "x"),
        "price_per_month": price,
        "number_of_bedrooms": beds,
        "area_sqft": sqft,
        "furnished": kwargs.pop("furnished", False),
        "amenities": kwargs.pop("amenities", {}),
    }
    row.update(kwargs)
    return row


def test_vector_length_and_confidence():
    likes = [
        _listing(1000, 2, 900),
        _listing(1050, 2, 920),
    ]
    vec, meta = build_vector_from_liked_listings(likes)
    assert len(vec) == VECTOR_DIM
    assert meta["liked_listing_count"] == 2
    assert vec[-1] == pytest.approx(min(math.sqrt(2), 10) / 10.0)


def test_histogram_normalizes():
    likes = [_listing(1100, 2, 950, amenities={"cats_allowed": 1, "dogs_allowed": 1})] * 3
    vec, _ = build_vector_from_liked_listings(likes)
    hist = vec[3:9]
    assert abs(sum(hist) - 1.0) < 1e-6
    # All same listing → one category gets all mass
    assert max(hist) == pytest.approx(1.0)


def test_empty_likes_uniform_histogram():
    vec, meta = build_vector_from_liked_listings([])
    assert meta["liked_listing_count"] == 0
    hist = vec[3:9]
    assert abs(sum(hist) - 1.0) < 1e-6
    assert vec[0] == 0.0 and vec[1] == 0.0 and vec[2] == 0.0


def test_scale_log_price_clamp():
    assert scale_log_price_value(None) == 0.0
    assert scale_log_price_value(300) == 0.0
    assert scale_log_price_value(15000) == 1.0
    mid = scale_log_price_value(2000)
    assert 0.0 < mid < 1.0


def test_similarity_warm_identical_high():
    likes = [_listing(1200, 2, 1000, id="a"), _listing(1180, 2, 980, id="b")]
    vu, _ = build_vector_from_liked_listings(likes)
    vv, _ = build_vector_from_liked_listings(list(reversed(likes)))
    k = ROOMMATE_BEHAVIOR_MIN_SWIPES
    fp_u = {"vector": vu, "positive_swipe_count": k}
    fp_v = {"vector": vv, "positive_swipe_count": k}
    out = similarity_behavior(fp_u, fp_v, prefs_u=None, prefs_v=None, k=k)
    assert out["cold_cold"] is False
    assert out["behavior_confidence"] == "high"
    assert out["similarity"] is not None
    assert out["similarity"] > 0.99


def test_similarity_cold_cold():
    vec, _ = build_vector_from_liked_listings([])
    fp = {"vector": vec, "positive_swipe_count": 0}
    out = similarity_behavior(fp, fp, k=ROOMMATE_BEHAVIOR_MIN_SWIPES)
    assert out["cold_cold"] is True
    assert out["similarity"] is None


def test_similarity_one_cold_uses_prefs_proxy():
    warm_likes = [_listing(1200, 2, 1000, id=str(i)) for i in range(5)]
    vu, _ = build_vector_from_liked_listings(warm_likes)
    vv, _ = build_vector_from_liked_listings([])
    fp_u = {"vector": vu, "positive_swipe_count": 5}
    fp_v = {"vector": vv, "positive_swipe_count": 0}
    prefs_v = {"budget_min": 1000, "budget_max": 1400, "required_bedrooms": 2}
    out = similarity_behavior(fp_u, fp_v, prefs_v=prefs_v, k=ROOMMATE_BEHAVIOR_MIN_SWIPES)
    assert out["cold_cold"] is False
    assert out["used_prefs_proxy_v"] is True
    assert out["behavior_confidence"] == "mixed"
    assert out["similarity"] is not None
    assert 0.0 <= out["similarity"] <= 1.0


def test_prefs_proxy_vector_budget_midpoint():
    v = build_prefs_proxy_vector({"budget_min": 1000, "budget_max": 2000, "required_bedrooms": 3})
    assert len(v) == VECTOR_DIM
    assert v[0] == scale_log_price_value(1500.0)
    assert abs(v[1] - 0.6) < 1e-6


def test_neutral_vector_shape():
    n = neutral_behavior_vector()
    assert len(n) == VECTOR_DIM
    assert abs(sum(n[3:9]) - 1.0) < 1e-6
