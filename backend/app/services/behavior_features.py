"""
Behavior feature extraction utilities for Phase 2A.

Builds user and group behavior vectors from swipe_interactions events.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.dependencies.supabase import get_admin_client


POSITIVE_ACTIONS = {"like", "super_like"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: Iterable[float]) -> Optional[float]:
    values = list(values)
    if not values:
        return None
    return sum(values) / len(values)


def _percentile(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * (p / 100.0)
    low = int(k)
    high = min(low + 1, len(values_sorted) - 1)
    if low == high:
        return values_sorted[low]
    ratio = k - low
    return (values_sorted[low] * (1 - ratio)) + (values_sorted[high] * ratio)


def _top_counts(counter: Counter, limit: int = 5, key_name: str = "value") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for key, count in counter.most_common(limit):
        as_float = float(count)
        as_int = int(as_float)
        normalized_count: Any = as_int if as_float.is_integer() else round(as_float, 4)
        out.append({key_name: key, "count": normalized_count})
    return out


def _chunked(values: List[str], size: int = 200) -> List[List[str]]:
    if not values:
        return []
    chunks = int(ceil(len(values) / size))
    return [values[i * size: (i + 1) * size] for i in range(chunks)]


def _fetch_user_swipes(user_id: str, days: int = 180, max_events: int = 2000) -> List[Dict[str, Any]]:
    since = (_utcnow() - timedelta(days=max(1, days))).isoformat()
    supabase = get_admin_client()
    response = (
        supabase.table("swipe_interactions")
        .select(
            "event_id, actor_user_id, listing_id, action, surface, session_id, "
            "position_in_feed, algorithm_version, model_version, city_filter, latency_ms, created_at"
        )
        .eq("actor_user_id", user_id)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(max_events)
        .execute()
    )
    return response.data or []


def _fetch_listing_features(listing_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not listing_ids:
        return {}

    supabase = get_admin_client()
    listing_map: Dict[str, Dict[str, Any]] = {}
    for chunk in _chunked(listing_ids, size=200):
        response = (
            supabase.table("listings")
            .select("id, price_per_month, number_of_bedrooms, number_of_bathrooms, area_sqft, city, property_type")
            .in_("id", chunk)
            .execute()
        )
        for row in (response.data or []):
            listing_map[str(row.get("id"))] = row
    return listing_map


def build_user_behavior_vector(
    user_id: str,
    days: int = 180,
    max_events: int = 2000,
) -> Dict[str, Any]:
    events = _fetch_user_swipes(user_id=user_id, days=days, max_events=max_events)
    total_events = len(events)

    like_count = sum(1 for e in events if e.get("action") == "like")
    pass_count = sum(1 for e in events if e.get("action") == "pass")
    super_like_count = sum(1 for e in events if e.get("action") == "super_like")
    positive_count = like_count + super_like_count

    now = _utcnow()
    recent_cutoff = now - timedelta(days=30)
    recent_events = [e for e in events if (_parse_dt(e.get("created_at")) or now) >= recent_cutoff]
    recent_positive = [e for e in recent_events if e.get("action") in POSITIVE_ACTIONS]

    positive_events = [
        e for e in events
        if e.get("action") in POSITIVE_ACTIONS and e.get("listing_id")
    ]
    positive_listing_ids = list({
        str(e.get("listing_id"))
        for e in positive_events
    })
    listing_map = _fetch_listing_features(positive_listing_ids)

    liked_prices: List[float] = []
    liked_beds: List[float] = []
    liked_baths: List[float] = []
    liked_sqft: List[float] = []
    liked_city_counter: Counter = Counter()
    liked_type_counter: Counter = Counter()

    for event in positive_events:
        listing_id = str(event.get("listing_id"))
        listing = listing_map.get(listing_id)
        if not listing:
            continue
        price = _safe_float(listing.get("price_per_month"))
        beds = _safe_float(listing.get("number_of_bedrooms"))
        baths = _safe_float(listing.get("number_of_bathrooms"))
        sqft = _safe_float(listing.get("area_sqft"))
        if price is not None:
            liked_prices.append(price)
        if beds is not None:
            liked_beds.append(beds)
        if baths is not None:
            liked_baths.append(baths)
        if sqft is not None:
            liked_sqft.append(sqft)
        city = str(listing.get("city") or "").strip()
        if city:
            liked_city_counter[city] += 1
        ptype = str(listing.get("property_type") or "").strip()
        if ptype:
            liked_type_counter[ptype] += 1

    missing_algorithm_version_count = sum(1 for e in events if not str(e.get("algorithm_version") or "").strip())
    missing_session_id_count = sum(1 for e in events if not str(e.get("session_id") or "").strip())
    latency_values = [
        float(e["latency_ms"])
        for e in events
        if e.get("latency_ms") is not None and _safe_float(e.get("latency_ms")) is not None
    ]

    vector = {
        "version": "phase2a-v1",
        "window_days": days,
        "sample_size": total_events,
        "total_swipes": total_events,
        "like_count": like_count,
        "pass_count": pass_count,
        "super_like_count": super_like_count,
        "positive_rate": round((positive_count / total_events), 4) if total_events else None,
        "recent_30d_swipes": len(recent_events),
        "recent_30d_positive_rate": (
            round((len(recent_positive) / len(recent_events)), 4) if recent_events else None
        ),
        "liked_mean_price": _mean(liked_prices),
        "liked_mean_beds": _mean(liked_beds),
        "liked_mean_baths": _mean(liked_baths),
        "liked_mean_sqfeet": _mean(liked_sqft),
        "top_liked_cities": _top_counts(liked_city_counter, limit=5, key_name="city"),
        "top_liked_property_types": _top_counts(liked_type_counter, limit=5, key_name="property_type"),
        "data_quality": {
            "missing_algorithm_version_rate": (
                round(missing_algorithm_version_count / total_events, 4) if total_events else None
            ),
            "missing_session_id_rate": (
                round(missing_session_id_count / total_events, 4) if total_events else None
            ),
            "latency_samples": len(latency_values),
            "latency_p50_ms": _percentile(latency_values, 50),
            "latency_p95_ms": _percentile(latency_values, 95),
        },
    }
    return vector


def _normalized_with_cap(base_weights: List[float], cap: float = 0.40) -> List[float]:
    if not base_weights:
        return []

    positive = [max(0.0, float(v)) for v in base_weights]
    total = sum(positive)
    if total <= 0:
        n = len(positive)
        return [round(1.0 / n, 6) for _ in range(n)]

    weights = [v / total for v in positive]
    fixed = set()

    for _ in range(20):
        over = [i for i, w in enumerate(weights) if i not in fixed and w > cap]
        if not over:
            break

        for i in over:
            weights[i] = cap
            fixed.add(i)

        remaining_indices = [i for i in range(len(weights)) if i not in fixed]
        if not remaining_indices:
            break
        remaining_mass = 1.0 - sum(weights[i] for i in fixed)
        if remaining_mass <= 0:
            break
        remaining_base = sum(positive[i] for i in remaining_indices)
        if remaining_base <= 0:
            equal = remaining_mass / len(remaining_indices)
            for i in remaining_indices:
                weights[i] = equal
        else:
            for i in remaining_indices:
                weights[i] = remaining_mass * (positive[i] / remaining_base)

    final_total = sum(weights)
    if final_total > 0:
        weights = [w / final_total for w in weights]
    return [round(w, 6) for w in weights]


def _weighted_mean(values: List[Optional[float]], weights: List[float]) -> Optional[float]:
    pairs = [(v, w) for v, w in zip(values, weights) if v is not None]
    if not pairs:
        return None
    den = sum(w for _, w in pairs)
    if den <= 0:
        return None
    return sum(v * w for v, w in pairs) / den


def build_group_behavior_vector(
    group_id: str,
    days: int = 180,
    max_events_per_user: int = 2000,
) -> Dict[str, Any]:
    supabase = get_admin_client()
    members_response = (
        supabase.table("group_members")
        .select("user_id, status")
        .eq("group_id", group_id)
        .eq("status", "accepted")
        .execute()
    )
    member_ids = [str(row.get("user_id")) for row in (members_response.data or []) if row.get("user_id")]
    member_ids = list(dict.fromkeys(member_ids))

    if not member_ids:
        return {
            "version": "phase2a-v1",
            "group_id": group_id,
            "window_days": days,
            "member_count": 0,
            "sample_size": 0,
            "weights": [],
            "vector": {},
        }

    member_vectors: List[Tuple[str, Dict[str, Any]]] = []
    for user_id in member_ids:
        member_vectors.append((user_id, build_user_behavior_vector(user_id, days=days, max_events=max_events_per_user)))

    base_weights = [max(1.0, float(vec.get("sample_size") or 0)) for _, vec in member_vectors]
    capped_weights = _normalized_with_cap(base_weights, cap=0.40)

    positive_rates = [vec.get("positive_rate") for _, vec in member_vectors]
    liked_mean_price = [vec.get("liked_mean_price") for _, vec in member_vectors]
    liked_mean_beds = [vec.get("liked_mean_beds") for _, vec in member_vectors]
    liked_mean_baths = [vec.get("liked_mean_baths") for _, vec in member_vectors]
    liked_mean_sqfeet = [vec.get("liked_mean_sqfeet") for _, vec in member_vectors]

    city_counter: Counter = Counter()
    type_counter: Counter = Counter()
    for (_, vec), weight in zip(member_vectors, capped_weights):
        for item in (vec.get("top_liked_cities") or []):
            city = str(item.get("city") or "").strip()
            count = _safe_float(item.get("count")) or 0.0
            if city and count > 0:
                city_counter[city] += count * weight
        for item in (vec.get("top_liked_property_types") or []):
            ptype = str(item.get("property_type") or "").strip()
            count = _safe_float(item.get("count")) or 0.0
            if ptype and count > 0:
                type_counter[ptype] += count * weight

    total_sample_size = int(sum(int(vec.get("sample_size") or 0) for _, vec in member_vectors))
    weights_payload = [
        {
            "user_id": user_id,
            "raw_weight": round(base_weight / sum(base_weights), 6) if sum(base_weights) else 0.0,
            "capped_weight": capped_weight,
            "sample_size": int(vec.get("sample_size") or 0),
        }
        for (user_id, vec), base_weight, capped_weight in zip(member_vectors, base_weights, capped_weights)
    ]

    return {
        "version": "phase2a-v1",
        "group_id": group_id,
        "window_days": days,
        "member_count": len(member_vectors),
        "sample_size": total_sample_size,
        "weights": weights_payload,
        "vector": {
            "positive_rate": _weighted_mean(positive_rates, capped_weights),
            "liked_mean_price": _weighted_mean(liked_mean_price, capped_weights),
            "liked_mean_beds": _weighted_mean(liked_mean_beds, capped_weights),
            "liked_mean_baths": _weighted_mean(liked_mean_baths, capped_weights),
            "liked_mean_sqfeet": _weighted_mean(liked_mean_sqfeet, capped_weights),
            "top_liked_cities": _top_counts(city_counter, limit=5, key_name="city"),
            "top_liked_property_types": _top_counts(type_counter, limit=5, key_name="property_type"),
        },
    }


def get_swipe_health_summary(days: int = 7, max_events: int = 10000) -> Dict[str, Any]:
    since = (_utcnow() - timedelta(days=max(1, days))).isoformat()
    supabase = get_admin_client()
    response = (
        supabase.table("swipe_interactions")
        .select(
            "event_id, actor_user_id, action, surface, session_id, position_in_feed, "
            "algorithm_version, model_version, latency_ms, created_at"
        )
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(max_events)
        .execute()
    )
    events = response.data or []
    total = len(events)

    action_counter: Counter = Counter()
    surface_counter: Counter = Counter()
    user_ids = set()
    latency_values: List[float] = []
    created_at_values: List[datetime] = []
    missing_algorithm_version = 0
    missing_session_id = 0
    null_position = 0

    for event in events:
        action_counter[str(event.get("action") or "").strip().lower()] += 1
        surface_counter[str(event.get("surface") or "").strip().lower()] += 1
        if event.get("actor_user_id"):
            user_ids.add(str(event.get("actor_user_id")))
        if not str(event.get("algorithm_version") or "").strip():
            missing_algorithm_version += 1
        if not str(event.get("session_id") or "").strip():
            missing_session_id += 1
        if event.get("position_in_feed") is None:
            null_position += 1
        latency = _safe_float(event.get("latency_ms"))
        if latency is not None:
            latency_values.append(latency)
        created = _parse_dt(event.get("created_at"))
        if created is not None:
            created_at_values.append(created)

    newest = max(created_at_values).isoformat() if created_at_values else None
    oldest = min(created_at_values).isoformat() if created_at_values else None

    return {
        "version": "phase2a-v1",
        "window_days": days,
        "sample_size": total,
        "unique_users": len(user_ids),
        "actions": dict(action_counter),
        "surfaces": dict(surface_counter),
        "data_quality": {
            "missing_algorithm_version_rate": round(missing_algorithm_version / total, 4) if total else None,
            "missing_session_id_rate": round(missing_session_id / total, 4) if total else None,
            "null_position_rate": round(null_position / total, 4) if total else None,
            "latency_samples": len(latency_values),
            "latency_p50_ms": _percentile(latency_values, 50),
            "latency_p95_ms": _percentile(latency_values, 95),
        },
        "freshness": {
            "oldest_event_at": oldest,
            "newest_event_at": newest,
        },
    }
