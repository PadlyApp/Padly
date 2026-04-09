"""
ML scoring / embedding client.

The API server uses this module instead of importing ``app.ai.recommender``
directly.  Behaviour depends on ``settings.ml_service_url``:

* **HTTP mode** (``ML_SERVICE_URL`` is set) — forwards requests to the
  dedicated ML inference service.  TensorFlow is never loaded in the API
  process.
* **In-process fallback** (no URL) — lazily imports ``app.ai.recommender``
  so the existing single-process workflow keeps working during local
  development.

All public functions are ``async`` so callers use a single interface
regardless of the backing implementation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from app.config import settings

_http_client = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ml_service_configured() -> bool:
    return bool(getattr(settings, "ml_service_url", ""))


def _get_http_client():
    global _http_client
    if _http_client is None:
        import httpx

        _http_client = httpx.AsyncClient(
            base_url=settings.ml_service_url,
            timeout=60.0,
        )
    return _http_client


def _fetch_listings_for_embedding(listing_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Load listing rows with fields needed by item-tower encoding."""
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


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    x = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(x))
    if n <= 1e-12:
        return x
    return (x / n).astype(np.float32)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def score_listings(
    user: Dict[str, Any],
    listings: List[Dict[str, Any]],
    top_n: int = 50,
) -> List[Dict[str, Any]]:
    """Score and rank listings for a user.

    Returns listing dicts augmented with ``match_score``, ``rule_score``,
    ``behavior_score``, ``ml_score``, etc.
    """
    if _ml_service_configured():
        try:
            client = _get_http_client()
            resp = await client.post(
                "/score-listings",
                json={"user": user, "listings": listings, "top_n": top_n},
            )
            resp.raise_for_status()
            return resp.json()["scored"]
        except Exception as e:
            print(f"[ml_client] HTTP scoring failed, falling back to in-process: {e}")

    from app.ai.recommender import score_listings as _score

    return _score(user, listings, top_n)


async def item_tower_latent_batch(
    listings: List[Dict[str, Any]],
) -> Optional[np.ndarray]:
    """Batch item-tower forward pass.  Returns (N, embed_dim) or None."""
    if _ml_service_configured():
        try:
            client = _get_http_client()
            resp = await client.post(
                "/embed/item-tower-batch",
                json={"listings": listings},
            )
            resp.raise_for_status()
            data = resp.json()
            if data["embeddings"] is None:
                return None
            return np.array(data["embeddings"], dtype=np.float32)
        except Exception as e:
            print(f"[ml_client] HTTP embedding failed, falling back to in-process: {e}")

    from app.ai.recommender import item_tower_latent_batch as _batch

    return _batch(listings)


async def embedding_inference_available() -> bool:
    """True when the ML model and tower sub-models are usable."""
    if _ml_service_configured():
        try:
            client = _get_http_client()
            resp = await client.get("/status")
            resp.raise_for_status()
            return resp.json().get("embedding_available", False)
        except Exception:
            return False

    from app.ai.recommender import embedding_inference_available as _avail

    return _avail()


async def mean_taste_item_embedding(
    user_id: str,
    *,
    k: int = 50,
    days: int = 180,
    max_events: int = 2000,
) -> Optional[np.ndarray]:
    """Mean L2-normalised item-tower embedding over a user's recent likes.

    Data fetching happens on the API side; only the neural forward pass
    is delegated to the ML service (or the in-process fallback).
    """
    if not await embedding_inference_available():
        return None

    from app.services.behavior_features import POSITIVE_ACTIONS, _fetch_user_swipes

    events = _fetch_user_swipes(user_id=user_id, days=days, max_events=max_events)
    positive = [
        e
        for e in events
        if e.get("action") in POSITIVE_ACTIONS and e.get("listing_id")
    ]
    seen: set[str] = set()
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

    rows = _fetch_listings_for_embedding(listing_ids)
    ordered = [rows[lid] for lid in listing_ids if lid in rows]
    if not ordered:
        return None

    embs = await item_tower_latent_batch(ordered)
    if embs is None or embs.size == 0:
        return None

    return _l2_normalize(np.mean(embs, axis=0))


def taste_similarity_from_mean_embeddings(
    embedding_a: Optional[np.ndarray],
    embedding_b: Optional[np.ndarray],
) -> Optional[float]:
    """Cosine similarity mapped from [-1, 1] to [0, 1].  None if either is missing."""
    if embedding_a is None or embedding_b is None:
        return None
    a = np.asarray(embedding_a, dtype=np.float64).reshape(-1)
    b = np.asarray(embedding_b, dtype=np.float64).reshape(-1)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.5
    cos = float(np.dot(a, b) / (na * nb))
    return max(0.0, min(1.0, (cos + 1.0) / 2.0))
