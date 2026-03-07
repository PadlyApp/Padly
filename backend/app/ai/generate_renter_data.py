"""
Generate synthetic renter profiles and (renter, listing) training pairs
for the Padly two-tower model.

Renter preferences are sampled from distributions derived from the *real*
listing data so the signal is realistic.  Match labels are computed
deterministically from preference-listing alignment, not random coin-flips.

Usage:
    python -m app.ai.generate_renter_data                        # defaults
    python -m app.ai.generate_renter_data --renters 50000 --pairs-per-renter 20
    python -m app.ai.generate_renter_data --out-npz data/train_data.npz
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# ── catalogue of every categorical value in the listing data ──────────────

LISTING_TYPES = [
    "apartment", "house", "condo", "townhouse", "duplex",
    "loft", "cottage/cabin", "manufactured", "flat",
    "in-law", "assisted living", "land",
]

LAUNDRY_OPTIONS = [
    "w/d in unit", "w/d hookups", "laundry in bldg",
    "laundry on site", "no laundry on site", "",
]

PARKING_OPTIONS = [
    "attached garage", "detached garage", "carport",
    "off-street parking", "street parking", "valet parking",
    "no parking", "",
]

STATES = [
    "al", "ak", "ar", "az", "ca", "co", "ct", "dc", "de", "fl",
    "ga", "hi", "ia", "id", "il", "in", "ks", "ky", "la", "ma",
    "md", "me", "mi", "mn", "mo", "ms", "mt", "nc", "nd", "ne",
    "nh", "nj", "nm", "nv", "ny", "oh", "ok", "or", "pa",
]


# ── helpers ───────────────────────────────────────────────────────────────

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── renter profile generation ────────────────────────────────────────────

def _generate_renters(
    n: int,
    listings: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Create *n* renter profiles whose preferences are anchored to real
    listing distributions so the downstream model gets meaningful signal.
    """

    valid_prices = listings["price"][
        (listings["price"] > 100) & (listings["price"] < 10_000)
    ]
    price_mean = float(valid_prices.mean())
    price_std = float(valid_prices.std())

    valid_sqft = listings["sqfeet"][
        (listings["sqfeet"] > 100) & (listings["sqfeet"] < 10_000)
    ]
    sqft_mean = float(valid_sqft.mean())
    sqft_std = float(valid_sqft.std())

    valid_lats = listings["lat"].dropna()
    valid_lons = listings["long"].dropna()

    # ── correlated demographics ───────────────────────────────────────
    age = rng.integers(18, 70, size=n)
    household_size = rng.choice([1, 2, 3, 4, 5], size=n,
                                p=[0.30, 0.30, 0.20, 0.12, 0.08])

    # income loosely correlates with age (peaks ~45) + household size
    base_income = 25_000 + 800 * np.minimum(age, 50) + rng.normal(0, 12_000, n)
    income = (base_income * (1 + 0.12 * (household_size - 1))).clip(15_000, 250_000)

    # budget is ~30 % of monthly income, with noise
    monthly_income = income / 12
    budget_center = monthly_income * rng.uniform(0.25, 0.40, n)
    budget_min = (budget_center * 0.70).clip(200)
    budget_max = (budget_center * 1.30).clip(400)

    # beds / baths driven by household size
    desired_beds = np.clip(
        household_size + rng.integers(-1, 1, n, endpoint=True), 0, 8
    ).astype(float)
    desired_baths = np.clip(
        np.ceil(desired_beds / 2) + rng.choice([0, 0.5, 0], n), 1, 6
    )

    desired_sqft_min = np.clip(
        sqft_mean + sqft_std * rng.normal(0, 0.5, n)
        + 150 * (desired_beds - 2),
        200, 5_000,
    )

    # pet ownership & lifestyle booleans
    has_cats = rng.random(n) < 0.25
    has_dogs = rng.random(n) < 0.30
    is_smoker = rng.random(n) < 0.12
    needs_wheelchair = rng.random(n) < 0.04
    has_ev = (rng.random(n) < 0.06) & (income > 60_000)
    wants_furnished = rng.random(n) < 0.18

    # location preference: sample from real listing coordinates + jitter
    loc_idx = rng.choice(len(valid_lats), size=n)
    pref_lat = valid_lats.values[loc_idx] + rng.normal(0, 0.15, n)
    pref_lon = valid_lons.values[loc_idx] + rng.normal(0, 0.15, n)
    max_distance_km = rng.uniform(5, 80, n)

    # type preference: pick 1-3 types per renter
    type_prefs = np.zeros((n, len(LISTING_TYPES)), dtype=np.float32)
    for i in range(n):
        k = rng.integers(1, 4)
        chosen = rng.choice(len(LISTING_TYPES), size=k, replace=False)
        type_prefs[i, chosen] = 1.0

    # laundry & parking encoded as preference index
    laundry_pref = rng.integers(0, len(LAUNDRY_OPTIONS), n)
    parking_pref = rng.integers(0, len(PARKING_OPTIONS), n)

    # credit score bracket (correlates loosely with income)
    credit_score = np.clip(
        550 + (income - 40_000) / 800 + rng.normal(0, 40, n),
        300, 850,
    )

    # move-in urgency: 0 = flexible, 1 = soon, 2 = urgent
    move_urgency = rng.choice([0, 1, 2], n, p=[0.35, 0.45, 0.20])

    renters = pd.DataFrame({
        "renter_id": np.arange(n),
        "age": age,
        "household_size": household_size,
        "income": income.round(0),
        "credit_score": credit_score.round(0),
        "budget_min": budget_min.round(0),
        "budget_max": budget_max.round(0),
        "desired_beds": desired_beds,
        "desired_baths": desired_baths,
        "desired_sqft_min": desired_sqft_min.round(0),
        "has_cats": has_cats.astype(int),
        "has_dogs": has_dogs.astype(int),
        "is_smoker": is_smoker.astype(int),
        "needs_wheelchair": needs_wheelchair.astype(int),
        "has_ev": has_ev.astype(int),
        "wants_furnished": wants_furnished.astype(int),
        "pref_lat": pref_lat.round(4),
        "pref_lon": pref_lon.round(4),
        "max_distance_km": max_distance_km.round(1),
        "laundry_pref": laundry_pref,
        "parking_pref": parking_pref,
        "move_urgency": move_urgency,
    })

    for j, t in enumerate(LISTING_TYPES):
        renters[f"type_pref_{t.replace('/', '_').replace(' ', '_')}"] = type_prefs[:, j].astype(int)

    return renters


# ── pairing & label computation ──────────────────────────────────────────

def _match_score(renter: pd.Series, listing: pd.Series) -> float:
    """
    Deterministic compatibility score in [0, 1].
    Higher = better match.  Computed from hard constraints + soft preferences.
    """
    score = 0.0
    total_weight = 0.0

    # ── hard constraints (if violated, heavy penalty) ─────────────────

    price = listing["price"]
    # budget fit
    w = 3.0
    total_weight += w
    if renter["budget_min"] <= price <= renter["budget_max"]:
        score += w
    elif price < renter["budget_min"]:
        score += w * max(0, 1 - (renter["budget_min"] - price) / 300)
    else:
        score += w * max(0, 1 - (price - renter["budget_max"]) / 500)

    # pet constraints – deal-breaker if listing forbids
    for pet, col in [("has_cats", "cats_allowed"), ("has_dogs", "dogs_allowed")]:
        w = 2.0
        total_weight += w
        if renter[pet] == 1 and listing[col] == 0:
            score += 0
        else:
            score += w

    # smoking
    w = 1.5
    total_weight += w
    if renter["is_smoker"] == 1 and listing["smoking_allowed"] == 0:
        score += 0
    else:
        score += w

    # wheelchair
    w = 2.5
    total_weight += w
    if renter["needs_wheelchair"] == 1 and listing["wheelchair_access"] == 0:
        score += 0
    else:
        score += w

    # EV charger
    w = 1.0
    total_weight += w
    if renter["has_ev"] == 1 and listing["electric_vehicle_charge"] == 0:
        score += 0.2 * w
    else:
        score += w

    # ── soft preferences ──────────────────────────────────────────────

    # beds
    w = 2.0
    total_weight += w
    diff = abs(listing["beds"] - renter["desired_beds"])
    score += w * max(0, 1 - diff / 3)

    # baths
    w = 1.0
    total_weight += w
    diff = abs(listing["baths"] - renter["desired_baths"])
    score += w * max(0, 1 - diff / 2)

    # sqft
    w = 1.5
    total_weight += w
    if listing["sqfeet"] >= renter["desired_sqft_min"]:
        score += w
    else:
        deficit = renter["desired_sqft_min"] - listing["sqfeet"]
        score += w * max(0, 1 - deficit / 500)

    # furnished
    w = 0.8
    total_weight += w
    if renter["wants_furnished"] == 1 and listing["comes_furnished"] == 1:
        score += w
    elif renter["wants_furnished"] == 0:
        score += w
    else:
        score += 0.3 * w

    # type preference
    w = 1.5
    total_weight += w
    ltype = listing["type"]
    type_col = f"type_pref_{ltype.replace('/', '_').replace(' ', '_')}"
    if type_col in renter.index and renter[type_col] == 1:
        score += w
    else:
        score += 0.3 * w

    # location proximity
    w = 2.5
    total_weight += w
    try:
        dist = _haversine_km(
            renter["pref_lat"], renter["pref_lon"],
            listing["lat"], listing["long"],
        )
        if dist <= renter["max_distance_km"]:
            score += w * (1 - 0.3 * dist / renter["max_distance_km"])
        else:
            overshoot = dist - renter["max_distance_km"]
            score += w * max(0, 0.5 - overshoot / 200)
    except (ValueError, TypeError):
        score += 0.4 * w

    return score / total_weight


def _build_pairs(
    renters: pd.DataFrame,
    listings: pd.DataFrame,
    pairs_per_renter: int,
    rng: np.random.Generator,
    pos_threshold: float = 0.65,
) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """
    For each renter, sample listings and compute match labels.
    Returns aligned (renter_rows, listing_rows, labels) arrays.
    """
    all_renter_rows: List[pd.Series] = []
    all_listing_rows: List[pd.Series] = []
    all_labels: List[float] = []

    listing_idx = np.arange(len(listings))

    for _, renter in renters.iterrows():
        sampled = rng.choice(listing_idx, size=pairs_per_renter, replace=False)
        for li in sampled:
            listing = listings.iloc[li]
            s = _match_score(renter, listing)
            all_renter_rows.append(renter)
            all_listing_rows.append(listing)
            all_labels.append(1.0 if s >= pos_threshold else 0.0)

    return (
        pd.DataFrame(all_renter_rows).reset_index(drop=True),
        pd.DataFrame(all_listing_rows).reset_index(drop=True),
        np.array(all_labels, dtype=np.float32),
    )


# ── feature encoding for the neural-net towers ──────────────────────────

# Column names for the 6 feedback features from categorize_and_map.py
FEEDBACK_COLS = [
    "cat_0_Budget_Compact",
    "cat_1_Spacious_Family",
    "cat_2_Pet-Friendly",
    "cat_3_Premium_Luxury",
    "cat_4_Urban_Convenience",
    "cat_5_Accessible_Modern",
]

NUM_LISTING_CATEGORIES = 6  # must match categorize_and_map.NUM_CATEGORIES


def encode_renter_features(renters: pd.DataFrame) -> np.ndarray:
    """Numeric matrix ready for the user tower.

    If the DataFrame contains feedback columns (cat_0_* … cat_5_*) they are
    appended as normalised features.  Otherwise encoding is unchanged.
    """
    numeric_cols = [
        "age", "household_size", "income", "credit_score",
        "budget_min", "budget_max",
        "desired_beds", "desired_baths", "desired_sqft_min",
        "has_cats", "has_dogs", "is_smoker",
        "needs_wheelchair", "has_ev", "wants_furnished",
        "pref_lat", "pref_lon", "max_distance_km",
        "laundry_pref", "parking_pref", "move_urgency",
    ]
    type_cols = [c for c in renters.columns if c.startswith("type_pref_")]
    cols = numeric_cols + sorted(type_cols)
    mat = renters[cols].values.astype(np.float32)

    # z-score continuous features (first 9 columns)
    for i in range(9):
        mu, sigma = mat[:, i].mean(), mat[:, i].std() + 1e-8
        mat[:, i] = (mat[:, i] - mu) / sigma

    # ── append feedback array (normalised to [0,1]) if present ────────
    has_feedback = all(c in renters.columns for c in FEEDBACK_COLS)
    if has_feedback:
        fb = renters[FEEDBACK_COLS].values.astype(np.float32)
        row_sums = fb.sum(axis=1, keepdims=True)
        row_sums = np.where(row_sums == 0, 1.0, row_sums)  # avoid /0
        fb_norm = fb / row_sums  # each row sums to 1
        mat = np.hstack([mat, fb_norm])

    return mat


def encode_listing_features(listings: pd.DataFrame) -> np.ndarray:
    """Numeric matrix ready for the item tower.

    If the DataFrame contains a ``category_id`` column (from
    categorize_and_map), it is one-hot encoded and appended.
    """
    type_dummies = pd.get_dummies(listings["type"].fillna(""), prefix="type")
    laundry_dummies = pd.get_dummies(
        listings["laundry_options"].fillna(""), prefix="laundry"
    )
    parking_dummies = pd.get_dummies(
        listings["parking_options"].fillna(""), prefix="parking"
    )

    numeric = listings[
        ["price", "sqfeet", "beds", "baths",
         "cats_allowed", "dogs_allowed", "smoking_allowed",
         "wheelchair_access", "electric_vehicle_charge", "comes_furnished",
         "lat", "long"]
    ].fillna(0).values.astype(np.float32)

    # z-score first 4 continuous features
    for i in range(4):
        mu, sigma = numeric[:, i].mean(), numeric[:, i].std() + 1e-8
        numeric[:, i] = (numeric[:, i] - mu) / sigma

    parts = [
        numeric,
        type_dummies.values.astype(np.float32),
        laundry_dummies.values.astype(np.float32),
        parking_dummies.values.astype(np.float32),
    ]

    # ── append listing category one-hot if present ────────────────────
    if "category_id" in listings.columns:
        cat_ids = listings["category_id"].fillna(0).astype(int).values
        one_hot = np.zeros((len(listings), NUM_LISTING_CATEGORIES), dtype=np.float32)
        one_hot[np.arange(len(listings)), cat_ids] = 1.0
        parts.append(one_hot)

    return np.hstack(parts)


# ── main ─────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate renter data for Padly two-tower")
    p.add_argument("--listings-csv", type=Path,
                   default=Path("app/ai/dataset/housing_train.csv"))
    p.add_argument("--renters", type=int, default=30_000,
                   help="Number of synthetic renter profiles to create")
    p.add_argument("--pairs-per-renter", type=int, default=10,
                   help="Listings sampled per renter for pair generation")
    p.add_argument("--pos-threshold", type=float, default=0.65,
                   help="Match-score threshold for a positive label")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-renters-csv", type=Path,
                   default=Path("app/ai/dataset/renters_synthetic.csv"))
    p.add_argument("--out-npz", type=Path,
                   default=Path("app/ai/dataset/train_pairs.npz"))
    # ── optional feedback / category files from categorize_and_map ────
    p.add_argument("--feedback-csv", type=Path, default=None,
                   help="user_feedback.csv from categorize_and_map.py "
                        "(adds 6 feedback features to user tower)")
    p.add_argument("--listing-cats-csv", type=Path, default=None,
                   help="listing_categories.csv from categorize_and_map.py "
                        "(adds category one-hot to item tower)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    print(f"Loading listings from {args.listings_csv} ...")
    listings = pd.read_csv(args.listings_csv)
    orig_len = len(listings)

    # basic cleaning – drop extreme outliers that would poison distributions
    listings = listings[
        (listings["price"] > 50) & (listings["price"] < 15_000)
        & (listings["sqfeet"] > 50) & (listings["sqfeet"] < 15_000)
        & (listings["beds"] >= 0) & (listings["beds"] <= 10)
        & listings["lat"].notna() & listings["long"].notna()
    ].reset_index(drop=True)
    print(f"  kept {len(listings):,} / {orig_len:,} listings after cleaning")

    print(f"Generating {args.renters:,} renter profiles ...")
    renters = _generate_renters(args.renters, listings, rng)

    renters.to_csv(args.out_renters_csv, index=False)
    print(f"  saved renter profiles -> {args.out_renters_csv}")

    # ── load optional feedback & listing-category data ────────────────
    feedback_df: pd.DataFrame | None = None
    if args.feedback_csv and args.feedback_csv.exists():
        feedback_df = pd.read_csv(args.feedback_csv)
        print(f"  loaded feedback array -> {args.feedback_csv}  "
              f"({len(feedback_df):,} rows)")

    listing_cats_df: pd.DataFrame | None = None
    if args.listing_cats_csv and args.listing_cats_csv.exists():
        listing_cats_df = pd.read_csv(args.listing_cats_csv)
        print(f"  loaded listing categories -> {args.listing_cats_csv}  "
              f"({len(listing_cats_df):,} rows)")

    print(f"Building pairs ({args.pairs_per_renter} per renter) ...")
    renter_rows, listing_rows, labels = _build_pairs(
        renters, listings, args.pairs_per_renter, rng, args.pos_threshold,
    )
    print(f"  total pairs: {len(labels):,}  "
          f"(pos={labels.sum():,.0f}  neg={len(labels) - labels.sum():,.0f}  "
          f"ratio={labels.mean():.2%})")

    # ── join feedback array onto renter pair rows ─────────────────────
    if feedback_df is not None:
        renter_rows = renter_rows.merge(
            feedback_df[["renter_id"] + FEEDBACK_COLS],
            on="renter_id", how="left",
        )
        # fill any renters without feedback with zeros
        renter_rows[FEEDBACK_COLS] = renter_rows[FEEDBACK_COLS].fillna(0)
        print(f"  joined feedback array -> renter pair rows "
              f"(+{len(FEEDBACK_COLS)} columns)")

    # ── join listing category onto listing pair rows ──────────────────
    if listing_cats_df is not None:
        listing_rows = listing_rows.merge(
            listing_cats_df[["id", "category_id"]],
            on="id", how="left",
        )
        listing_rows["category_id"] = listing_rows["category_id"].fillna(0).astype(int)
        print(f"  joined listing categories -> listing pair rows "
              f"(+1 column)")

    print("Encoding features ...")
    user_features = encode_renter_features(renter_rows)
    item_features = encode_listing_features(listing_rows)

    print(f"  user_features shape: {user_features.shape}")
    print(f"  item_features shape: {item_features.shape}")

    np.savez_compressed(
        args.out_npz,
        user_features=user_features,
        item_features=item_features,
        labels=labels,
    )
    print(f"  saved training pairs -> {args.out_npz}")
    print("Done.")


if __name__ == "__main__":
    main()
