"""
Evaluation endpoints — list available models and run the eval pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])

_ARTIFACTS_DIR = Path(__file__).parent.parent / "ai" / "artifacts"
_NPZ_PATH      = Path(__file__).parent.parent / "ai" / "dataset" / "train_pairs.npz"


# ── schemas ───────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    model: str  # filename only, e.g. "two_tower_bce.keras"


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/models")
def list_models() -> List[str]:
    """Return the filenames of all .keras model files in the artifacts directory."""
    if not _ARTIFACTS_DIR.exists():
        return []
    return sorted(p.name for p in _ARTIFACTS_DIR.glob("*.keras"))


@router.post("/run")
def run_evaluation(body: RunRequest):
    """
    Run the full eval pipeline for the requested model and return results as JSON.

    Inference on 60k pairs takes ~8-10s — runs synchronously (internal tool).
    """
    model_path = _ARTIFACTS_DIR / body.model

    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"Model '{body.model}' not found in artifacts directory.")

    if not _NPZ_PATH.exists():
        raise HTTPException(status_code=500, detail="Dataset file train_pairs.npz not found.")

    try:
        from app.ai.eval_model import run_eval
        results = run_eval(model_path=model_path, npz_path=_NPZ_PATH)
        return results
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/category-eval")
def run_category_evaluation(body: RunRequest):
    """
    Build a 6×6 category cross-prediction matrix.

    For each (user_category, listing_category) combination in the test split,
    returns the mean model prediction score.  Requires that the NPZ was
    generated with category labels (run generate_renter_data.py first).
    """
    model_path = _ARTIFACTS_DIR / body.model

    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"Model '{body.model}' not found in artifacts directory.")

    if not _NPZ_PATH.exists():
        raise HTTPException(status_code=500, detail="Dataset file train_pairs.npz not found.")

    try:
        from app.ai.eval_model import run_category_eval
        results = run_category_eval(model_path=model_path, npz_path=_NPZ_PATH)
        return results
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
