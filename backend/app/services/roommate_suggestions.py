"""
Roommate matching Phase 2: ranked individual suggestions (hard gates + behavior + lifestyle).

Defaults: alpha=0.6 (behavior), beta=0.4 (lifestyle). Two-stage scoring: rank by lifestyle
on the capped candidate pool, then compute fingerprints only for the top behavior_prefilter_k.

When both users are behavior-cold (similarity_behavior cold_cold), final score is lifestyle-only;
behavior is null in the API response for that pair.

Phase 3.2 (optional): with blend_embedding=true, mean item-tower embeddings from recent likes
are blended into the lifestyle term (see EMBEDDING_IN_LIFESTYLE_WEIGHT) before fusion with
behavior. If the two-tower model is unavailable or a user has no encodable likes, embedding
is skipped with no regression.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.dependencies.supabase import get_admin_client
from app.services.listing_category import LISTING_CATEGORY_NAMES, NUM_LISTING_CATEGORIES
from app.services.roommate_behavior_fingerprint import (
    ROOMMATE_BEHAVIOR_MIN_SWIPES,
    build_roommate_behavior_fingerprint,
    similarity_behavior,
)
from app.services.user_group_matching import _norm, calculate_lifestyle_compatibility

logger = logging.getLogger(__name__)

# Fusion weights (documented defaults; behavior + lifestyle in [0,1])
ALPHA_BEHAVIOR = 0.6
BETA_LIFESTYLE = 0.4

# When blend_embedding is on: lifestyle_effective = (1-delta)*lifestyle + delta*embedding_sim
EMBEDDING_IN_LIFESTYLE_WEIGHT = 0.4

DEFAULT_CANDIDATE_POOL_CAP = 300
DEFAULT_EMBEDDING_LIKE_CAP = 50
MAX_EMBEDDING_LIKE_CAP = 100

DEFAULT_BEHAVIOR_PREFILTER_K = 80
MAX_CANDIDATE_POOL_CAP = 500
MAX_BEHAVIOR_PREFILTER_K = 200
MAX_RESULT_LIMIT = 50
USER_BATCH = 200


def clamp_cap(value: int, default: int, max_value: int) -> int:
    if value < 1:
        return default
    return min(value, max_value)


def _city_str(value: Any) -> str:
    return str(value or "").strip().lower()


def budgets_overlap_user(
    u_min: Optional[Any],
    u_max: Optional[Any],
    v_min: Optional[Any],
    v_max: Optional[Any],
) -> bool:
    a = float(u_min or 0)
    b = float(u_max if u_max is not None else float("inf"))
    c = float(v_min or 0)
    d = float(v_max if v_max is not None else float("inf"))
    return b >= c and a <= d


def states_compatible_if_both_set(
    seeker_prefs: Dict[str, Any], cand_prefs: Dict[str, Any]
) -> bool:
    ss = _norm(seeker_prefs.get("target_state_province"))
    cs = _norm(cand_prefs.get("target_state_province"))
    if not ss or not cs:
        return True
    return ss == cs


def effective_gender_policy(prefs: Dict[str, Any]) -> str:
    lp = prefs.get("lifestyle_preferences") or {}
    return _norm(prefs.get("gender_policy") or lp.get("gender_policy") or "mixed_ok")


def passes_same_gender_gate(seeker_prefs: Dict[str, Any], cand_prefs: Dict[str, Any]) -> bool:
    if effective_gender_policy(seeker_prefs) != "same_gender_only":
        return True
    sl = seeker_prefs.get("lifestyle_preferences") or {}
    cl = cand_prefs.get("lifestyle_preferences") or {}
    sg = _norm(sl.get("gender_identity"))
    cg = _norm(cl.get("gender_identity"))
    if not sg:
        return False
    if not cg:
        return False
    return sg == cg


def _group_budget_bounds(group: Dict[str, Any]) -> Tuple[float, float]:
    g_min = group.get("budget_per_person_min")
    if g_min is None:
        g_min = group.get("budget_min")
    g_max = group.get("budget_per_person_max")
    if g_max is None:
        g_max = group.get("budget_max")
    lo = float(g_min or 0)
    hi = float(g_max if g_max is not None else float("inf"))
    return lo, hi


def _group_status_active(group: Dict[str, Any]) -> bool:
    s = group.get("status")
    if s is None:
        return False
    label = str(s).strip().lower()
    return label == "active"


def seeker_compatible_with_group_hard(seeker_prefs: Dict[str, Any], group: Dict[str, Any]) -> bool:
    """Whether seeker's city/state/budget hard prefs align with the group's posted ranges."""
    sc = _city_str(seeker_prefs.get("target_city"))
    gc = _city_str(group.get("target_city"))
    if not sc or not gc or sc != gc:
        return False
    ss = _norm(seeker_prefs.get("target_state_province"))
    gs = _norm(group.get("target_state_province"))
    if ss and gs and ss != gs:
        return False
    glo, ghi = _group_budget_bounds(group)
    return budgets_overlap_user(
        seeker_prefs.get("budget_min"),
        seeker_prefs.get("budget_max"),
        glo,
        ghi,
    )


def candidate_excluded_for_incompatible_group(
    seeker_prefs: Dict[str, Any],
    memberships: List[Dict[str, Any]],
) -> bool:
    """True if user has an accepted membership in an active group that fails seeker hard gates."""
    for row in memberships:
        g = row.get("roommate_groups") or {}
        if not isinstance(g, dict) or not g.get("id"):
            continue
        if not _group_status_active(g):
            continue
        if not seeker_compatible_with_group_hard(seeker_prefs, g):
            return True
    return False


def lifestyle_similarity_user_user(
    seeker_prefs: Dict[str, Any], cand_prefs: Dict[str, Any]
) -> float:
    seeker_life = seeker_prefs.get("lifestyle_preferences") or {}
    cand_life = cand_prefs.get("lifestyle_preferences") or {}
    raw = float(
        calculate_lifestyle_compatibility(
            seeker_life,
            cand_life,
            user_prefs=seeker_prefs,
            group={"_preferred_neighborhoods": cand_prefs.get("preferred_neighborhoods") or []},
        )
    )
    return max(0.0, min(1.0, raw / 20.0))


def _price_band_reason(mean_a: Optional[float], mean_b: Optional[float]) -> Optional[str]:
    if mean_a is None or mean_b is None or mean_a <= 0 or mean_b <= 0:
        return None
    hi, lo = (mean_a, mean_b) if mean_a >= mean_b else (mean_b, mean_a)
    if hi <= 0:
        return None
    if (hi - lo) / hi <= 0.15:
        return "Similar liked price band on listings"
    return None


def _beds_reason(ba: Optional[float], bb: Optional[float]) -> Optional[str]:
    if ba is None or bb is None:
        return None
    try:
        if abs(float(ba) - float(bb)) <= 0.51:
            return "Similar bedroom count in listings you both liked"
    except (TypeError, ValueError):
        return None
    return None


def _category_overlap_reasons(
    counts_a: List[float], counts_b: List[float], max_n: int
) -> List[str]:
    if len(counts_a) != NUM_LISTING_CATEGORIES or len(counts_b) != NUM_LISTING_CATEGORIES:
        return []
    scored: List[Tuple[float, int]] = []
    for i in range(NUM_LISTING_CATEGORIES):
        ca = float(counts_a[i] or 0)
        cb = float(counts_b[i] or 0)
        if ca <= 0 or cb <= 0:
            continue
        scored.append((ca * cb, i))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[str] = []
    for _, idx in scored[:max_n]:
        name = LISTING_CATEGORY_NAMES.get(idx, f"category_{idx}")
        out.append(f"Both engage with {name} listings")
    return out


def build_top_reasons(
    seeker_prefs: Dict[str, Any],
    cand_prefs: Dict[str, Any],
    meta_s: Dict[str, Any],
    meta_c: Dict[str, Any],
    max_reasons: int = 3,
) -> List[str]:
    reasons: List[str] = []

    pr = _price_band_reason(meta_s.get("liked_mean_price"), meta_c.get("liked_mean_price"))
    if pr:
        reasons.append(pr)

    br = _beds_reason(meta_s.get("liked_mean_beds"), meta_c.get("liked_mean_beds"))
    if br:
        reasons.append(br)

    reasons.extend(
        _category_overlap_reasons(
            list(meta_s.get("category_counts") or []),
            list(meta_c.get("category_counts") or []),
            max_n=max_reasons,
        )
    )

    sl = seeker_prefs.get("lifestyle_preferences") or {}
    cl = cand_prefs.get("lifestyle_preferences") or {}
    sclean = _norm(sl.get("cleanliness_level") or sl.get("cleanliness"))
    cclean = _norm(cl.get("cleanliness_level") or cl.get("cleanliness"))
    if sclean and cclean and sclean == cclean:
        reasons.append("Similar cleanliness preference")

    if _norm(sl.get("social_preference")) and _norm(sl.get("social_preference")) == _norm(
        cl.get("social_preference")
    ):
        reasons.append("Similar social noise preference")

    sn = {_norm(x) for x in (seeker_prefs.get("preferred_neighborhoods") or []) if _norm(x)}
    cn = {_norm(x) for x in (cand_prefs.get("preferred_neighborhoods") or []) if _norm(x)}
    if sn and cn and sn.intersection(cn):
        reasons.append("Overlapping neighborhood interests")

    ua = {_norm(x) for x in (sl.get("amenity_priorities") or []) if _norm(x)}
    va = {_norm(x) for x in (cl.get("amenity_priorities") or []) if _norm(x)}
    if ua and va and ua.intersection(va):
        reasons.append("Shared amenity priorities")

    if not reasons:
        reasons.append("Compatible location and budget; explore lifestyle fit in chat")

    # de-dupe preserving order
    seen = set()
    unique: List[str] = []
    for r in reasons:
        if r in seen:
            continue
        seen.add(r)
        unique.append(r)
    return unique[:max_reasons]


def fuse_final_score(
    behavior_sim: Optional[float], lifestyle_sim: float, alpha: float, beta: float
) -> float:
    if behavior_sim is None:
        return lifestyle_sim
    return alpha * behavior_sim + beta * lifestyle_sim


def blend_lifestyle_with_embedding(
    lifestyle_sim: float,
    embedding_sim: Optional[float],
    *,
    delta: float = EMBEDDING_IN_LIFESTYLE_WEIGHT,
) -> float:
    """Blend raw lifestyle [0,1] with taste embedding similarity; no-op if embedding is None."""
    if embedding_sim is None:
        return float(lifestyle_sim)
    d = max(0.0, min(1.0, float(delta)))
    return (1.0 - d) * float(lifestyle_sim) + d * float(embedding_sim)


def _chunked(ids: List[str], size: int) -> List[List[str]]:
    return [ids[i : i + size] for i in range(0, len(ids), size)]


async def get_roommate_suggestions(
    seeker_id: str,
    seeker_prefs: Dict[str, Any],
    *,
    limit: int = 20,
    candidate_pool_cap: int = DEFAULT_CANDIDATE_POOL_CAP,
    behavior_prefilter_k: int = DEFAULT_BEHAVIOR_PREFILTER_K,
    alpha: float = ALPHA_BEHAVIOR,
    beta: float = BETA_LIFESTYLE,
    blend_embedding: bool = False,
    embedding_like_cap: int = DEFAULT_EMBEDDING_LIKE_CAP,
) -> Dict[str, Any]:
    """
    Returns dict: user_id, weights, suggestions (list), and optional debug timings via logging.
    """
    city = seeker_prefs.get("target_city")
    if not city or not str(city).strip():
        raise ValueError("target_city is required on your profile to get roommate suggestions")

    cap = clamp_cap(candidate_pool_cap, DEFAULT_CANDIDATE_POOL_CAP, MAX_CANDIDATE_POOL_CAP)
    pre_k = clamp_cap(behavior_prefilter_k, DEFAULT_BEHAVIOR_PREFILTER_K, MAX_BEHAVIOR_PREFILTER_K)
    out_limit = max(1, min(limit, MAX_RESULT_LIMIT))
    like_k = max(1, min(int(embedding_like_cap), MAX_EMBEDDING_LIKE_CAP))

    _rec: Any = None
    seeker_taste_vec: Optional[Any] = None
    if blend_embedding:
        from app.ai import recommender as _rec

        seeker_taste_vec = _rec.mean_taste_item_embedding(
            seeker_id, k=like_k, days=180, max_events=2000
        )

    supabase = get_admin_client()
    target_city = str(city).strip()

    pool_resp = (
        supabase.table("personal_preferences")
        .select("*")
        .neq("user_id", seeker_id)
        .ilike("target_city", target_city)
        .order("updated_at", desc=True)
        .limit(cap)
        .execute()
    )
    raw_rows: List[Dict[str, Any]] = list(pool_resp.data or [])

    gated: List[Dict[str, Any]] = []
    for row in raw_rows:
        cid = row.get("user_id")
        if not cid:
            continue
        if not budgets_overlap_user(
            seeker_prefs.get("budget_min"),
            seeker_prefs.get("budget_max"),
            row.get("budget_min"),
            row.get("budget_max"),
        ):
            continue
        if not states_compatible_if_both_set(seeker_prefs, row):
            continue
        if not passes_same_gender_gate(seeker_prefs, row):
            continue
        gated.append(row)

    candidate_ids = [str(r["user_id"]) for r in gated]
    memberships_by_user: Dict[str, List[Dict[str, Any]]] = {uid: [] for uid in candidate_ids}

    for chunk in _chunked(candidate_ids, USER_BATCH):
        if not chunk:
            continue
        mem_resp = (
            supabase.table("group_members")
            .select("user_id, roommate_groups(*)")
            .in_("user_id", chunk)
            .eq("status", "accepted")
            .execute()
        )
        for mrow in mem_resp.data or []:
            uid = str(mrow.get("user_id") or "")
            if uid in memberships_by_user:
                memberships_by_user[uid].append(mrow)

    filtered: List[Dict[str, Any]] = []
    for row in gated:
        uid = str(row["user_id"])
        if candidate_excluded_for_incompatible_group(seeker_prefs, memberships_by_user.get(uid, [])):
            continue
        filtered.append(row)

    if not filtered:
        weights_out: Dict[str, Any] = {"alpha": alpha, "beta": beta}
        if blend_embedding:
            weights_out["embedding_in_lifestyle"] = EMBEDDING_IN_LIFESTYLE_WEIGHT
        return {
            "user_id": seeker_id,
            "weights": weights_out,
            "suggestions": [],
        }

    lifestyle_scored: List[Tuple[float, Dict[str, Any]]] = []
    for row in filtered:
        ls = lifestyle_similarity_user_user(seeker_prefs, row)
        lifestyle_scored.append((ls, row))

    lifestyle_scored.sort(key=lambda x: x[0], reverse=True)
    shortlist = [row for _, row in lifestyle_scored[:pre_k]]

    fp_seeker = build_roommate_behavior_fingerprint(seeker_id)
    meta_seeker = fp_seeker.get("metadata") or {}

    ranked: List[Dict[str, Any]] = []
    for row in shortlist:
        cid = str(row["user_id"])
        fp_c = build_roommate_behavior_fingerprint(cid)
        beh = similarity_behavior(
            fp_seeker,
            fp_c,
            prefs_u=seeker_prefs,
            prefs_v=row,
            k=ROOMMATE_BEHAVIOR_MIN_SWIPES,
        )
        ls = lifestyle_similarity_user_user(seeker_prefs, row)
        emb_sim: Optional[float] = None
        if blend_embedding and seeker_taste_vec is not None and _rec is not None:
            cand_taste = _rec.mean_taste_item_embedding(cid, k=like_k, days=180, max_events=2000)
            emb_sim = _rec.taste_similarity_from_mean_embeddings(seeker_taste_vec, cand_taste)
        ls_eff = blend_lifestyle_with_embedding(ls, emb_sim) if blend_embedding else ls

        if beh.get("cold_cold"):
            b_val = None
            final = ls_eff
            conf = "low"
        else:
            b_val = float(beh["similarity"])
            final = fuse_final_score(b_val, ls_eff, alpha, beta)
            conf = str(beh.get("behavior_confidence") or "low")

        score_row: Dict[str, Any] = {
            "behavior": b_val,
            "lifestyle": round(ls, 4),
            "final": round(final, 4),
            "behavior_confidence": conf,
        }
        if blend_embedding:
            score_row["embedding"] = round(emb_sim, 4) if emb_sim is not None else None

        ranked.append(
            {
                "user_id": cid,
                "final": final,
                "scores": score_row,
                "cand_prefs": row,
                "meta_c": fp_c.get("metadata") or {},
            }
        )

    ranked.sort(key=lambda x: x["final"], reverse=True)
    top = ranked[:out_limit]
    top_ids = [t["user_id"] for t in top]

    profiles: Dict[str, Dict[str, Any]] = {}
    for chunk in _chunked(top_ids, USER_BATCH):
        uresp = (
            supabase.table("users")
            .select("id, full_name, verification_status, profile_picture_url, company_name, school_name")
            .in_("id", chunk)
            .execute()
        )
        for u in uresp.data or []:
            profiles[str(u["id"])] = u

    suggestions: List[Dict[str, Any]] = []
    for item in top:
        uid = item["user_id"]
        prof = profiles.get(uid, {})
        reasons = build_top_reasons(
            seeker_prefs,
            item["cand_prefs"],
            meta_seeker,
            item["meta_c"],
        )
        suggestions.append(
            {
                "user_id": uid,
                "scores": item["scores"],
                "reasons": reasons,
                "profile": {
                    "full_name": prof.get("full_name"),
                    "verification_status": prof.get("verification_status"),
                    "profile_picture_url": prof.get("profile_picture_url"),
                    "company_name": prof.get("company_name"),
                    "school_name": prof.get("school_name"),
                },
            }
        )

    logger.debug(
        "roommate_suggestions seeker=%s pool=%d gated=%d shortlist=%d out=%d",
        seeker_id,
        len(raw_rows),
        len(filtered),
        len(shortlist),
        len(suggestions),
    )

    weights_out = {"alpha": alpha, "beta": beta}
    if blend_embedding:
        weights_out["embedding_in_lifestyle"] = EMBEDDING_IN_LIFESTYLE_WEIGHT

    return {
        "user_id": seeker_id,
        "weights": weights_out,
        "suggestions": suggestions,
    }


__all__ = [
    "ALPHA_BEHAVIOR",
    "BETA_LIFESTYLE",
    "EMBEDDING_IN_LIFESTYLE_WEIGHT",
    "DEFAULT_EMBEDDING_LIKE_CAP",
    "MAX_EMBEDDING_LIKE_CAP",
    "DEFAULT_BEHAVIOR_PREFILTER_K",
    "DEFAULT_CANDIDATE_POOL_CAP",
    "blend_lifestyle_with_embedding",
    "MAX_BEHAVIOR_PREFILTER_K",
    "MAX_CANDIDATE_POOL_CAP",
    "MAX_RESULT_LIMIT",
    "budgets_overlap_user",
    "candidate_excluded_for_incompatible_group",
    "fuse_final_score",
    "get_roommate_suggestions",
    "lifestyle_similarity_user_user",
    "passes_same_gender_gate",
    "seeker_compatible_with_group_hard",
    "states_compatible_if_both_set",
]
