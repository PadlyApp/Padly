"""
Categorize listings into 6 rule-based categories, then map each synthetic
renter to 15 "liked" listings that pass their hard constraints.  Produces a
per-user feedback array  [c0, c1, c2, c3, c4, c5]  where c_i = number of
liked listings in category i.

Categories (index → name):
    0  Budget Compact      – cheap, small, studio / 1-bed
    1  Spacious Family     – 3+ beds, large sqft
    2  Pet-Friendly        – allows cats AND dogs (general-purpose)
    3  Premium / Luxury    – high price + upscale amenities
    4  Urban Convenience   – remaining apartments / moderate listings
    5  Accessible Modern   – wheelchair access or EV charging

Usage (from backend/):
    python -m app.ai.categorize_and_map                        # defaults
    python -m app.ai.categorize_and_map --likes 15 --seed 42
    python -m app.ai.categorize_and_map --renters-csv path.csv --likes 20
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# ── category definitions ──────────────────────────────────────────────────

NUM_CATEGORIES = 6

CATEGORY_NAMES: Dict[int, str] = {
    0: "Budget Compact",
    1: "Spacious Family",
    2: "Pet-Friendly",
    3: "Premium / Luxury",
    4: "Urban Convenience",
    5: "Accessible Modern",
}

# Readable summary of what defines each category
CATEGORY_RULES_DESCRIPTION: Dict[int, str] = {
    0: "price < $900  AND  sqfeet < 800  AND  beds <= 1",
    1: "beds >= 3  AND  sqfeet > 1100",
    2: "cats AND dogs allowed  (catch-all after higher-priority categories)",
    3: "price > $1500  AND  (furnished OR w/d in unit OR garage parking)",
    4: "everything remaining (mostly moderate-price apartments)",
    5: "wheelchair accessible  OR  EV charging available",
}


# ── 1) listing categorization ────────────────────────────────────────────

def categorize_listings(listings: pd.DataFrame) -> pd.Series:
    """
    Assign exactly ONE category id (0-5) to every listing using a
    priority-based cascade of rule-based conditions.

    Priority order (highest first):
        5  Accessible Modern   – rarest signal, checked first
        3  Premium / Luxury
        1  Spacious Family
        0  Budget Compact
        2  Pet-Friendly
        4  Urban Convenience   – catch-all for anything left
    """
    cat = pd.Series(-1, index=listings.index, dtype=int)

    # helper: only assign where not yet assigned
    def _assign(mask: pd.Series, cat_id: int) -> None:
        cat.loc[mask & (cat == -1)] = cat_id

    # 5 – Accessible Modern
    _assign(
        (listings["wheelchair_access"] == 1)
        | (listings["electric_vehicle_charge"] == 1),
        5,
    )

    # 3 – Premium / Luxury
    _assign(
        (listings["price"] > 1500)
        & (
            (listings["comes_furnished"] == 1)
            | (listings["laundry_options"] == "w/d in unit")
            | (listings["parking_options"].isin(["attached garage", "detached garage"]))
        ),
        3,
    )

    # 1 – Spacious Family
    _assign(
        (listings["beds"] >= 3) & (listings["sqfeet"] > 1100),
        1,
    )

    # 0 – Budget Compact
    _assign(
        (listings["price"] < 900)
        & (listings["sqfeet"] < 800)
        & (listings["beds"] <= 1),
        0,
    )

    # 2 – Pet-Friendly  (remaining that allow both pets)
    _assign(
        (listings["cats_allowed"] == 1) & (listings["dogs_allowed"] == 1),
        2,
    )

    # 4 – Urban Convenience  (everything else)
    cat.loc[cat == -1] = 4

    return cat


# ── 2) hard-constraint filter ────────────────────────────────────────────

def passes_hard_constraints(renter: pd.Series, listing: pd.Series) -> bool:
    """
    Return True only if the listing satisfies ALL of the renter's
    non-negotiable constraints.  These are the same deal-breakers used
    in generate_renter_data._match_score but evaluated as booleans.
    """
    price = listing["price"]

    # budget – allow 20 % slack above max (they might stretch)
    budget_ceil = renter["budget_max"] * 1.20
    if price > budget_ceil:
        return False

    # pets
    if renter["has_cats"] == 1 and listing["cats_allowed"] == 0:
        return False
    if renter["has_dogs"] == 1 and listing["dogs_allowed"] == 0:
        return False

    # smoking
    if renter["is_smoker"] == 1 and listing["smoking_allowed"] == 0:
        return False

    # wheelchair
    if renter["needs_wheelchair"] == 1 and listing["wheelchair_access"] == 0:
        return False

    return True


def _vectorized_hard_filter(
    renter: pd.Series,
    listings: pd.DataFrame,
) -> np.ndarray:
    """
    Return a boolean mask (length = len(listings)) that is True where
    the listing passes all hard constraints for *renter*.
    Vectorized for speed.
    """
    budget_ceil = renter["budget_max"] * 1.20
    mask = listings["price"] <= budget_ceil

    if renter["has_cats"] == 1:
        mask = mask & (listings["cats_allowed"] == 1)
    if renter["has_dogs"] == 1:
        mask = mask & (listings["dogs_allowed"] == 1)
    if renter["is_smoker"] == 1:
        mask = mask & (listings["smoking_allowed"] == 1)
    if renter["needs_wheelchair"] == 1:
        mask = mask & (listings["wheelchair_access"] == 1)

    return mask.values


# ── 3) user → category affinity ──────────────────────────────────────────

def compute_user_category_affinity(renter: pd.Series) -> np.ndarray:
    """
    Return a float array of shape (NUM_CATEGORIES,) representing how
    strongly this renter is drawn to each category.  Values are NOT
    normalised to sum to 1 – the caller should convert to sampling
    weights.

    Mapping logic (renter preference → category affinity):
        Budget Compact (0)   ← low budget
        Spacious Family (1)  ← large household, many beds desired
        Pet-Friendly (2)     ← has cats or dogs
        Premium/Luxury (3)   ← high budget, wants furnished
        Urban Convenience (4)← prefers apartments, moderate budget
        Accessible Modern (5)← needs wheelchair or has EV
    """
    aff = np.ones(NUM_CATEGORIES, dtype=np.float64) * 0.05  # small base

    # --- Budget Compact (0) ---
    # Renter with low budget ceiling → attracted to cheap listings
    if renter["budget_max"] < 900:
        aff[0] += 0.8
    elif renter["budget_max"] < 1100:
        aff[0] += 0.3

    # --- Spacious Family (1) ---
    if renter["desired_beds"] >= 3:
        aff[1] += 0.7
    if renter["household_size"] >= 3:
        aff[1] += 0.4
    if renter["desired_sqft_min"] > 1100:
        aff[1] += 0.3

    # --- Pet-Friendly (2) ---
    if renter["has_cats"] == 1:
        aff[2] += 0.5
    if renter["has_dogs"] == 1:
        aff[2] += 0.5

    # --- Premium / Luxury (3) ---
    if renter["budget_max"] > 1500:
        aff[3] += 0.6
    if renter["wants_furnished"] == 1:
        aff[3] += 0.5
    if renter["income"] > 80_000:
        aff[3] += 0.3

    # --- Urban Convenience (4) ---
    # Renters who prefer apartment type
    type_col = "type_pref_apartment"
    if type_col in renter.index and renter[type_col] == 1:
        aff[4] += 0.6
    # Moderate budget → not budget, not premium
    if 900 <= renter["budget_max"] <= 1500:
        aff[4] += 0.4

    # --- Accessible Modern (5) ---
    if renter["needs_wheelchair"] == 1:
        aff[5] += 1.0
    if renter["has_ev"] == 1:
        aff[5] += 0.8

    return aff


# ── 4) sample liked listings per user ────────────────────────────────────

def sample_liked_listings(
    renter: pd.Series,
    listings: pd.DataFrame,
    listing_categories: pd.Series,
    num_likes: int,
    rng: np.random.Generator,
    noise: float = 0.20,
) -> Tuple[np.ndarray, List[dict]]:
    """
    For one renter, sample `num_likes` listings they would "like".

    Steps:
        1. Compute category affinity for this renter.
        2. Apply hard-constraint filter to get eligible listings.
        3. For each eligible listing, compute a sampling weight =
           category_affinity[listing_cat] + small uniform noise.
        4. Sample `num_likes` listings (without replacement) using
           those weights.

    Returns:
        feedback_array : np.ndarray  shape (NUM_CATEGORIES,)
            Count of liked listings per category.
        detail_rows : list of dicts
            One dict per liked listing for the CSV detail log.
    """
    affinity = compute_user_category_affinity(renter)

    # Hard-constraint filter (vectorized)
    eligible_mask = _vectorized_hard_filter(renter, listings)
    eligible_idx = np.where(eligible_mask)[0]

    if len(eligible_idx) == 0:
        # Extremely constrained user – relax to all listings
        eligible_idx = np.arange(len(listings))

    # Build sampling weights from category affinity
    eligible_cats = listing_categories.values[eligible_idx]
    weights = affinity[eligible_cats]

    # Add noise so it's not fully deterministic
    weights += rng.uniform(0, noise, size=len(weights))
    weights = np.maximum(weights, 1e-8)
    weights /= weights.sum()

    # Sample (cap at available count)
    k = min(num_likes, len(eligible_idx))
    chosen_local = rng.choice(len(eligible_idx), size=k, replace=False, p=weights)
    chosen_global = eligible_idx[chosen_local]

    # Build feedback array
    feedback = np.zeros(NUM_CATEGORIES, dtype=int)
    detail_rows: List[dict] = []

    for gi in chosen_global:
        cat_id = listing_categories.iloc[gi]
        feedback[cat_id] += 1
        detail_rows.append({
            "renter_id": int(renter["renter_id"]),
            "listing_id": listings.iloc[gi]["id"],
            "listing_price": listings.iloc[gi]["price"],
            "listing_beds": listings.iloc[gi]["beds"],
            "listing_sqfeet": listings.iloc[gi]["sqfeet"],
            "listing_type": listings.iloc[gi]["type"],
            "category_id": int(cat_id),
            "category_name": CATEGORY_NAMES[int(cat_id)],
        })

    return feedback, detail_rows


# ── 5) main pipeline ─────────────────────────────────────────────────────

def clean_listings(listings: pd.DataFrame) -> pd.DataFrame:
    """Same cleaning rules as generate_renter_data.main()."""
    return listings[
        (listings["price"] > 50) & (listings["price"] < 15_000)
        & (listings["sqfeet"] > 50) & (listings["sqfeet"] < 15_000)
        & (listings["beds"] >= 0) & (listings["beds"] <= 10)
        & listings["lat"].notna() & listings["long"].notna()
    ].reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Categorize listings & map renters to liked listings"
    )
    p.add_argument(
        "--listings-csv", type=Path,
        default=Path("app/ai/dataset/housing_train.csv"),
        help="Path to raw listings CSV",
    )
    p.add_argument(
        "--renters-csv", type=Path,
        default=Path("app/ai/dataset/renters_synthetic.csv"),
        help="Path to synthetic renters CSV (from generate_renter_data)",
    )
    p.add_argument(
        "--likes", type=int, default=15,
        help="Number of listings each user 'likes'",
    )
    p.add_argument(
        "--noise", type=float, default=0.20,
        help="Noise added to category-affinity sampling weights [0..1]",
    )
    p.add_argument(
        "--seed", type=int, default=42,
    )
    # ── output paths ──────────────────────────────────────────────────
    p.add_argument(
        "--out-listing-cats-csv", type=Path,
        default=Path("app/ai/dataset/listing_categories.csv"),
        help="Output: listing id → category mapping",
    )
    p.add_argument(
        "--out-feedback-csv", type=Path,
        default=Path("app/ai/dataset/user_feedback.csv"),
        help="Output: per-user feedback array + detail",
    )
    p.add_argument(
        "--out-detail-csv", type=Path,
        default=Path("app/ai/dataset/liked_listings_detail.csv"),
        help="Output: detailed log of every liked listing per user",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    # ── load & clean listings ─────────────────────────────────────────
    print(f"Loading listings from {args.listings_csv} ...")
    listings = pd.read_csv(args.listings_csv)
    orig = len(listings)
    listings = clean_listings(listings)
    print(f"  kept {len(listings):,} / {orig:,} after cleaning")

    # ── categorize listings ───────────────────────────────────────────
    print("Categorizing listings into 6 categories ...")
    listing_cats = categorize_listings(listings)
    listings["category_id"] = listing_cats
    listings["category_name"] = listing_cats.map(CATEGORY_NAMES)

    # Show distribution
    print("\n  Category distribution:")
    for cid in range(NUM_CATEGORIES):
        count = (listing_cats == cid).sum()
        pct = 100 * count / len(listings)
        print(f"    {cid}  {CATEGORY_NAMES[cid]:<22s}  {count:>7,}  ({pct:5.1f}%)")
    print()

    # Save listing → category mapping
    args.out_listing_cats_csv.parent.mkdir(parents=True, exist_ok=True)
    listings[["id", "category_id", "category_name"]].to_csv(
        args.out_listing_cats_csv, index=False,
    )
    print(f"  saved listing categories -> {args.out_listing_cats_csv}")

    # ── load renters ──────────────────────────────────────────────────
    print(f"\nLoading renters from {args.renters_csv} ...")
    renters = pd.read_csv(args.renters_csv)
    print(f"  {len(renters):,} renters loaded")

    # ── map each renter to liked listings ─────────────────────────────
    print(f"\nMapping each renter to {args.likes} liked listings "
          f"(noise={args.noise}) ...")
    all_feedback: List[np.ndarray] = []
    all_detail: List[dict] = []

    for idx, renter in renters.iterrows():
        fb, detail = sample_liked_listings(
            renter, listings, listing_cats,
            num_likes=args.likes, rng=rng, noise=args.noise,
        )
        all_feedback.append(fb)
        all_detail.extend(detail)

        if (idx + 1) % 5000 == 0 or idx == len(renters) - 1:
            print(f"  processed {idx + 1:,} / {len(renters):,} renters")

    # ── build feedback DataFrame ──────────────────────────────────────
    fb_matrix = np.vstack(all_feedback)  # shape (n_renters, NUM_CATEGORIES)
    fb_df = pd.DataFrame(
        fb_matrix,
        columns=[f"cat_{i}_{CATEGORY_NAMES[i].replace(' / ', '_').replace(' ', '_')}"
                 for i in range(NUM_CATEGORIES)],
    )
    fb_df.insert(0, "renter_id", renters["renter_id"].values)

    # Add totals & dominant category for quick inspection
    fb_df["total_likes"] = fb_matrix.sum(axis=1)
    fb_df["dominant_category_id"] = fb_matrix.argmax(axis=1)
    fb_df["dominant_category_name"] = fb_df["dominant_category_id"].map(CATEGORY_NAMES)

    # ── save outputs ──────────────────────────────────────────────────
    args.out_feedback_csv.parent.mkdir(parents=True, exist_ok=True)
    fb_df.to_csv(args.out_feedback_csv, index=False)
    print(f"\n  saved user feedback array -> {args.out_feedback_csv}")

    detail_df = pd.DataFrame(all_detail)
    args.out_detail_csv.parent.mkdir(parents=True, exist_ok=True)
    detail_df.to_csv(args.out_detail_csv, index=False)
    print(f"  saved liked listings detail -> {args.out_detail_csv}")

    # ── summary stats ─────────────────────────────────────────────────
    print("\n── Summary ─────────────────────────────────────────────")
    print(f"  Renters:              {len(renters):,}")
    print(f"  Likes per renter:     {args.likes}")
    print(f"  Total liked pairs:    {len(detail_df):,}")
    print(f"  Feedback array shape: {fb_matrix.shape}")
    print()
    print("  Mean likes per category across all users:")
    for i in range(NUM_CATEGORIES):
        col = fb_df.columns[1 + i]  # skip renter_id
        print(f"    {CATEGORY_NAMES[i]:<22s}  {fb_df[col].mean():.2f}")
    print()
    print("  Dominant category distribution (most-liked category per user):")
    dom = fb_df["dominant_category_name"].value_counts()
    for name, cnt in dom.items():
        print(f"    {name:<22s}  {cnt:>6,}  ({100*cnt/len(renters):5.1f}%)")

    print("\nDone.")


if __name__ == "__main__":
    main()
