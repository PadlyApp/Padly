"""
Padly Recommender Service

Loads the trained Two-Tower model and scores listings for a given user.
Designed to be called from the API route — no ML knowledge needed outside this file.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# ── paths ──────────────────────────────────────────────────────────────────

_AI_DIR = Path(__file__).parent
_MODEL_PATH = _AI_DIR / "artifacts" / "two_tower_baseline.keras"
_META_PATH  = _AI_DIR / "dataset" / "feature_meta.json"

# ── singleton model + metadata ─────────────────────────────────────────────

_model = None
_meta: Optional[Dict] = None
_model_disabled = False


def _load():
    """Load model and feature metadata once, cache for all subsequent calls."""
    global _model, _meta, _model_disabled

    if _model is not None or _model_disabled:
        return

    try:
        print(f"[recommender] loading model from {_MODEL_PATH}")
        import tensorflow as tf  # imported here so the rest of the app doesn't need TF

        # compile=False avoids requiring training-only objects at inference time.
        _model = tf.keras.models.load_model(_MODEL_PATH, safe_mode=False, compile=False)
        print(f"[recommender] model loaded, input shapes: {[i.shape for i in _model.inputs]}")
    except Exception as e:
        # Degrade gracefully when model/runtime versions are incompatible.
        _model = None
        _model_disabled = True
        print(f"[recommender] model unavailable, using heuristic fallback: {e}")

    try:
        with open(_META_PATH) as f:
            _meta = json.load(f)
        print(f"[recommender] meta loaded: user_dim={_meta['user_dim']} item_dim={_meta['item_dim']}")
    except Exception as e:
        _meta = None
        print(f"[recommender] metadata unavailable, using heuristic fallback: {e}")


# ── feature encoding ───────────────────────────────────────────────────────

# Numeric renter columns in the exact order used during training
_USER_NUMERIC_COLS = [
    "age", "household_size", "income", "credit_score",
    "budget_min", "budget_max",
    "desired_beds", "desired_baths", "desired_sqft_min",
    "has_cats", "has_dogs", "is_smoker",
    "needs_wheelchair", "has_ev", "wants_furnished",
    "pref_lat", "pref_lon", "max_distance_km",
    "laundry_pref", "parking_pref", "move_urgency",
]

# All type_pref columns in sorted order (matches training)
_USER_TYPE_PREF_COLS = sorted([
    "type_pref_apartment", "type_pref_assisted_living", "type_pref_condo",
    "type_pref_cottage_cabin", "type_pref_duplex", "type_pref_flat",
    "type_pref_house", "type_pref_in-law", "type_pref_land",
    "type_pref_loft", "type_pref_manufactured", "type_pref_townhouse",
])

# Numeric listing columns in the exact order used during training
_ITEM_NUMERIC_COLS = [
    "price", "sqfeet", "beds", "baths",
    "cats_allowed", "dogs_allowed", "smoking_allowed",
    "wheelchair_access", "electric_vehicle_charge", "comes_furnished",
    "lat", "long",
]


def _encode_user(user: Dict) -> np.ndarray:
    """
    Encode a user preference dict into the user tower input vector.

    Expected keys (all optional — missing ones default to 0):
        budget_min, budget_max, desired_beds, desired_baths, desired_sqft_min,
        has_cats, has_dogs, is_smoker, needs_wheelchair, has_ev, wants_furnished,
        pref_lat, pref_lon, max_distance_km, age, household_size, income,
        credit_score, laundry_pref, parking_pref, move_urgency,
        liked_mean_price, liked_mean_beds, liked_mean_sqfeet,
        liked_type_* (one per listing type)
    """
    # Build numeric + type_pref block
    row = []
    for col in _USER_NUMERIC_COLS:
        row.append(float(user.get(col, 0) or 0))
    for col in _USER_TYPE_PREF_COLS:
        row.append(float(user.get(col, 0) or 0))

    vec = np.array(row, dtype=np.float32)

    # z-score first 9 continuous features with the same approach as training
    # (single-sample: we can't z-score properly, so we pass raw and rely on
    #  the model's learned weights to handle the scale)
    # NOTE: for production, save training μ/σ and apply them here.

    # Append liked listing averages if present
    liked_cols = (
        ["liked_mean_price", "liked_mean_beds", "liked_mean_sqfeet"]
        + sorted([k for k in user if k.startswith("liked_type_")])
    )
    if _meta and _meta.get("has_liked_listings") and "liked_mean_price" in user:
        liked = np.array(
            [float(user.get(c, 0) or 0) for c in liked_cols],
            dtype=np.float32
        )
        vec = np.concatenate([vec, liked])

    return vec.reshape(1, -1)


def _encode_listing(listing: Dict) -> np.ndarray:
    """
    Encode a Padly listing dict into the item tower input vector.

    Maps Padly DB schema → training feature schema.
    Missing features default to 0.
    """
    amenities = listing.get("amenities") or {}

    # Map Padly property_type to training type column
    prop_type_map = {
        "entire_place": "type_apartment",
        "private_room": "type_apartment",
        "shared_room":  "type_apartment",
    }
    listing_type_col = prop_type_map.get(listing.get("property_type", ""), "type_apartment")

    numeric = [
        float(listing.get("price_per_month") or 0),
        float(listing.get("area_sqft") or 0),
        float(listing.get("number_of_bedrooms") or 0),
        float(listing.get("number_of_bathrooms") or 0),
        float(amenities.get("cats_allowed", 0)),
        float(amenities.get("dogs_allowed", 0)),
        float(amenities.get("smoking_allowed", 0)),
        float(amenities.get("wheelchair_access", 0)),
        float(amenities.get("electric_vehicle_charge", 0)),
        float(1 if listing.get("furnished") else 0),
        float(listing.get("latitude") or 0),
        float(listing.get("longitude") or 0),
    ]

    # Build dummy columns in exact training order
    type_cols    = _meta["item_type_cols"]
    laundry_cols = _meta["item_laundry_cols"]
    parking_cols = _meta["item_parking_cols"]

    type_vec    = [1.0 if c == listing_type_col else 0.0 for c in type_cols]
    laundry_vec = [1.0 if c == "laundry_" else 0.0 for c in laundry_cols]   # unknown → empty
    parking_vec = [1.0 if c == "parking_" else 0.0 for c in parking_cols]   # unknown → empty

    vec = np.array(numeric + type_vec + laundry_vec + parking_vec, dtype=np.float32)
    return vec.reshape(1, -1)


# ── hard constraint filter ─────────────────────────────────────────────────

def _passes_hard_constraints(user: Dict, listing: Dict) -> bool:
    """Return True if the listing satisfies the user's non-negotiable constraints."""
    amenities = listing.get("amenities") or {}
    price = float(listing.get("price_per_month") or 0)

    budget_max = float(user.get("budget_max") or 0)
    if budget_max and price > budget_max * 1.20:
        return False
    if user.get("has_cats") and not amenities.get("cats_allowed"):
        return False
    if user.get("has_dogs") and not amenities.get("dogs_allowed"):
        return False
    if user.get("is_smoker") and not amenities.get("smoking_allowed"):
        return False
    if user.get("needs_wheelchair") and not amenities.get("wheelchair_access"):
        return False

    return True


# ── fallback scoring ────────────────────────────────────────────────────────

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance in kilometers.
    """
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def _relative_closeness(value: float, target: float, tolerance: float) -> float:
    if tolerance <= 0:
        return 0.5
    return _clamp01(1.0 - abs(value - target) / tolerance)


def _heuristic_match_score(user: Dict, listing: Dict) -> float:
    """
    Lightweight deterministic fallback score used when ML model is unavailable.
    """
    components: List[float] = []
    weights: List[float] = []
    amenities = listing.get("amenities") or {}

    # Budget proximity
    price = _safe_float(listing.get("price_per_month"))
    budget_min = _safe_float(user.get("budget_min"))
    budget_max = _safe_float(user.get("budget_max"))
    if budget_min > 0 or budget_max > 0:
        if budget_min > 0 and budget_max > 0:
            budget_target = (budget_min + budget_max) / 2.0
        else:
            budget_target = budget_max or budget_min
        budget_tol = max(250.0, budget_target * 0.75)
        components.append(_relative_closeness(price, budget_target, budget_tol))
        weights.append(0.40)

    # Bedroom preference
    desired_beds = _safe_float(user.get("desired_beds"))
    beds = _safe_float(listing.get("number_of_bedrooms"))
    if desired_beds > 0:
        components.append(_relative_closeness(beds, desired_beds, max(1.0, desired_beds)))
        weights.append(0.20)

    # Bathroom preference
    desired_baths = _safe_float(user.get("desired_baths"))
    baths = _safe_float(listing.get("number_of_bathrooms"))
    if desired_baths > 0:
        components.append(_relative_closeness(baths, desired_baths, max(1.0, desired_baths)))
        weights.append(0.15)

    # Furnished preference
    wants_furnished = user.get("wants_furnished")
    if wants_furnished is not None:
        pref = 1 if bool(wants_furnished) else 0
        listing_furnished = 1 if listing.get("furnished") else 0
        components.append(1.0 if pref == listing_furnished else 0.35)
        weights.append(0.10)

    # Optional geo preference
    pref_lat = _safe_float(user.get("pref_lat"))
    pref_lon = _safe_float(user.get("pref_lon"))
    lat = _safe_float(listing.get("latitude"))
    lon = _safe_float(listing.get("longitude"))
    if pref_lat and pref_lon and lat and lon:
        dist = _distance_km(pref_lat, pref_lon, lat, lon)
        max_dist = _safe_float(user.get("max_distance_km"))
        if max_dist > 0:
            components.append(_clamp01(1.0 - dist / max_dist))
        else:
            # Without explicit max distance, decay gently by distance.
            components.append(1.0 / (1.0 + dist / 15.0))
        weights.append(0.15)

    # Pet-friendly signal when relevant
    if user.get("has_cats"):
        components.append(1.0 if amenities.get("cats_allowed") else 0.0)
        weights.append(0.05)
    if user.get("has_dogs"):
        components.append(1.0 if amenities.get("dogs_allowed") else 0.0)
        weights.append(0.05)

    if not components:
        return 0.5
    return _clamp01(sum(c * w for c, w in zip(components, weights)) / sum(weights))


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _resolve_swipe_count(user: Dict) -> int:
    for key in ("behavior_sample_size", "sample_size", "total_swipes", "swipe_count"):
        if key in user:
            count = _coerce_int(user.get(key), default=0)
            if count >= 0:
                return count
    return 0


def _resolve_weight_profile(swipe_count: int, ml_available: bool) -> Dict[str, Any]:
    # PRD defaults by data maturity.
    if swipe_count < 20:
        profile = "cold"
        weights = {"rule": 0.80, "behavior": 0.20, "ml": 0.00}
    elif swipe_count < 100:
        profile = "warm"
        weights = {"rule": 0.50, "behavior": 0.25, "ml": 0.25}
    else:
        profile = "mature"
        weights = {"rule": 0.35, "behavior": 0.20, "ml": 0.45}

    if not ml_available and weights["ml"] > 0:
        # ML unavailable: force w_ml=0 and re-normalize rule/behavior.
        rule_behavior_total = weights["rule"] + weights["behavior"]
        if rule_behavior_total <= 0:
            weights = {"rule": 0.50, "behavior": 0.50, "ml": 0.00}
        else:
            weights = {
                "rule": weights["rule"] / rule_behavior_total,
                "behavior": weights["behavior"] / rule_behavior_total,
                "ml": 0.00,
            }

    return {
        "profile": profile,
        "weights": {
            "rule": round(float(weights["rule"]), 4),
            "behavior": round(float(weights["behavior"]), 4),
            "ml": round(float(weights["ml"]), 4),
        },
    }


def _behavior_similarity_score(user: Dict, listing: Dict) -> float:
    """
    Behavior score from swipe-derived liked listing averages.
    Returns neutral prior (0.5) when signal is missing/sparse.
    """
    liked_price = _safe_float(user.get("liked_mean_price"))
    liked_beds = _safe_float(user.get("liked_mean_beds"))
    liked_sqft = _safe_float(user.get("liked_mean_sqfeet"))

    price = _safe_float(listing.get("price_per_month"))
    beds = _safe_float(listing.get("number_of_bedrooms"))
    sqft = _safe_float(listing.get("area_sqft"))

    components: List[float] = []
    weights: List[float] = []

    if liked_price > 0 and price > 0:
        tol = max(300.0, liked_price * 0.60)
        components.append(_relative_closeness(price, liked_price, tol))
        weights.append(0.50)

    if liked_beds > 0 and beds > 0:
        tol = max(1.0, liked_beds)
        components.append(_relative_closeness(beds, liked_beds, tol))
        weights.append(0.20)

    if liked_sqft > 0 and sqft > 0:
        tol = max(250.0, liked_sqft * 0.60)
        components.append(_relative_closeness(sqft, liked_sqft, tol))
        weights.append(0.30)

    if not components:
        return 0.5
    return _clamp01(sum(c * w for c, w in zip(components, weights)) / sum(weights))


def _build_component_explainability(
    rule_score: float,
    behavior_score: float,
    ml_score: Optional[float],
    weights: Dict[str, float],
) -> Dict[str, Any]:
    labeled: List[Dict[str, Any]] = [
        {
            "label": "Rule preference alignment",
            "score": rule_score,
            "contribution": weights["rule"] * rule_score,
        },
        {
            "label": "Behavior similarity to liked listings",
            "score": behavior_score,
            "contribution": weights["behavior"] * behavior_score,
        },
    ]
    if ml_score is not None and weights["ml"] > 0:
        labeled.append(
            {
                "label": "Neural model affinity",
                "score": ml_score,
                "contribution": weights["ml"] * ml_score,
            }
        )

    labeled_sorted = sorted(labeled, key=lambda x: x["contribution"], reverse=True)
    positives = [x["label"] for x in labeled_sorted[:3]]
    negative = min(labeled, key=lambda x: x["score"])["label"] if labeled else None

    return {
        "hard_pass": True,
        "top_positive_contributors": positives,
        "top_negative_contributor": negative,
    }


def _score_with_blend(
    user: Dict,
    eligible: List[Dict],
    top_n: int,
    ml_scores: Optional[List[float]] = None,
) -> List[Dict]:
    swipe_count = _resolve_swipe_count(user)
    ml_available = ml_scores is not None
    profile = _resolve_weight_profile(swipe_count=swipe_count, ml_available=ml_available)
    weights = profile["weights"]
    algorithm_version = (
        f"phase2b-{profile['profile']}-{'with-ml' if ml_available and weights['ml'] > 0 else 'no-ml'}"
    )

    results = []
    for idx, listing in enumerate(eligible):
        rule_score = _clamp01(_heuristic_match_score(user, listing))
        behavior_score = _clamp01(_behavior_similarity_score(user, listing))
        ml_score: Optional[float] = None
        if ml_available and ml_scores is not None and idx < len(ml_scores):
            ml_score = _clamp01(_safe_float(ml_scores[idx], default=0.5))

        final_score = (
            (weights["rule"] * rule_score)
            + (weights["behavior"] * behavior_score)
            + (weights["ml"] * (ml_score if ml_score is not None else 0.0))
        )
        final_score = _clamp01(final_score)

        result = dict(listing)
        result["rule_score"] = round(float(rule_score), 4)
        result["behavior_score"] = round(float(behavior_score), 4)
        result["ml_score"] = round(float(ml_score), 4) if ml_score is not None and weights["ml"] > 0 else None
        result["match_score"] = round(float(final_score), 4)
        result["algorithm_version"] = algorithm_version
        result["score_breakdown"] = {
            "rule": result["rule_score"],
            "behavior": result["behavior_score"],
            "ml": result["ml_score"],
            "final": result["match_score"],
            "weights": weights,
            "weights_profile": profile["profile"],
            "swipe_count_used": swipe_count,
        }
        result["explainability"] = _build_component_explainability(
            rule_score=rule_score,
            behavior_score=behavior_score,
            ml_score=ml_score if weights["ml"] > 0 else None,
            weights=weights,
        )
        results.append(result)

    results.sort(key=lambda x: (x["match_score"], str(x.get("id") or "")), reverse=True)
    return results[:top_n]


# ── public API ─────────────────────────────────────────────────────────────

def score_listings(user: Dict, listings: List[Dict], top_n: int = 50) -> List[Dict]:
    """
    Score and rank listings for a user.

    Args:
        user:     dict of user preferences (see _encode_user for keys)
        listings: list of listing dicts from the Padly DB
        top_n:    max number of results to return

    Returns:
        List of listing dicts with an added "match_score" field (0.0 – 1.0),
        sorted by match_score descending.
    """
    _load()

    # Filter by hard constraints first
    eligible = [l for l in listings if _passes_hard_constraints(user, l)]

    if not eligible:
        return []

    # Graceful degradation when model or metadata cannot be loaded.
    if _model is None or _meta is None:
        return _score_with_blend(user, eligible, top_n, ml_scores=None)

    # Encode user once
    user_vec = _encode_user(user)
    user_dim = _meta["user_dim"]

    # Pad or trim to expected user_dim
    if user_vec.shape[1] < user_dim:
        pad = np.zeros((1, user_dim - user_vec.shape[1]), dtype=np.float32)
        user_vec = np.hstack([user_vec, pad])
    elif user_vec.shape[1] > user_dim:
        user_vec = user_vec[:, :user_dim]

    # Encode all eligible listings
    item_vecs = np.vstack([_encode_listing(l) for l in eligible])  # (N, item_dim)
    user_vecs = np.repeat(user_vec, len(eligible), axis=0)          # (N, user_dim)

    # Run model inference
    try:
        raw = _model.predict(
            {"user_features": user_vecs, "item_features": item_vecs},
            batch_size=512,
            verbose=0,
        )
        # Handle both output shapes:
        #   (N, 2) — 2-class softmax: column 1 is the match probability
        #   (N, 1) or (N,) — single sigmoid output
        if raw.ndim == 2 and raw.shape[1] >= 2:
            scores = raw[:, 1]
        else:
            scores = raw.reshape(-1)
    except Exception as e:
        print(f"[recommender] inference failed, using blended fallback without ML: {e}")
        return _score_with_blend(user, eligible, top_n, ml_scores=None)

    return _score_with_blend(user, eligible, top_n, ml_scores=[float(s) for s in scores])
