"""
Padly Recommender Service

Loads the trained Two-Tower model and scores listings for a given user.
Designed to be called from the API route — no ML knowledge needed outside this file.

Phase 3.1: exposes user_tower_latent / item_tower_latent and mean taste vectors from liked
listings (item tower). All embedding entrypoints return None when the model or towers are
unavailable — same graceful degradation as listing scoring.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from app.services.location_matching import (
    cities_match as _shared_cities_match,
    normalize_country as _shared_normalize_country,
    normalize_state as _shared_normalize_state,
)
from app.services.preferences_contract import (
    lease_types_compatible,
    normalize_gender_policy,
    normalize_lease_type,
    resolve_furnished_preference,
)

# ── paths ──────────────────────────────────────────────────────────────────

_AI_DIR = Path(__file__).parent
_MODEL_PATH = _AI_DIR / "artifacts" / "two_tower_baseline.keras"
_META_PATH  = _AI_DIR / "dataset" / "feature_meta.json"

# ── singleton model + metadata ─────────────────────────────────────────────

_model = None
_meta: Optional[Dict] = None
_model_disabled = False
_user_tower = None
_item_tower = None
_towers_resolved = False


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


def _resolve_tower_submodels():
    """
    Extract user/item tower submodels from the saved two-tower graph (see two_tower_baseline.py).
    Caches result; returns (user_tower, item_tower) or (None, None) if unavailable.
    """
    global _user_tower, _item_tower, _towers_resolved

    if _towers_resolved:
        return _user_tower, _item_tower

    _towers_resolved = True
    _user_tower, _item_tower = None, None

    _load()
    if _model is None:
        return None, None

    try:
        for layer in _model.layers:
            if layer.name == "user_tower":
                _user_tower = layer
            elif layer.name == "item_tower":
                _item_tower = layer
    except Exception as e:
        print(f"[recommender] could not resolve tower layers: {e}")

    if _user_tower is None or _item_tower is None:
        print(
            "[recommender] user_tower/item_tower layers missing; "
            "embedding APIs will return None until model layout matches training."
        )
        _user_tower, _item_tower = None, None

    return _user_tower, _item_tower


def embedding_inference_available() -> bool:
    """True when the two-tower model, metadata, and tower submodels are usable."""
    _load()
    ut, it = _resolve_tower_submodels()
    return _model is not None and _meta is not None and ut is not None and it is not None


def _pad_user_features(user_vec: np.ndarray) -> np.ndarray:
    """Align user features to metadata schema."""
    if _meta is None:
        return user_vec
    user_dim = int(_meta["user_dim"])
    if _meta.get("strict_user_feature_schema") and _meta.get("user_feature_cols"):
        if user_vec.shape[1] != user_dim:
            raise ValueError(
                f"user feature width mismatch: got {user_vec.shape[1]}, expected {user_dim}"
            )
        return user_vec
    if user_vec.shape[1] < user_dim:
        pad = np.zeros((user_vec.shape[0], user_dim - user_vec.shape[1]), dtype=np.float32)
        user_vec = np.hstack([user_vec, pad])
    elif user_vec.shape[1] > user_dim:
        user_vec = user_vec[:, :user_dim]
    return user_vec


def user_tower_latent(user: Dict) -> Optional[np.ndarray]:
    """
    Forward pass through the user tower only. Returns shape (embedding_dim,) or None if unavailable.
    """
    ut, _ = _resolve_tower_submodels()
    if ut is None or _meta is None:
        return None
    try:
        user_vec = _pad_user_features(_encode_user(user))
        out = ut.predict(user_vec, verbose=0)
        return np.asarray(out, dtype=np.float32).reshape(-1)
    except Exception as e:
        print(f"[recommender] user_tower_latent failed: {e}")
        return None


def item_tower_latent(listing: Dict) -> Optional[np.ndarray]:
    """
    Forward pass through the item tower only. Returns shape (embedding_dim,) or None if unavailable.
    """
    _, it = _resolve_tower_submodels()
    if it is None or _meta is None:
        return None
    try:
        item_vec = _encode_listing(listing)
        out = it.predict(item_vec, verbose=0)
        return np.asarray(out, dtype=np.float32).reshape(-1)
    except Exception as e:
        print(f"[recommender] item_tower_latent failed: {e}")
        return None


def item_tower_latent_batch(listings: List[Dict]) -> Optional[np.ndarray]:
    """Batch item tower forward. Returns array (N, embedding_dim) or None."""
    _, it = _resolve_tower_submodels()
    if it is None or _meta is None or not listings:
        return None
    try:
        mats = [_encode_listing(l) for l in listings]
        batch = np.vstack(mats)
        out = it.predict(batch, verbose=0)
        return np.asarray(out, dtype=np.float32)
    except Exception as e:
        print(f"[recommender] item_tower_latent_batch failed: {e}")
        return None


def _fetch_listings_for_item_tower(listing_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Load listing rows with fields required by _encode_listing."""
    if not listing_ids:
        return {}
    from app.dependencies.supabase import get_admin_client

    supabase = get_admin_client()
    out: Dict[str, Dict[str, Any]] = {}
    chunk_size = 200
    for i in range(0, len(listing_ids), chunk_size):
        chunk = listing_ids[i : i + chunk_size]
        response = (
            supabase.table("listings")
            .select(
                "id, price_per_month, number_of_bedrooms, number_of_bathrooms, area_sqft, "
                "furnished, utilities_included, amenities, latitude, longitude, property_type"
            )
            .in_("id", chunk)
            .execute()
        )
        for row in response.data or []:
            rid = row.get("id")
            if rid is not None:
                out[str(rid)] = row
    return out


def _cosine_to_unit_interval(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity mapped from [-1, 1] to [0, 1]."""
    a = np.asarray(a, dtype=np.float64).reshape(-1)
    b = np.asarray(b, dtype=np.float64).reshape(-1)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.5
    cos = float(np.dot(a, b) / (na * nb))
    return _clamp01((cos + 1.0) / 2.0)


def _l2_normalize_vector(v: np.ndarray) -> np.ndarray:
    x = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(x))
    if n <= 1e-12:
        return x
    return (x / n).astype(np.float32)


def mean_taste_item_embedding(
    user_id: str,
    *,
    k: int = 50,
    days: int = 180,
    max_events: int = 2000,
) -> Optional[np.ndarray]:
    """
    Mean of item-tower embeddings over up to k distinct positively swiped listings (recent first).
    The mean vector is L2-normalized for stable cosine similarity vs other users.
    Returns None if the model is off, metadata missing, or there are no encodable likes.
    """
    if not embedding_inference_available():
        return None

    from app.services.behavior_features import POSITIVE_ACTIONS, _fetch_user_swipes

    events = _fetch_user_swipes(user_id=user_id, days=days, max_events=max_events)
    positive = [
        e for e in events if e.get("action") in POSITIVE_ACTIONS and e.get("listing_id")
    ]
    seen = set()
    listing_ids: List[str] = []
    for e in positive:
        lid = str(e.get("listing_id"))
        if lid in seen:
            continue
        seen.add(lid)
        listing_ids.append(lid)
        if len(listing_ids) >= max(1, k):
            break

    if not listing_ids:
        return None

    rows = _fetch_listings_for_item_tower(listing_ids)
    ordered = [rows[lid] for lid in listing_ids if lid in rows]
    if not ordered:
        return None

    embs = item_tower_latent_batch(ordered)
    if embs is None or embs.size == 0:
        return None

    mean_vec = np.mean(embs, axis=0)
    return _l2_normalize_vector(mean_vec)


def taste_similarity_from_mean_embeddings(
    embedding_a: Optional[np.ndarray],
    embedding_b: Optional[np.ndarray],
) -> Optional[float]:
    """Map cosine similarity between two mean taste vectors to [0, 1]. None if either is missing."""
    if embedding_a is None or embedding_b is None:
        return None
    return _cosine_to_unit_interval(embedding_a, embedding_b)


def taste_embedding_similarity_users(
    user_id_a: str,
    user_id_b: str,
    *,
    k: int = 50,
    days: int = 180,
    max_events: int = 2000,
) -> Optional[float]:
    """
    Cosine-based similarity in [0, 1] between mean taste vectors of two users.
    None if either side has no usable embedding.
    """
    ea = mean_taste_item_embedding(user_id_a, k=k, days=days, max_events=max_events)
    eb = mean_taste_item_embedding(user_id_b, k=k, days=days, max_events=max_events)
    return taste_similarity_from_mean_embeddings(ea, eb)


# ── feature encoding ───────────────────────────────────────────────────────

# Legacy fallback numeric columns (for old metadata without user_feature_cols)
_LEGACY_USER_NUMERIC_COLS = [
    "age", "household_size", "income", "credit_score",
    "budget_min", "budget_max",
    "desired_beds", "desired_baths", "desired_sqft_min",
    "has_cats", "has_dogs", "is_smoker",
    "needs_wheelchair", "has_ev", "wants_furnished",
    "pref_lat", "pref_lon", "max_distance_km",
    "laundry_pref", "parking_pref", "move_urgency",
]

# Legacy fallback type-pref columns (for old metadata without user_feature_cols)
_LEGACY_USER_TYPE_PREF_COLS = sorted([
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


_FRONTEND_FURNISHED_PREFERENCES = ["required", "preferred", "no_preference"]
_FRONTEND_GENDER_POLICIES = ["same_gender_only", "mixed_ok"]
_FRONTEND_LEASE_TYPES = ["fixed", "month_to_month", "sublet", "any"]


def _coerce_feature_value(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().lower()
    if not raw:
        return 0.0
    if raw in {"true", "t", "yes", "y"}:
        return 1.0
    if raw in {"false", "f", "no", "n"}:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _derive_user_feature_values(user: Dict) -> Dict[str, Any]:
    values = dict(user or {})

    # Frontend contract aliases
    if values.get("desired_beds") is None:
        values["desired_beds"] = values.get("required_bedrooms")
    if values.get("desired_baths") is None:
        values["desired_baths"] = values.get("target_bathrooms")

    furnished_preference = resolve_furnished_preference(
        values.get("furnished_preference"),
        values.get("target_furnished"),
    )
    if furnished_preference is None:
        wants_furnished = _coerce_feature_value(values.get("wants_furnished")) > 0
        furnished_preference = "preferred" if wants_furnished else "no_preference"

    values["furnished_preference"] = furnished_preference
    values["wants_furnished"] = 1.0 if furnished_preference in {"required", "preferred"} else 0.0
    for pref in _FRONTEND_FURNISHED_PREFERENCES:
        values[f"furnished_pref_{pref}"] = 1.0 if furnished_preference == pref else 0.0

    gender_policy = normalize_gender_policy(values.get("gender_policy")) or "mixed_ok"
    values["gender_policy"] = gender_policy
    for policy in _FRONTEND_GENDER_POLICIES:
        values[f"gender_policy_{policy}"] = 1.0 if gender_policy == policy else 0.0

    lease_type = normalize_lease_type(values.get("target_lease_type")) or "any"
    values["target_lease_type"] = lease_type
    for lt in _FRONTEND_LEASE_TYPES:
        values[f"target_lease_type_{lt}"] = 1.0 if lease_type == lt else 0.0

    if values.get("target_lease_duration_months") is None and lease_type == "month_to_month":
        values["target_lease_duration_months"] = 1

    if values.get("target_deposit_amount") is None and values.get("budget_max") is not None:
        values["target_deposit_amount"] = values.get("budget_max")

    return values


def _meta_user_feature_cols() -> Optional[List[str]]:
    if _meta is None:
        return None
    cols = _meta.get("user_feature_cols")
    if not isinstance(cols, list) or not cols:
        return None
    cols = [str(c) for c in cols]
    if len(cols) != len(set(cols)):
        raise ValueError("feature_meta.json has duplicated user_feature_cols")
    return cols


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
    values = _derive_user_feature_values(user)
    schema_cols = _meta_user_feature_cols()
    if schema_cols:
        vec = np.array(
            [_coerce_feature_value(values.get(col, 0)) for col in schema_cols],
            dtype=np.float32,
        )
        return vec.reshape(1, -1)

    # Fallback for legacy metadata files
    row = []
    for col in _LEGACY_USER_NUMERIC_COLS:
        row.append(_coerce_feature_value(values.get(col, 0)))
    for col in _LEGACY_USER_TYPE_PREF_COLS:
        row.append(_coerce_feature_value(values.get(col, 0)))

    vec = np.array(row, dtype=np.float32)

    # z-score first 9 continuous features with the same approach as training
    # (single-sample: we can't z-score properly, so we pass raw and rely on
    #  the model's learned weights to handle the scale)
    # NOTE: for production, save training μ/σ and apply them here.

    # Append liked listing averages if present
    liked_cols = (
        ["liked_mean_price", "liked_mean_beds", "liked_mean_sqfeet"]
        + sorted([k for k in values if k.startswith("liked_type_")])
    )
    if _meta and _meta.get("has_liked_listings") and "liked_mean_price" in values:
        liked = np.array(
            [_coerce_feature_value(values.get(c, 0)) for c in liked_cols],
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

def _normalize_country(value: Any) -> str:
    return _shared_normalize_country(value)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_state(value: Any) -> str:
    return _shared_normalize_state(value)


def _normalize_city(value: Any) -> str:
    raw = _normalize_text(value)
    if " (" in raw:
        raw = raw.split(" (", 1)[0].strip()
    return raw


def _city_matches(target: str, listing: str) -> bool:
    return _shared_cities_match(target, listing)


def _parse_iso_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "t", "1", "yes", "y"}


def _passes_hard_constraints(user: Dict, listing: Dict) -> bool:
    """Return True if the listing satisfies all listing-relevant hard constraints."""
    amenities = listing.get("amenities") or {}
    price = _safe_float(listing.get("price_per_month"))

    # Location hard constraints
    target_city = _normalize_text(user.get("target_city"))
    listing_city = _normalize_text(listing.get("city"))
    if target_city and listing_city and not _city_matches(target_city, listing_city):
        return False

    target_state = _normalize_state(user.get("target_state_province"))
    listing_state = _normalize_state(listing.get("state_province"))
    if target_state and listing_state and target_state != listing_state:
        return False

    target_country = _normalize_country(user.get("target_country"))
    listing_country = _normalize_country(listing.get("country"))
    if target_country and listing_country and target_country != listing_country:
        return False

    # Budget hard constraints
    budget_min = _safe_float(user.get("budget_min"))
    if budget_min > 0 and price < budget_min:
        return False

    budget_max = _safe_float(user.get("budget_max"))
    if budget_max > 0 and price > budget_max:
        return False

    # Beds / baths minimum hard constraints
    required_bedrooms = _safe_float(user.get("required_bedrooms") or user.get("desired_beds"))
    listing_bedrooms = _safe_float(listing.get("number_of_bedrooms"))
    if required_bedrooms > 0 and listing_bedrooms > 0 and listing_bedrooms < required_bedrooms:
        return False

    target_bathrooms = _safe_float(user.get("target_bathrooms") or user.get("desired_baths"))
    listing_bathrooms = _safe_float(listing.get("number_of_bathrooms"))
    if target_bathrooms > 0 and listing_bathrooms > 0 and listing_bathrooms < target_bathrooms:
        return False

    # Deposit hard cap only when an explicit deposit is known.
    target_deposit = _safe_float(user.get("target_deposit_amount"))
    if target_deposit > 0:
        listing_deposit = _safe_float(listing.get("deposit_amount"))
        if listing_deposit > 0 and listing_deposit > target_deposit:
            return False

    # Furnished is hard only when explicitly required
    furnished_pref = resolve_furnished_preference(
        user.get("furnished_preference"),
        user.get("target_furnished"),
    )
    if furnished_pref == "required" and not _as_bool(listing.get("furnished")):
        return False

    # Move-in date hard window (+/- 60 days)
    target_move_in = _parse_iso_date(user.get("move_in_date"))
    listing_available_from = _parse_iso_date(listing.get("available_from"))
    if target_move_in and listing_available_from:
        if abs((listing_available_from - target_move_in).days) > 60:
            return False

    # Lease type and duration hard constraints
    if not lease_types_compatible(user.get("target_lease_type"), listing.get("lease_type")):
        return False

    target_duration = _safe_float(user.get("target_lease_duration_months"))
    listing_duration = _safe_float(listing.get("lease_duration_months"))
    if target_duration > 0 and listing_duration > 0 and int(listing_duration) != int(target_duration):
        return False

    # Amenity safety hard constraints
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

    try:
        # Encode user once
        user_vec = _pad_user_features(_encode_user(user))

        # Encode all eligible listings
        item_vecs = np.vstack([_encode_listing(l) for l in eligible])  # (N, item_dim)
        user_vecs = np.repeat(user_vec, len(eligible), axis=0)         # (N, user_dim)
    except Exception as e:
        print(f"[recommender] feature encoding failed, using blended fallback without ML: {e}")
        return _score_with_blend(user, eligible, top_n, ml_scores=None)

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
