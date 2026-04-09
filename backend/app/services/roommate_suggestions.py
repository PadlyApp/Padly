"""
Roommate matching Phase 2: ranked individual suggestions (hard gates + behavior + lifestyle).

Defaults: alpha=0.6 (behavior), beta=0.4 (lifestyle). Two-stage scoring: rank by lifestyle
on the capped candidate pool, then compute fingerprints only for the top behavior_prefilter_k.

When both users are behavior-cold (similarity_behavior cold_cold), final score is lifestyle-only;
behavior is null in the API response for that pair.

Phase 3.2: mean item-tower embeddings from recent likes are blended into the lifestyle term
(see EMBEDDING_IN_LIFESTYLE_WEIGHT) before fusion with behavior. If the two-tower model is
unavailable or a user has no encodable likes, embedding is skipped with no regression.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.dependencies.supabase import get_admin_client
from app.services.location_matching import cities_match, metro_for_city
from app.services.preferences_contract import (
    lease_types_compatible,
    resolve_furnished_preference,
    target_furnished_from_preference,
)
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
DATE_FLEXIBILITY_DAYS = 60
SUGGESTION_MODE_ML = "ml"
SUGGESTION_MODE_HARD_FILTER = "hard_filter"
_SUGGESTION_MODES = {SUGGESTION_MODE_ML, SUGGESTION_MODE_HARD_FILTER}
_CANDIDATE_PAGE_SIZE = 500


def clamp_cap(value: int, default: int, max_value: int) -> int:
    if value < 1:
        return default
    return min(value, max_value)


def _city_str(value: Any) -> str:
    return str(value or "").strip().lower()


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def _load_city_candidate_rows(
    supabase: Any,
    *,
    seeker_id: str,
    target_city: str,
    cap: Optional[int],
) -> List[Dict[str, Any]]:
    """
    Load personal_preferences rows for the target city excluding seeker.
    cap=None means fetch all pages.
    """
    city_value = str(target_city or "").strip()
    metro_mode = metro_for_city(city_value) is not None

    base = (
        supabase.table("personal_preferences")
        .select("*")
        .neq("user_id", seeker_id)
        .order("updated_at", desc=True)
    )
    if not metro_mode:
        base = base.ilike("target_city", city_value)
        if cap is not None:
            resp = base.limit(cap).execute()
            return list(resp.data or [])

    out: List[Dict[str, Any]] = []
    start = 0
    while True:
        resp = base.range(start, start + _CANDIDATE_PAGE_SIZE - 1).execute()
        page_rows = list(resp.data or [])
        if not page_rows:
            break
        rows = page_rows
        if metro_mode:
            rows = [
                row for row in rows
                if row.get("target_city") and cities_match(city_value, row.get("target_city"))
            ]
        out.extend(rows)
        if cap is not None and len(out) >= cap:
            return out[:cap]
        if len(page_rows) < _CANDIDATE_PAGE_SIZE:
            break
        start += _CANDIDATE_PAGE_SIZE
    return out


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


def countries_compatible_if_both_set(
    seeker_prefs: Dict[str, Any], cand_prefs: Dict[str, Any]
) -> bool:
    sc = _norm(seeker_prefs.get("target_country"))
    cc = _norm(cand_prefs.get("target_country"))
    if not sc or not cc:
        return True
    return sc == cc


def cities_compatible_if_both_set(
    seeker_prefs: Dict[str, Any], cand_prefs: Dict[str, Any]
) -> bool:
    sc = _city_str(seeker_prefs.get("target_city"))
    cc = _city_str(cand_prefs.get("target_city"))
    if not sc or not cc:
        return True
    return cities_match(sc, cc)


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


def _effective_furnished_preference(prefs: Dict[str, Any]) -> Optional[str]:
    return resolve_furnished_preference(
        prefs.get("furnished_preference"),
        prefs.get("target_furnished"),
    )


def _requires_furnished(prefs: Dict[str, Any]) -> bool:
    pref = _effective_furnished_preference(prefs)
    if pref == "required":
        return True
    return bool(prefs.get("furnished_is_hard")) and target_furnished_from_preference(pref) is True


def furnished_preferences_compatible(
    seeker_prefs: Dict[str, Any], cand_prefs: Dict[str, Any]
) -> bool:
    """
    Hard-gate furnished requirement.
    Only blocks when one side requires furnished and the other side explicitly opts out.
    """
    if not _requires_furnished(seeker_prefs) and not _requires_furnished(cand_prefs):
        return True

    cand_pref = _effective_furnished_preference(cand_prefs)
    seeker_pref = _effective_furnished_preference(seeker_prefs)
    cand_target = target_furnished_from_preference(cand_pref)
    seeker_target = target_furnished_from_preference(seeker_pref)

    if _requires_furnished(seeker_prefs) and cand_target is False:
        return False
    if _requires_furnished(cand_prefs) and seeker_target is False:
        return False
    return True


def move_in_dates_compatible_if_both_set(
    seeker_prefs: Dict[str, Any],
    cand_prefs: Dict[str, Any],
    *,
    max_days: int = DATE_FLEXIBILITY_DAYS,
) -> bool:
    sd = _parse_date(seeker_prefs.get("move_in_date"))
    cd = _parse_date(cand_prefs.get("move_in_date") or cand_prefs.get("target_move_in_date"))
    if sd is None or cd is None:
        return True
    return abs((sd - cd).days) <= max_days


def lease_duration_compatible_if_both_set(
    seeker_prefs: Dict[str, Any],
    cand_prefs: Dict[str, Any],
) -> bool:
    sd = _safe_int(seeker_prefs.get("target_lease_duration_months"))
    cd = _safe_int(cand_prefs.get("target_lease_duration_months"))
    if sd is None or cd is None:
        return True
    return sd == cd


def required_bedrooms_compatible_if_both_set(
    seeker_prefs: Dict[str, Any],
    cand_prefs: Dict[str, Any],
) -> bool:
    sb = _safe_int(seeker_prefs.get("required_bedrooms"))
    cb = _safe_int(cand_prefs.get("required_bedrooms"))
    if sb is None or cb is None:
        return True
    return sb == cb


def target_bathrooms_compatible_if_both_set(
    seeker_prefs: Dict[str, Any],
    cand_prefs: Dict[str, Any],
) -> bool:
    sb = _safe_float(seeker_prefs.get("target_bathrooms"))
    cb = _safe_float(cand_prefs.get("target_bathrooms"))
    if sb is None or cb is None:
        return True
    return abs(sb - cb) <= 1e-6


def target_deposit_compatible_if_both_set(
    seeker_prefs: Dict[str, Any],
    cand_prefs: Dict[str, Any],
) -> bool:
    """
    Seeker-side hard cap semantics:
    if both users specified max deposit, candidate's cap must not exceed seeker's cap.
    """
    sd = _safe_float(seeker_prefs.get("target_deposit_amount"))
    cd = _safe_float(cand_prefs.get("target_deposit_amount"))
    if sd is None or cd is None:
        return True
    return cd <= sd


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


def lease_types_compatible_if_both_set(
    seeker_prefs: Dict[str, Any],
    cand_prefs: Dict[str, Any],
) -> bool:
    return lease_types_compatible(
        seeker_prefs.get("target_lease_type"),
        cand_prefs.get("target_lease_type"),
    )


def passes_all_hard_gates_user_user(
    seeker_prefs: Dict[str, Any],
    cand_prefs: Dict[str, Any],
) -> bool:
    return (
        countries_compatible_if_both_set(seeker_prefs, cand_prefs)
        and cities_compatible_if_both_set(seeker_prefs, cand_prefs)
        and states_compatible_if_both_set(seeker_prefs, cand_prefs)
        and budgets_overlap_user(
            seeker_prefs.get("budget_min"),
            seeker_prefs.get("budget_max"),
            cand_prefs.get("budget_min"),
            cand_prefs.get("budget_max"),
        )
        and required_bedrooms_compatible_if_both_set(seeker_prefs, cand_prefs)
        and target_bathrooms_compatible_if_both_set(seeker_prefs, cand_prefs)
        and target_deposit_compatible_if_both_set(seeker_prefs, cand_prefs)
        and move_in_dates_compatible_if_both_set(seeker_prefs, cand_prefs)
        and lease_types_compatible_if_both_set(seeker_prefs, cand_prefs)
        and lease_duration_compatible_if_both_set(seeker_prefs, cand_prefs)
        and furnished_preferences_compatible(seeker_prefs, cand_prefs)
        and passes_same_gender_gate(seeker_prefs, cand_prefs)
        and passes_same_gender_gate(cand_prefs, seeker_prefs)
    )


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
    """Whether seeker's hard prefs align with the group's posted hard constraints."""
    seeker_country = _norm(seeker_prefs.get("target_country"))
    group_country = _norm(group.get("target_country"))
    if seeker_country and group_country and seeker_country != group_country:
        return False

    sc = _city_str(seeker_prefs.get("target_city"))
    gc = _city_str(group.get("target_city"))
    if not sc or not gc or not cities_match(sc, gc):
        return False

    ss = _norm(seeker_prefs.get("target_state_province"))
    gs = _norm(group.get("target_state_province"))
    if ss and gs and ss != gs:
        return False

    glo, ghi = _group_budget_bounds(group)
    if not budgets_overlap_user(
        seeker_prefs.get("budget_min"),
        seeker_prefs.get("budget_max"),
        glo,
        ghi,
    ):
        return False

    if not required_bedrooms_compatible_if_both_set(
        seeker_prefs,
        {"required_bedrooms": group.get("required_bedrooms") or group.get("target_bedrooms")},
    ):
        return False

    if not target_bathrooms_compatible_if_both_set(
        seeker_prefs,
        {"target_bathrooms": group.get("target_bathrooms")},
    ):
        return False

    if not target_deposit_compatible_if_both_set(
        seeker_prefs,
        {"target_deposit_amount": group.get("target_deposit_amount")},
    ):
        return False

    if not move_in_dates_compatible_if_both_set(
        seeker_prefs,
        {"move_in_date": group.get("target_move_in_date") or group.get("move_in_date")},
    ):
        return False

    if not lease_types_compatible_if_both_set(
        seeker_prefs,
        {"target_lease_type": group.get("target_lease_type")},
    ):
        return False

    if not lease_duration_compatible_if_both_set(
        seeker_prefs,
        {"target_lease_duration_months": group.get("target_lease_duration_months")},
    ):
        return False

    if not furnished_preferences_compatible(
        seeker_prefs,
        {
            "furnished_preference": group.get("furnished_preference"),
            "target_furnished": group.get("target_furnished"),
            "furnished_is_hard": group.get("furnished_is_hard"),
        },
    ):
        return False

    return True


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
            group={
                "_preferred_neighborhoods": cand_prefs.get("preferred_neighborhoods") or [],
                "target_house_rules": cand_prefs.get("target_house_rules"),
            },
        )
    )
    return max(0.0, min(1.0, raw / 20.0))


def build_top_reasons(
    seeker_prefs: Dict[str, Any],
    cand_prefs: Dict[str, Any],
    meta_s: Dict[str, Any],
    meta_c: Dict[str, Any],
    max_reasons: int = 3,
) -> List[str]:
    """
    Explainability aligned to new PreferencesForm soft constraints only.
    """
    _ = meta_s, meta_c
    reasons: List[str] = []

    sl = seeker_prefs.get("lifestyle_preferences") or {}
    cl = cand_prefs.get("lifestyle_preferences") or {}
    sclean = _norm(sl.get("cleanliness_level"))
    cclean = _norm(cl.get("cleanliness_level"))
    if sclean and cclean and sclean == cclean:
        reasons.append("Similar cleanliness preference")

    if _norm(sl.get("social_preference")) and _norm(sl.get("social_preference")) == _norm(
        cl.get("social_preference")
    ):
        reasons.append("Similar social noise preference")

    if _norm(sl.get("cooking_frequency")) and _norm(sl.get("cooking_frequency")) == _norm(
        cl.get("cooking_frequency")
    ):
        reasons.append("Similar cooking frequency")

    if _norm(sl.get("gender_identity")) and _norm(sl.get("gender_identity")) == _norm(
        cl.get("gender_identity")
    ):
        reasons.append("Same gender identity preference")

    sn = {_norm(x) for x in (seeker_prefs.get("preferred_neighborhoods") or []) if _norm(x)}
    cn = {_norm(x) for x in (cand_prefs.get("preferred_neighborhoods") or []) if _norm(x)}
    if sn and cn and sn.intersection(cn):
        reasons.append("Overlapping neighborhood interests")

    ua = {_norm(x) for x in (sl.get("amenity_priorities") or []) if _norm(x)}
    va = {_norm(x) for x in (cl.get("amenity_priorities") or []) if _norm(x)}
    if ua and va and ua.intersection(va):
        reasons.append("Shared amenity priorities")

    ub = {_norm(x) for x in (sl.get("building_type_preferences") or []) if _norm(x)}
    vb = {_norm(x) for x in (cl.get("building_type_preferences") or []) if _norm(x)}
    if ub and vb and ub.intersection(vb):
        reasons.append("Shared building type preferences")

    user_rules = _norm(seeker_prefs.get("target_house_rules"))
    cand_rules = _norm(cand_prefs.get("target_house_rules"))
    if user_rules and cand_rules and user_rules == cand_rules:
        reasons.append("Aligned house rules expectations")

    if not reasons:
        reasons.append("Compatible soft-constraint profile; explore fit in chat")

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
    blend_embedding: bool = True,
    embedding_like_cap: int = DEFAULT_EMBEDDING_LIKE_CAP,
    mode: str = SUGGESTION_MODE_ML,
) -> Dict[str, Any]:
    """
    Returns dict: user_id, weights, suggestions (list), and optional debug timings via logging.
    """
    city = seeker_prefs.get("target_city")
    if not city or not str(city).strip():
        raise ValueError("target_city is required on your profile to get roommate suggestions")

    mode_norm = str(mode or SUGGESTION_MODE_ML).strip().lower()
    if mode_norm not in _SUGGESTION_MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(_SUGGESTION_MODES))}")

    cap = clamp_cap(candidate_pool_cap, DEFAULT_CANDIDATE_POOL_CAP, MAX_CANDIDATE_POOL_CAP)
    pre_k = clamp_cap(behavior_prefilter_k, DEFAULT_BEHAVIOR_PREFILTER_K, MAX_BEHAVIOR_PREFILTER_K)
    out_limit = max(1, min(limit, MAX_RESULT_LIMIT))
    like_k = max(1, min(int(embedding_like_cap), MAX_EMBEDDING_LIKE_CAP))

    from app.services import ml_client as _mlc

    seeker_taste_vec: Optional[Any] = None
    if blend_embedding and mode_norm == SUGGESTION_MODE_ML:
        seeker_taste_vec = await _mlc.mean_taste_item_embedding(
            seeker_id, k=like_k, days=180, max_events=2000
        )

    supabase = get_admin_client()
    target_city = str(city).strip()

    raw_rows: List[Dict[str, Any]] = _load_city_candidate_rows(
        supabase,
        seeker_id=seeker_id,
        target_city=target_city,
        cap=cap if mode_norm == SUGGESTION_MODE_ML else None,
    )

    gated: List[Dict[str, Any]] = []
    for row in raw_rows:
        cid = row.get("user_id")
        if not cid:
            continue
        if not passes_all_hard_gates_user_user(seeker_prefs, row):
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
        weights_out: Dict[str, Any] = {"mode": mode_norm, "alpha": alpha, "beta": beta}
        if blend_embedding:
            weights_out["embedding_in_lifestyle"] = EMBEDDING_IN_LIFESTYLE_WEIGHT
        return {
            "user_id": seeker_id,
            "weights": weights_out,
            "suggestions": [],
        }

    if mode_norm == SUGGESTION_MODE_HARD_FILTER:
        filtered_ids = [str(r["user_id"]) for r in filtered]
        profiles: Dict[str, Dict[str, Any]] = {}
        for chunk in _chunked(filtered_ids, USER_BATCH):
            uresp = (
                supabase.table("users")
                .select("id, full_name, verification_status, profile_picture_url, company_name, school_name")
                .in_("id", chunk)
                .execute()
            )
            for u in uresp.data or []:
                profiles[str(u["id"])] = u

        suggestions: List[Dict[str, Any]] = []
        for row in filtered:
            uid = str(row["user_id"])
            prof = profiles.get(uid, {})
            suggestions.append(
                {
                    "user_id": uid,
                    "scores": {
                        "behavior": None,
                        "lifestyle": None,
                        "final": None,
                        "behavior_confidence": "hard_filter",
                        "embedding": None,
                    },
                    "reasons": ["Meets your hard constraints"],
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
            "roommate_suggestions_hard_filter seeker=%s pool=%d gated=%d out=%d",
            seeker_id,
            len(raw_rows),
            len(filtered),
            len(suggestions),
        )

        weights_out: Dict[str, Any] = {"mode": mode_norm, "alpha": alpha, "beta": beta}
        if blend_embedding:
            weights_out["embedding_in_lifestyle"] = EMBEDDING_IN_LIFESTYLE_WEIGHT
        return {
            "user_id": seeker_id,
            "weights": weights_out,
            "suggestions": suggestions,
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
        if blend_embedding and seeker_taste_vec is not None:
            cand_taste = await _mlc.mean_taste_item_embedding(cid, k=like_k, days=180, max_events=2000)
            emb_sim = _mlc.taste_similarity_from_mean_embeddings(seeker_taste_vec, cand_taste)
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

    weights_out = {"mode": mode_norm, "alpha": alpha, "beta": beta}
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
    "DATE_FLEXIBILITY_DAYS",
    "SUGGESTION_MODE_ML",
    "SUGGESTION_MODE_HARD_FILTER",
    "budgets_overlap_user",
    "cities_compatible_if_both_set",
    "countries_compatible_if_both_set",
    "candidate_excluded_for_incompatible_group",
    "fuse_final_score",
    "get_roommate_suggestions",
    "lifestyle_similarity_user_user",
    "lease_duration_compatible_if_both_set",
    "lease_types_compatible_if_both_set",
    "move_in_dates_compatible_if_both_set",
    "passes_all_hard_gates_user_user",
    "passes_same_gender_gate",
    "required_bedrooms_compatible_if_both_set",
    "seeker_compatible_with_group_hard",
    "states_compatible_if_both_set",
    "target_bathrooms_compatible_if_both_set",
    "target_deposit_compatible_if_both_set",
]
