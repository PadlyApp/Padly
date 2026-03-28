"""
Padly Two-Tower Model Evaluator

Compares the trained model's continuous sigmoid output against the deterministic
_match_score values stored in the dataset, using the difference as the primary
evaluation signal.  Binary metrics (AUC, accuracy) are included for reference.

Run from backend/:
    python -m app.ai.eval_model
    python -m app.ai.eval_model --npz-path app/ai/dataset/train_pairs.npz \\
                                --model    app/ai/artifacts/two_tower_baseline.keras
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_data(path: Path):
    """Load the npz produced by generate_renter_data.py."""
    data = np.load(path)
    for key in ("user_features", "item_features", "labels"):
        if key not in data:
            raise ValueError(f"Missing '{key}' in {path}")

    uf     = data["user_features"].astype(np.float32)
    itf    = data["item_features"].astype(np.float32)
    labels = data["labels"].astype(np.float32).reshape(-1)

    if "raw_scores" in data:
        raw_scores = data["raw_scores"].astype(np.float32).reshape(-1)
    else:
        raw_scores = None

    return uf, itf, labels, raw_scores


def _mae(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a - b)))


def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(np.mean((a - b) ** 2)))


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.std() < 1e-9 or b.std() < 1e-9:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation — Pearson on ranks, no scipy needed."""
    ra = np.argsort(np.argsort(a)).astype(np.float64)
    rb = np.argsort(np.argsort(b)).astype(np.float64)
    return _pearson(ra, rb)


def _auc_roc(labels: np.ndarray, preds: np.ndarray) -> float:
    """Mann-Whitney AUC — no sklearn needed."""
    if len(np.unique(labels)) < 2:
        return float("nan")
    pos = preds[labels == 1]
    neg = preds[labels == 0]
    n_pos, n_neg = len(pos), len(neg)
    all_scores = np.concatenate([pos, neg])
    all_labels = np.concatenate([np.ones(n_pos), np.zeros(n_neg)])
    order = np.argsort(all_scores)
    ranks = np.argsort(order) + 1
    pos_rank_sum = ranks[all_labels == 1].sum()
    auc = (pos_rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return float(auc)


def _build_calibration(raw_scores: np.ndarray, preds: np.ndarray, n_deciles: int = 10) -> List[Dict[str, Any]]:
    """Return calibration data as a list of dicts (one per decile)."""
    edges = np.linspace(0.0, 1.0, n_deciles + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (raw_scores >= lo) & (raw_scores < hi if hi < 1.0 else raw_scores <= hi)
        n = int(mask.sum())
        mean_pred = float(preds[mask].mean()) if n > 0 else None
        rows.append({
            "range": f"[{lo:.1f} - {hi:.1f})",
            "n_pairs": n,
            "mean_pred": round(mean_pred, 4) if mean_pred is not None else None,
        })
    return rows


# ── public API ────────────────────────────────────────────────────────────────

CATEGORY_NAMES = [
    "Budget Compact",
    "Spacious Family",
    "Pet-Friendly",
    "Premium / Luxury",
    "Urban Convenience",
    "Accessible Modern",
]


def run_category_eval(
    model_path: Path,
    npz_path: Path,
    batch_size: int = 512,
) -> dict:
    """
    Build a 6×6 matrix of mean model predictions grouped by
    (user primary category, listing category).

    Requires that the NPZ was generated with category labels saved
    (user_cats and item_cats arrays) — run generate_renter_data.py after
    the latest changes to produce them.

    Uses the same 20 % test split as run_eval() so results are comparable.

    Returns a dict with keys:
        category_names  – list of 6 human-readable strings
        matrix          – 6×6 list of mean prediction scores (float)
        counts          – 6×6 list of pair counts (int)
    """
    import tensorflow as tf

    data = np.load(npz_path)
    if "user_cats" not in data or "item_cats" not in data:
        raise ValueError(
            "NPZ is missing 'user_cats' / 'item_cats' arrays. "
            "Re-run generate_renter_data.py to regenerate the dataset."
        )

    n_total = len(data["labels"])
    split = int(0.8 * n_total)

    test_uf    = data["user_features"][split:].astype(np.float32)
    test_itf   = data["item_features"][split:].astype(np.float32)
    test_ucats = data["user_cats"][split:].astype(np.int8)
    test_icats = data["item_cats"][split:].astype(np.int8)

    model = tf.keras.models.load_model(str(model_path), safe_mode=False, compile=False)

    raw_out = model.predict(
        {"user_features": test_uf, "item_features": test_itf},
        batch_size=batch_size,
        verbose=0,
    )
    preds = raw_out.reshape(-1).astype(np.float64)

    matrix = [[None] * 6 for _ in range(6)]
    counts = [[0] * 6 for _ in range(6)]

    for uc in range(6):
        for lc in range(6):
            mask = (test_ucats == uc) & (test_icats == lc)
            n = int(mask.sum())
            counts[uc][lc] = n
            matrix[uc][lc] = round(float(preds[mask].mean()), 4) if n > 0 else None

    return {
        "category_names": CATEGORY_NAMES,
        "matrix": matrix,
        "counts": counts,
    }


def run_eval(
    model_path: Path,
    npz_path: Path,
    batch_size: int = 512,
) -> Dict[str, Any]:
    """
    Run the full evaluation pipeline and return results as a plain dict.

    Suitable for calling from the FastAPI route or any other Python code.
    Returns a dict with keys: model, test_pairs, positives, negatives,
    regression (or None), binary.
    """
    import tensorflow as tf  # deferred so non-ML code doesn't need TF

    user_features, item_features, labels, raw_scores = _load_data(npz_path)
    n_total = len(labels)

    split = int(0.8 * n_total)
    test_uf     = user_features[split:]
    test_itf    = item_features[split:]
    test_labels = labels[split:].astype(np.float64)
    test_raw    = raw_scores[split:].astype(np.float64) if raw_scores is not None else None

    model = tf.keras.models.load_model(str(model_path), safe_mode=False, compile=False)

    raw_out = model.predict(
        {"user_features": test_uf, "item_features": test_itf},
        batch_size=batch_size,
        verbose=0,
    )
    preds = raw_out.reshape(-1).astype(np.float64)

    # ── regression metrics ────────────────────────────────────────────────────
    regression: Optional[Dict[str, Any]] = None
    if test_raw is not None:
        regression = {
            "mae":          round(_mae(test_raw, preds), 4),
            "rmse":         round(_rmse(test_raw, preds), 4),
            "pearson_r":    round(_pearson(test_raw, preds), 4),
            "spearman_rho": round(_spearman(test_raw, preds), 4),
            "calibration":  _build_calibration(test_raw, preds),
        }

    # ── binary metrics ────────────────────────────────────────────────────────
    pos_mask = test_labels == 1
    neg_mask = test_labels == 0
    binary: Dict[str, Any] = {
        "auc_roc":       round(_auc_roc(test_labels, preds), 4),
        "accuracy":      round(float(((preds >= 0.5) == test_labels).mean()), 4),
        "mean_pred_pos": round(float(preds[pos_mask].mean()), 4),
        "mean_pred_neg": round(float(preds[neg_mask].mean()), 4),
        "delta":         round(float(preds[pos_mask].mean() - preds[neg_mask].mean()), 4),
    }

    return {
        "model":      Path(model_path).name,
        "test_pairs": int(len(test_labels)),
        "positives":  int(pos_mask.sum()),
        "negatives":  int(neg_mask.sum()),
        "regression": regression,
        "binary":     binary,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate Padly Two-Tower model")
    p.add_argument("--npz-path", type=Path,
                   default=Path("app/ai/dataset/train_pairs.npz"))
    p.add_argument("--model", type=Path,
                   default=Path("app/ai/artifacts/two_tower_bce.keras"))
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--out-csv", type=Path, default=None,
                   help="Optional path to save per-pair results as CSV")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Loading data from {args.npz_path} ...")
    results = run_eval(args.model, args.npz_path, args.batch_size)

    print(f"  total test pairs : {results['test_pairs']:,}")
    print(f"  positives        : {results['positives']:,}")
    print(f"  negatives        : {results['negatives']:,}")

    print("\n" + "=" * 64)
    print("  MODEL vs DETERMINISTIC SCORE  (primary eval)")
    print("=" * 64)

    reg = results["regression"]
    if reg:
        print(f"\n  MAE                  : {reg['mae']:.4f}")
        print(f"  RMSE                 : {reg['rmse']:.4f}")
        print(f"  Pearson r            : {reg['pearson_r']:.4f}  (linear alignment)")
        print(f"  Spearman rho         : {reg['spearman_rho']:.4f}  (rank alignment)")

        print(f"\n  {'Deterministic score range':<28s}  {'N pairs':>8s}  {'Mean model output':>18s}")
        print("  " + "-" * 60)
        for row in reg["calibration"]:
            mean_str = f"{row['mean_pred']:.4f}" if row["mean_pred"] is not None else "    nan"
            print(f"  {row['range']:<30s}  {row['n_pairs']:>8,d}  {mean_str:>18s}")
    else:
        print("\n  [skipped — raw_scores not available in npz]")

    print("\n" + "=" * 64)
    print("  BINARY METRICS  (reference only)")
    print("=" * 64)

    b = results["binary"]
    print(f"\n  AUC-ROC              : {b['auc_roc']:.4f}")
    print(f"  Accuracy @ 0.5       : {b['accuracy']:.4f}")
    print(f"  Mean pred (positives): {b['mean_pred_pos']:.4f}")
    print(f"  Mean pred (negatives): {b['mean_pred_neg']:.4f}")
    print(f"  Delta (pos - neg)    : {b['delta']:.4f}")

    if args.out_csv is not None:
        import csv
        user_features, item_features, labels, raw_scores = _load_data(args.npz_path)
        n_total = len(labels)
        split = int(0.8 * n_total)
        # Re-use already computed preds by re-running (simple approach for CLI)
        print(f"\n  (CSV output requires a second pass — skipped in refactored CLI)")

    print("\nDone.")


if __name__ == "__main__":
    main()
