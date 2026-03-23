"""
Roommate matching Phase 1: behavioral fingerprint from positive listing swipes
and pairwise similarity with cold-start handling.

See plan: Phase 1 similarity v0 (roommate-fp-v1 vector + cosine similarity).
"""

from __future__ import annotations

import math
from math import ceil
from typing import Any, Dict, List, Optional, Tuple

from app.services.listing_category import NUM_LISTING_CATEGORIES, categorize_padly_listing

# Keep in sync with app.services.behavior_features.POSITIVE_ACTIONS (avoid importing that module at load time).
_POSITIVE_SWIPE_ACTIONS = frozenset({"like", "super_like"})

ROOMMATE_FP_VERSION = "roommate-fp-v1"
ROOMMATE_BEHAVIOR_MIN_SWIPES = 5
VECTOR_DIM = 10  # 3 continuous + 6 histogram + 1 confidence

# log(price) clamps for dim 0 (match plan ~ $300–$15k scale)
_LOG_PRICE_MIN = math.log(300.0)
_LOG_PRICE_MAX = math.log(15000.0)


def _chunked(values: List[str], size: int = 200) -> List[List[str]]:
    if not values:
        return []
    nchunks = int(ceil(len(values) / size))
    return [values[i * size : (i + 1) * size] for i in range(nchunks)]


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fetch_listings_for_fingerprint(listing_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not listing_ids:
        return {}
    from app.dependencies.supabase import get_admin_client

    supabase = get_admin_client()
    out: Dict[str, Dict[str, Any]] = {}
    for chunk in _chunked(listing_ids, size=200):
        response = (
            supabase.table("listings")
            .select(
                "id, price_per_month, number_of_bedrooms, area_sqft, furnished, utilities_included, amenities"
            )
            .in_("id", chunk)
            .execute()
        )
        for row in response.data or []:
            out[str(row.get("id"))] = row
    return out


def scale_log_price_value(price: Optional[float]) -> float:
    """
    Map a monthly price to [0, 1] via log clamp (log space, not log1p, for interpretability).
    Missing or non-positive price → 0.0.
    """
    if price is None or price <= 0:
        return 0.0
    lp = math.log(price)
    if lp <= _LOG_PRICE_MIN:
        return 0.0
    if lp >= _LOG_PRICE_MAX:
        return 1.0
    return (lp - _LOG_PRICE_MIN) / (_LOG_PRICE_MAX - _LOG_PRICE_MIN)


def build_vector_from_liked_listings(
    liked_listings: List[Dict[str, Any]],
) -> Tuple[List[float], Dict[str, Any]]:
    """
    Build the fixed roommate-fp-v1 vector from listing dicts (positive swipes only).

    Layout:
      [0] scaled log mean price
      [1] mean beds / 5 (cap 1)
      [2] mean sqft / 3000 (cap 1)
      [3:9] L1-normalized category histogram (uniform 1/6 if no likes)
      [9] sqrt(n_likes) / 10, cap 1.0
    """
    n = len(liked_listings)
    prices: List[float] = []
    beds_l: List[float] = []
    sqft_l: List[float] = []
    hist = [0.0] * NUM_LISTING_CATEGORIES

    for row in liked_listings:
        p = _safe_float(row.get("price_per_month"))
        if p is not None and p > 0:
            prices.append(p)
        b = _safe_float(row.get("number_of_bedrooms"))
        if b is not None:
            beds_l.append(b)
        s = _safe_float(row.get("area_sqft"))
        if s is not None and s > 0:
            sqft_l.append(s)
        cat = categorize_padly_listing(row)
        if 0 <= cat < NUM_LISTING_CATEGORIES:
            hist[cat] += 1.0

    mean_price = sum(prices) / len(prices) if prices else None
    mean_beds = sum(beds_l) / len(beds_l) if beds_l else None
    mean_sqft = sum(sqft_l) / len(sqft_l) if sqft_l else None

    v0 = scale_log_price_value(mean_price)
    v1 = min((mean_beds or 0.0) / 5.0, 1.0) if mean_beds is not None else 0.0
    v2 = min((mean_sqft or 0.0) / 3000.0, 1.0) if mean_sqft is not None else 0.0

    if n > 0 and sum(hist) > 0:
        s = sum(hist)
        hist_norm = [h / s for h in hist]
    else:
        hist_norm = [1.0 / NUM_LISTING_CATEGORIES] * NUM_LISTING_CATEGORIES

    conf = min(math.sqrt(float(n)), 10.0) / 10.0

    vector = [v0, v1, v2] + hist_norm + [conf]

    meta = {
        "liked_listing_count": n,
        "liked_mean_price": mean_price,
        "liked_mean_beds": mean_beds,
        "liked_mean_sqft": mean_sqft,
        "category_counts": hist if n > 0 else [0.0] * NUM_LISTING_CATEGORIES,
    }
    return vector, meta


def neutral_behavior_vector() -> List[float]:
    """Mid-range continuous dims + uniform category prior + zero confidence."""
    return [0.5, 0.3, 0.3] + [1.0 / NUM_LISTING_CATEGORIES] * NUM_LISTING_CATEGORIES + [0.0]


def build_prefs_proxy_vector(prefs: Optional[Dict[str, Any]]) -> List[float]:
    """
    Cold-user proxy from personal_preferences row (budget + bedrooms only).
    Uniform histogram; confidence 0.
    """
    if not prefs:
        return neutral_behavior_vector()

    bmin = _safe_float(prefs.get("budget_min"))
    bmax = _safe_float(prefs.get("budget_max"))
    mid: Optional[float] = None
    if bmin is not None and bmax is not None:
        mid = (bmin + bmax) / 2.0
    elif bmax is not None:
        mid = bmax
    elif bmin is not None:
        mid = bmin

    v0 = scale_log_price_value(mid) if mid is not None and mid > 0 else 0.0
    rb = prefs.get("required_bedrooms")
    try:
        v1 = min(float(rb) / 5.0, 1.0) if rb is not None else 0.0
    except (TypeError, ValueError):
        v1 = 0.0
    v2 = 0.0
    hist = [1.0 / NUM_LISTING_CATEGORIES] * NUM_LISTING_CATEGORIES
    return [v0, v1, v2] + hist + [0.0]


def build_roommate_behavior_fingerprint(
    user_id: str,
    days: int = 180,
    max_events: int = 2000,
) -> Dict[str, Any]:
    """
    Load swipe events + listing rows and return fingerprint dict for one user.
    """
    from app.services.behavior_features import _fetch_user_swipes

    events = _fetch_user_swipes(user_id=user_id, days=days, max_events=max_events)
    positive = [
        e
        for e in events
        if e.get("action") in _POSITIVE_SWIPE_ACTIONS and e.get("listing_id")
    ]
    listing_ids = list({str(e.get("listing_id")) for e in positive})
    listing_map = _fetch_listings_for_fingerprint(listing_ids)

    liked_listings: List[Dict[str, Any]] = []
    for e in positive:
        lid = str(e.get("listing_id"))
        row = listing_map.get(lid)
        if row:
            liked_listings.append(row)

    vector, meta = build_vector_from_liked_listings(liked_listings)
    positive_swipe_count = len(positive)

    return {
        "version": ROOMMATE_FP_VERSION,
        "vector": vector,
        "positive_swipe_count": positive_swipe_count,
        "metadata": meta,
    }


def fetch_personal_preferences_row(user_id: str) -> Optional[Dict[str, Any]]:
    from app.dependencies.supabase import get_admin_client

    supabase = get_admin_client()
    response = (
        supabase.table("personal_preferences")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Vectors must have same length")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.5
    cos = dot / (na * nb)
    return max(0.0, min(1.0, cos))


def similarity_behavior(
    fp_u: Dict[str, Any],
    fp_v: Dict[str, Any],
    *,
    prefs_u: Optional[Dict[str, Any]] = None,
    prefs_v: Optional[Dict[str, Any]] = None,
    k: int = ROOMMATE_BEHAVIOR_MIN_SWIPES,
) -> Dict[str, Any]:
    """
    Pairwise behavioral similarity in [0, 1] (cosine on non-negative fp vectors).

    - Both users with positive_swipe_count < k: cold_cold, similarity None.
    - One cold: substitute proxy vector from prefs if provided, else neutral_behavior_vector.
    - Warm–warm: cosine of stored vectors.

    Returns:
      similarity: float | None
      cold_cold: bool
      behavior_confidence: "high" | "mixed" | "low"
      used_prefs_proxy_u / used_prefs_proxy_v: bool
    """
    cu = int(fp_u.get("positive_swipe_count") or 0)
    cv = int(fp_v.get("positive_swipe_count") or 0)
    warm_u = cu >= k
    warm_v = cv >= k

    vec_u = list(fp_u.get("vector") or [])
    vec_v = list(fp_v.get("vector") or [])
    if len(vec_u) != VECTOR_DIM or len(vec_v) != VECTOR_DIM:
        raise ValueError(f"Expected vector length {VECTOR_DIM}")

    used_proxy_u = False
    used_proxy_v = False

    if not warm_u and not warm_v:
        return {
            "similarity": None,
            "cold_cold": True,
            "behavior_confidence": "low",
            "used_prefs_proxy_u": False,
            "used_prefs_proxy_v": False,
            "note": "Both users below behavior swipe threshold; do not rank on behavior alone.",
        }

    if not warm_u:
        vec_u = build_prefs_proxy_vector(prefs_u) if prefs_u else neutral_behavior_vector()
        used_proxy_u = True
    if not warm_v:
        vec_v = build_prefs_proxy_vector(prefs_v) if prefs_v else neutral_behavior_vector()
        used_proxy_v = True

    sim = _cosine_similarity(vec_u, vec_v)

    if warm_u and warm_v:
        confidence = "high"
    elif used_proxy_u or used_proxy_v:
        confidence = "mixed"
    else:
        confidence = "low"

    return {
        "similarity": sim,
        "cold_cold": False,
        "behavior_confidence": confidence,
        "used_prefs_proxy_u": used_proxy_u,
        "used_prefs_proxy_v": used_proxy_v,
    }


__all__ = [
    "ROOMMATE_FP_VERSION",
    "ROOMMATE_BEHAVIOR_MIN_SWIPES",
    "VECTOR_DIM",
    "build_prefs_proxy_vector",
    "build_roommate_behavior_fingerprint",
    "build_vector_from_liked_listings",
    "fetch_personal_preferences_row",
    "neutral_behavior_vector",
    "scale_log_price_value",
    "similarity_behavior",
]
