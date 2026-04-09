"""
Padly ML Inference Service

Standalone FastAPI app that loads the Two-Tower model and exposes
scoring / embedding endpoints over HTTP.  The main API server calls
these endpoints via ``app.services.ml_client`` so that TensorFlow
never needs to be installed in the API image.

Endpoints
---------
POST /score-listings       — rank listings for a user (hard-filter + blend)
POST /embed/item-tower-batch — batch item-tower forward pass
GET  /status               — model / tower availability
GET  /health               — liveness probe
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="Padly ML Service",
    version="1.0.0",
    description="Two-Tower inference service for Padly recommendations",
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ScoreListingsRequest(BaseModel):
    user: Dict[str, Any]
    listings: List[Dict[str, Any]]
    top_n: int = Field(default=50, ge=1)


class ScoreListingsResponse(BaseModel):
    scored: List[Dict[str, Any]]


class ItemTowerBatchRequest(BaseModel):
    listings: List[Dict[str, Any]]


class ItemTowerBatchResponse(BaseModel):
    embeddings: Optional[List[List[float]]] = None


class StatusResponse(BaseModel):
    model_loaded: bool
    embedding_available: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/score-listings", response_model=ScoreListingsResponse)
def score_listings_endpoint(req: ScoreListingsRequest):
    from app.ai.recommender import score_listings

    scored = score_listings(req.user, req.listings, top_n=req.top_n)
    return ScoreListingsResponse(scored=scored)


@app.post("/embed/item-tower-batch", response_model=ItemTowerBatchResponse)
def item_tower_batch_endpoint(req: ItemTowerBatchRequest):
    from app.ai.recommender import item_tower_latent_batch

    if not req.listings:
        return ItemTowerBatchResponse(embeddings=None)

    result = item_tower_latent_batch(req.listings)
    if result is None:
        return ItemTowerBatchResponse(embeddings=None)

    return ItemTowerBatchResponse(embeddings=result.tolist())


@app.get("/status", response_model=StatusResponse)
def status_endpoint():
    from app.ai.recommender import embedding_inference_available, _model, _meta

    model_loaded = _model is not None and _meta is not None
    emb_avail = embedding_inference_available()
    return StatusResponse(model_loaded=model_loaded, embedding_available=emb_avail)


@app.get("/health")
def health_endpoint():
    return {"status": "healthy", "service": "Padly ML Service"}
