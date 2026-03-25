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
import json
import math
from pathlib import Path
from typing import List, Tuple

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


FRONTEND_FURNISHED_PREFERENCES = ["required", "preferred", "no_preference"]
FRONTEND_GENDER_POLICIES = ["same_gender_only", "mixed_ok"]
FRONTEND_LEASE_TYPES = ["fixed", "month_to_month", "sublet", "any"]


def _type_feature_col(prefix: str, value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = normalized.replace("/", "_").replace(" ", "_")
    return f"{prefix}_{normalized}"


TYPE_PREF_COLS = [_type_feature_col("type_pref", t) for t in LISTING_TYPES]


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

    # Frontend preference-contract fields
    gender_policy = rng.choice(
        FRONTEND_GENDER_POLICIES, size=n, p=[0.30, 0.70]
    )
    target_lease_type = rng.choice(
        FRONTEND_LEASE_TYPES, size=n, p=[0.30, 0.30, 0.10, 0.30]
    )
    target_lease_duration_months = rng.choice(
        [1, 3, 6, 9, 12, 18], size=n, p=[0.18, 0.10, 0.20, 0.12, 0.30, 0.10]
    )
    target_lease_duration_months = np.where(
        target_lease_type == "month_to_month",
        1,
        target_lease_duration_months,
    )
    target_deposit_amount = np.clip(budget_max * rng.uniform(0.40, 1.25, n), 0, 8_000)

    furnished_preference = np.where(
        wants_furnished,
        np.where(rng.random(n) < 0.50, "required", "preferred"),
        np.where(rng.random(n) < 0.15, "preferred", "no_preference"),
    )

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
        "target_deposit_amount": target_deposit_amount.round(0),
        "target_lease_duration_months": target_lease_duration_months.astype(int),
        "gender_policy": gender_policy,
        "target_lease_type": target_lease_type,
        "furnished_preference": furnished_preference,
    })

    for j, col in enumerate(TYPE_PREF_COLS):
        renters[col] = type_prefs[:, j].astype(int)

    for value in FRONTEND_GENDER_POLICIES:
        renters[f"gender_policy_{value}"] = (renters["gender_policy"] == value).astype(int)
    for value in FRONTEND_LEASE_TYPES:
        renters[f"target_lease_type_{value}"] = (renters["target_lease_type"] == value).astype(int)
    for value in FRONTEND_FURNISHED_PREFERENCES:
        renters[f"furnished_pref_{value}"] = (renters["furnished_preference"] == value).astype(int)

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
    furnished_pref = str(renter.get("furnished_preference") or "").strip().lower()
    if furnished_pref == "required":
        score += w if listing["comes_furnished"] == 1 else 0
    elif furnished_pref == "preferred":
        score += w if listing["comes_furnished"] == 1 else 0.3 * w
    elif renter["wants_furnished"] == 0:
        score += w
    else:
        score += 0.3 * w

    # deposit affordability (deposit approximated as one month of rent)
    w = 0.8
    total_weight += w
    target_deposit = float(renter.get("target_deposit_amount", 0) or 0)
    if target_deposit <= 0:
        score += 0.7 * w
    else:
        est_deposit = float(listing["price"])
        if est_deposit <= target_deposit:
            score += w
        else:
            score += w * max(0, 1 - (est_deposit - target_deposit) / 1_000)

    # type preference
    w = 1.5
    total_weight += w
    ltype = listing["type"]
    type_col = _type_feature_col("type_pref", ltype)
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

# Listing types used for one-hot encoding liked listings aggregation
# Must stay consistent with the values in liked_listings_detail.csv
LIKED_LISTING_TYPES = [
    "apartment", "house", "condo", "townhouse", "duplex",
    "loft", "cottage/cabin", "manufactured", "flat",
    "in-law", "assisted living", "land",
]


LIKED_TYPE_COLS = [_type_feature_col("liked_type", t) for t in LIKED_LISTING_TYPES]
LIKED_NUMERIC_COLS = ["liked_mean_price", "liked_mean_beds", "liked_mean_sqfeet"]


def _assert_unique_columns(columns: List[str], label: str) -> None:
    seen = set()
    duplicates = []
    for col in columns:
        if col in seen and col not in duplicates:
            duplicates.append(col)
        seen.add(col)
    if duplicates:
        raise ValueError(f"{label} has duplicated columns: {duplicates}")


def _build_user_feature_schema(renters: pd.DataFrame) -> List[str]:
    base_cols = [
        "age", "household_size", "income", "credit_score",
        "budget_min", "budget_max",
        "desired_beds", "desired_baths", "desired_sqft_min",
        "target_deposit_amount", "target_lease_duration_months",
        "has_cats", "has_dogs", "is_smoker",
        "needs_wheelchair", "has_ev", "wants_furnished",
        "pref_lat", "pref_lon", "max_distance_km",
        "laundry_pref", "parking_pref", "move_urgency",
    ]
    categorical_cols = (
        TYPE_PREF_COLS
        + [f"gender_policy_{v}" for v in FRONTEND_GENDER_POLICIES]
        + [f"target_lease_type_{v}" for v in FRONTEND_LEASE_TYPES]
        + [f"furnished_pref_{v}" for v in FRONTEND_FURNISHED_PREFERENCES]
    )
    schema = base_cols + categorical_cols
    has_liked = all(c in renters.columns for c in LIKED_NUMERIC_COLS)
    if has_liked:
        schema += LIKED_NUMERIC_COLS + LIKED_TYPE_COLS
    _assert_unique_columns(schema, "user feature schema")
    return schema


def aggregate_liked_listings(liked_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each renter, collapse their liked listings into a single fixed-size
    vector by averaging raw listing features.

    Input columns used: listing_price, listing_beds, listing_sqfeet, listing_type
    Category columns (category_id, category_name) are intentionally ignored.

    Returns a DataFrame indexed by renter_id with columns:
        liked_mean_price, liked_mean_beds, liked_mean_sqfeet,
        liked_type_<type> x len(LIKED_LISTING_TYPES)
    """
    normalized_listing_types = (
        liked_df["listing_type"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )
    normalized_listing_types = normalized_listing_types.where(
        normalized_listing_types.isin(LIKED_LISTING_TYPES),
        "",
    )
    liked_type_feature = normalized_listing_types.map(
        lambda t: _type_feature_col("liked_type", t) if t else ""
    )
    type_dummies = pd.get_dummies(liked_type_feature)
    if "" in type_dummies.columns:
        type_dummies = type_dummies.drop(columns=[""])
    for col in LIKED_TYPE_COLS:
        if col not in type_dummies.columns:
            type_dummies[col] = 0.0
    type_dummies = type_dummies[LIKED_TYPE_COLS]
    _assert_unique_columns(type_dummies.columns.tolist(), "liked_type feature block")

    liked_df = liked_df[["renter_id", "listing_price", "listing_beds", "listing_sqfeet"]].copy()
    liked_df = pd.concat([liked_df, type_dummies], axis=1)

    agg = liked_df.groupby("renter_id").mean().reset_index()
    agg = agg.rename(columns={
        "listing_price": "liked_mean_price",
        "listing_beds":  "liked_mean_beds",
        "listing_sqfeet": "liked_mean_sqfeet",
    })
    return agg


def encode_renter_features(renters: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    """Numeric matrix ready for the user tower.

    Uses raw renter profile features. If the DataFrame contains liked-listing
    aggregate columns (liked_mean_price, liked_mean_beds, etc.) they are
    appended as additional features — no category-derived columns anywhere.
    """
    cols = _build_user_feature_schema(renters)
    frame = renters.copy()
    for col in cols:
        if col not in frame.columns:
            frame[col] = 0.0
    mat = frame[cols].fillna(0).values.astype(np.float32)

    zscore_cols = [
        "age", "household_size", "income", "credit_score",
        "budget_min", "budget_max",
        "desired_beds", "desired_baths", "desired_sqft_min",
        "target_deposit_amount", "target_lease_duration_months",
        "liked_mean_price", "liked_mean_beds", "liked_mean_sqfeet",
    ]
    col_to_idx = {col: idx for idx, col in enumerate(cols)}
    for col in zscore_cols:
        idx = col_to_idx.get(col)
        if idx is None:
            continue
        mu, sigma = mat[:, idx].mean(), mat[:, idx].std() + 1e-8
        mat[:, idx] = (mat[:, idx] - mu) / sigma

    return mat, cols


def encode_listing_features(listings: pd.DataFrame) -> np.ndarray:
    """Numeric matrix ready for the item tower.

    Uses only raw listing features — no category-derived columns.
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

    return np.hstack([
        numeric,
        type_dummies.values.astype(np.float32),
        laundry_dummies.values.astype(np.float32),
        parking_dummies.values.astype(np.float32),
    ])


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
    p.add_argument("--liked-listings-csv", type=Path, default=None,
                   help="liked_listings_detail.csv from categorize_and_map.py "
                        "(adds averaged liked listing features to user tower)")
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

    print(f"Building pairs ({args.pairs_per_renter} per renter) ...")
    renter_rows, listing_rows, labels = _build_pairs(
        renters, listings, args.pairs_per_renter, rng, args.pos_threshold,
    )
    print(f"  total pairs: {len(labels):,}  "
          f"(pos={labels.sum():,.0f}  neg={len(labels) - labels.sum():,.0f}  "
          f"ratio={labels.mean():.2%})")

    # ── load and join liked listings aggregate onto renter pair rows ──
    if args.liked_listings_csv and args.liked_listings_csv.exists():
        print(f"Loading liked listings from {args.liked_listings_csv} ...")
        liked_df = pd.read_csv(args.liked_listings_csv)
        print(f"  {len(liked_df):,} liked listing rows loaded")
        liked_agg = aggregate_liked_listings(liked_df)
        renter_rows = renter_rows.merge(liked_agg, on="renter_id", how="left")
        print(f"  joined averaged liked listing features -> renter pair rows "
              f"(+{len(liked_agg.columns) - 1} columns)")

    print("Encoding features ...")
    user_features, user_feature_cols = encode_renter_features(renter_rows)
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

    _assert_unique_columns(user_feature_cols, "saved user feature schema")
    item_type_cols = sorted(
        pd.get_dummies(listing_rows["type"].fillna(""), prefix="type").columns.tolist()
    )
    item_laundry_cols = sorted(
        pd.get_dummies(listing_rows["laundry_options"].fillna(""), prefix="laundry").columns.tolist()
    )
    item_parking_cols = sorted(
        pd.get_dummies(listing_rows["parking_options"].fillna(""), prefix="parking").columns.tolist()
    )
    _assert_unique_columns(item_type_cols, "item type schema")
    _assert_unique_columns(item_laundry_cols, "item laundry schema")
    _assert_unique_columns(item_parking_cols, "item parking schema")

    # ── save feature column names for inference alignment ─────────────
    feature_meta = {
        "user_dim": int(user_features.shape[1]),
        "item_dim": int(item_features.shape[1]),
        "schema_version": 2,
        "strict_user_feature_schema": True,
        "user_feature_cols": user_feature_cols,
        "item_type_cols": item_type_cols,
        "item_laundry_cols": item_laundry_cols,
        "item_parking_cols": item_parking_cols,
        "liked_type_cols": LIKED_TYPE_COLS,
        "has_liked_listings": all(c in renter_rows.columns for c in LIKED_NUMERIC_COLS),
    }
    meta_path = args.out_npz.parent / "feature_meta.json"
    with open(meta_path, "w") as f:
        json.dump(feature_meta, f, indent=2)
    print(f"  saved feature metadata -> {meta_path}")
    print("Done.")


if __name__ == "__main__":
    main()
