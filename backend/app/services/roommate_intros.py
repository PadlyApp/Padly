"""
Phase 4: directed roommate intro requests and mutual opt-in funnel into groups.

Mutual match = both directions have status pending. On second pending, creates a 2-person
roommate_groups row (creator = lexicographically smaller users.id), pending invite for the other,
after dissolving solo groups when safe.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.services.controlled_vocab import validate_city_name

logger = logging.getLogger(__name__)

INTRO_PENDING = "pending"
INTRO_ACCEPTED = "accepted"
INTRO_DECLINED = "declined"
INTRO_EXPIRED = "expired"

PAIR_NONE = "none"
PAIR_WAITING_ON_THEM = "waiting_on_them"
PAIR_WAITING_ON_ME = "waiting_on_me"
PAIR_MUTUAL = "mutual"
PAIR_DECLINED = "declined"
PAIR_EXPIRED = "expired"
PAIR_MANUAL = "manual"

NEXT_OPEN_GROUP = "open_group"
NEXT_JOIN_GROUP = "join_group"
NEXT_MANUAL = "manual"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utcnow().isoformat()


def _is_expired_row(row: Optional[Dict[str, Any]]) -> bool:
    if not row or not row.get("expires_at"):
        return False
    try:
        raw = row["expires_at"]
        if isinstance(raw, datetime):
            exp = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        else:
            s = str(raw).replace("Z", "+00:00")
            exp = datetime.fromisoformat(s)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
        return exp < _utcnow()
    except (TypeError, ValueError):
        return False


def _maybe_mark_expired(supabase: Any, row: Dict[str, Any]) -> Dict[str, Any]:
    if row.get("status") != INTRO_PENDING or not _is_expired_row(row):
        return row
    supabase.table("roommate_intro_requests").update(
        {"status": INTRO_EXPIRED, "updated_at": _iso_now()}
    ).eq("id", row["id"]).execute()
    out = dict(row)
    out["status"] = INTRO_EXPIRED
    return out


def fetch_intro_row(supabase: Any, from_user_id: str, to_user_id: str) -> Optional[Dict[str, Any]]:
    r = (
        supabase.table("roommate_intro_requests")
        .select("*")
        .eq("from_user_id", from_user_id)
        .eq("to_user_id", to_user_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    row = r.data[0]
    return _maybe_mark_expired(supabase, row)


def _pair_rows(
    supabase: Any, user_a: str, user_b: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Row from a->b and row from b->a."""
    return (
        fetch_intro_row(supabase, user_a, user_b),
        fetch_intro_row(supabase, user_b, user_a),
    )


def compute_pair_state(
    my_user_id: str, counterparty_user_id: str, row_me_to_them: Optional[Dict[str, Any]], row_them_to_me: Optional[Dict[str, Any]]
) -> str:
    """Derive pair_state for API (no DB writes)."""
    def eff(r: Optional[Dict[str, Any]]) -> Optional[str]:
        if not r:
            return None
        if r.get("status") == INTRO_PENDING and _is_expired_row(r):
            return INTRO_EXPIRED
        return r.get("status")

    s_out = eff(row_me_to_them)
    s_in = eff(row_them_to_me)

    if (s_out == INTRO_ACCEPTED or s_in == INTRO_ACCEPTED) and (
        (row_me_to_them and row_me_to_them.get("result_group_id"))
        or (row_them_to_me and row_them_to_me.get("result_group_id"))
    ):
        return PAIR_MUTUAL

    if s_out == INTRO_DECLINED or s_in == INTRO_DECLINED:
        return PAIR_DECLINED
    if s_out == INTRO_EXPIRED or s_in == INTRO_EXPIRED:
        return PAIR_EXPIRED

    if s_out == INTRO_PENDING and s_in == INTRO_PENDING:
        return PAIR_MUTUAL
    if s_out == INTRO_PENDING:
        return PAIR_WAITING_ON_THEM
    if s_in == INTRO_PENDING:
        return PAIR_WAITING_ON_ME
    return PAIR_NONE


def _funnel_payload(
    *,
    group_id: str,
    creator_user_id: str,
    current_user_id: str,
) -> Dict[str, Any]:
    if current_user_id == creator_user_id:
        return {
            "next_step": NEXT_OPEN_GROUP,
            "group_id": group_id,
            "join_path": f"/api/roommate-groups/{group_id}/join",
        }
    return {
        "next_step": NEXT_JOIN_GROUP,
        "group_id": group_id,
        "join_path": f"/api/roommate-groups/{group_id}/join",
    }


def _list_accepted_memberships(supabase: Any, user_id: str) -> List[Dict[str, Any]]:
    r = (
        supabase.table("group_members")
        .select("group_id, is_creator, roommate_groups(id, is_solo, group_name, creator_user_id)")
        .eq("user_id", user_id)
        .eq("status", "accepted")
        .execute()
    )
    return r.data or []


def _count_accepted_members(supabase: Any, group_id: str) -> int:
    r = (
        supabase.table("group_members")
        .select("user_id")
        .eq("group_id", group_id)
        .eq("status", "accepted")
        .execute()
    )
    return len(r.data or [])


def _dissolve_solo_group_for_user(supabase: Any, user_id: str) -> None:
    """Remove user's solo-only group (creator, single accepted member) if present."""
    memberships = _list_accepted_memberships(supabase, user_id)
    for m in memberships:
        g = m.get("roommate_groups") or {}
        gid = m.get("group_id")
        if not gid or not g.get("is_solo"):
            continue
        n = _count_accepted_members(supabase, gid)
        if n != 1:
            logger.warning("Solo group %s has %s accepted members; skipping auto-dissolve", gid, n)
            continue
        if not m.get("is_creator"):
            continue
        supabase.table("group_members").delete().eq("group_id", gid).execute()
        supabase.table("roommate_groups").delete().eq("id", gid).execute()


def _blocking_non_solo_group(supabase: Any, user_id: str) -> Optional[str]:
    """Return group_id if user is in a non-solo accepted group."""
    for m in _list_accepted_memberships(supabase, user_id):
        g = m.get("roommate_groups") or {}
        if g.get("is_solo"):
            continue
        return str(m.get("group_id"))
    return None


def _get_user_profile(supabase: Any, user_id: str) -> Dict[str, Any]:
    r = supabase.table("users").select("id, full_name").eq("id", user_id).limit(1).execute()
    return (r.data or [{}])[0] if r.data else {}


def _get_prefs(supabase: Any, user_id: str) -> Dict[str, Any]:
    r = supabase.table("personal_preferences").select("*").eq("user_id", user_id).limit(1).execute()
    return r.data[0] if r.data else {}


def _pick_city(supabase: Any, creator_id: str, other_id: str) -> str:
    for uid in (creator_id, other_id):
        p = _get_prefs(supabase, uid)
        c = (p.get("target_city") or "").strip()
        if c:
            try:
                return validate_city_name(c)
            except ValueError:
                continue
    return validate_city_name("San Francisco")


def _build_group_insert_payload(supabase: Any, creator_id: str, other_id: str) -> Dict[str, Any]:
    city = _pick_city(supabase, creator_id, other_id)
    u1 = _get_user_profile(supabase, creator_id)
    u2 = _get_user_profile(supabase, other_id)
    n1 = (u1.get("full_name") or "You").strip() or "You"
    n2 = (u2.get("full_name") or "Roommate").strip() or "Roommate"
    prefs = _get_prefs(supabase, creator_id)
    bmin = prefs.get("budget_min")
    bmax = prefs.get("budget_max")
    move_in = prefs.get("move_in_date")
    if isinstance(move_in, date):
        move_in = move_in.isoformat()

    payload: Dict[str, Any] = {
        "creator_user_id": creator_id,
        "group_name": f"{n1} & {n2}",
        "description": "Pair from mutual roommate intro",
        "target_city": city,
        "target_group_size": 2,
        "is_solo": False,
        "status": "active",
        "current_member_count": 1,
    }
    if bmin is not None:
        payload["budget_per_person_min"] = float(bmin)
        payload["budget_min"] = float(bmin)
    if bmax is not None:
        payload["budget_per_person_max"] = float(bmax)
        payload["budget_max"] = float(bmax)
    if move_in:
        payload["target_move_in_date"] = move_in
        payload["move_in_date"] = move_in

    for key, val in list(payload.items()):
        if isinstance(val, Decimal):
            payload[key] = float(val)
    return payload


def _existing_result_group(
    row_ab: Optional[Dict[str, Any]], row_ba: Optional[Dict[str, Any]]
) -> Optional[str]:
    for row in (row_ab, row_ba):
        if not row:
            continue
        if row.get("status") == INTRO_ACCEPTED and row.get("result_group_id"):
            return str(row["result_group_id"])
    return None


def finalize_mutual_pair(supabase: Any, user_a: str, user_b: str) -> Dict[str, Any]:
    """
    Idempotent: if intro rows already linked to a group, return that funnel.
    Requires reciprocal pending intros (after express upserts). Dissolves solo shells,
    then creates 2-person group + pending member for non-creator.
    """
    a, b = user_a, user_b
    if a > b:
        a, b = b, a
    creator_id, other_id = a, b

    row_ab, row_ba = _pair_rows(supabase, user_a, user_b)

    existing_gid = _existing_result_group(row_ab, row_ba)
    if existing_gid:
        return {
            "created": False,
            "group_id": existing_gid,
            "creator_user_id": creator_id,
            "other_user_id": other_id,
        }

    s_ab = row_ab.get("status") if row_ab else None
    s_ba = row_ba.get("status") if row_ba else None
    if s_ab != INTRO_PENDING or s_ba != INTRO_PENDING:
        raise ValueError("Mutual pending intros required to finalize pair funnel")

    for uid in (user_a, user_b):
        block_gid = _blocking_non_solo_group(supabase, uid)
        if block_gid:
            raise IntroFunnelBlocked(
                "One or both users already belong to a non-solo group. Leave or invite manually.",
                group_id=block_gid,
            )

    for uid in (user_a, user_b):
        _dissolve_solo_group_for_user(supabase, uid)

    group_payload = _build_group_insert_payload(supabase, creator_id, other_id)
    ins = supabase.table("roommate_groups").insert(group_payload).execute()
    if not ins.data:
        raise RuntimeError("Failed to create roommate group for intro funnel")
    group_id = ins.data[0]["id"]

    supabase.table("group_members").insert(
        {"group_id": group_id, "user_id": creator_id, "is_creator": True, "status": "accepted"}
    ).execute()
    supabase.table("group_members").insert(
        {"group_id": group_id, "user_id": other_id, "is_creator": False, "status": "pending"}
    ).execute()

    now = _iso_now()
    for fr, to in ((user_a, user_b), (user_b, user_a)):
        supabase.table("roommate_intro_requests").update(
            {
                "status": INTRO_ACCEPTED,
                "result_group_id": group_id,
                "updated_at": now,
            }
        ).eq("from_user_id", fr).eq("to_user_id", to).execute()

    return {
        "created": True,
        "group_id": group_id,
        "creator_user_id": creator_id,
        "other_user_id": other_id,
    }


class IntroFunnelBlocked(Exception):
    def __init__(self, message: str, group_id: Optional[str] = None):
        super().__init__(message)
        self.group_id = group_id


def express_interest(supabase: Any, from_user_id: str, to_user_id: str) -> Dict[str, Any]:
    if from_user_id == to_user_id:
        raise ValueError("Cannot express interest to yourself")

    existing = fetch_intro_row(supabase, from_user_id, to_user_id)
    now = _iso_now()

    if existing and existing.get("status") == INTRO_ACCEPTED and existing.get("result_group_id"):
        gid = str(existing["result_group_id"])
        a, b = from_user_id, to_user_id
        if a > b:
            a, b = b, a
        creator_id, other_id = a, b
        return {
            "intro": existing,
            "pair_state": PAIR_MUTUAL,
            "mutual_just_formed": False,
            "funnel": _funnel_payload(
                group_id=gid,
                creator_user_id=creator_id,
                current_user_id=from_user_id,
            ),
        }

    if existing:
        supabase.table("roommate_intro_requests").update(
            {"status": INTRO_PENDING, "updated_at": now}
        ).eq("id", existing["id"]).execute()
        intro = fetch_intro_row(supabase, from_user_id, to_user_id)
    else:
        ins = (
            supabase.table("roommate_intro_requests")
            .insert(
                {
                    "from_user_id": from_user_id,
                    "to_user_id": to_user_id,
                    "status": INTRO_PENDING,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            .execute()
        )
        intro = ins.data[0] if ins.data else None

    reciprocal = fetch_intro_row(supabase, to_user_id, from_user_id)
    row_me = intro
    row_them = reciprocal
    pair_state = compute_pair_state(from_user_id, to_user_id, row_me, row_them)

    out: Dict[str, Any] = {
        "intro": intro,
        "pair_state": pair_state,
        "mutual_just_formed": False,
        "funnel": None,
    }

    if pair_state == PAIR_MUTUAL and reciprocal and reciprocal.get("status") == INTRO_PENDING:
        try:
            funnel = finalize_mutual_pair(supabase, from_user_id, to_user_id)
        except IntroFunnelBlocked as e:
            out["pair_state"] = PAIR_MANUAL
            out["funnel"] = {
                "next_step": NEXT_MANUAL,
                "group_id": e.group_id,
                "join_path": None,
                "detail": str(e),
            }
            return out

        gid = funnel["group_id"]
        a, b = from_user_id, to_user_id
        if a > b:
            a, b = b, a
        creator_id = a
        out["mutual_just_formed"] = funnel.get("created", True)
        out["pair_state"] = PAIR_MUTUAL
        out["funnel"] = _funnel_payload(
            group_id=gid,
            creator_user_id=creator_id,
            current_user_id=from_user_id,
        )
    return out


def respond_decline(supabase: Any, intro_id: str, current_user_id: str) -> Dict[str, Any]:
    r = supabase.table("roommate_intro_requests").select("*").eq("id", intro_id).limit(1).execute()
    if not r.data:
        raise ValueError("Intro request not found")
    row = r.data[0]
    if row.get("to_user_id") != current_user_id:
        raise ValueError("You can only respond to intros addressed to you")
    if row.get("status") != INTRO_PENDING:
        raise ValueError("This intro is no longer pending")

    supabase.table("roommate_intro_requests").update(
        {"status": INTRO_DECLINED, "updated_at": _iso_now()}
    ).eq("id", intro_id).execute()

    updated = fetch_intro_row(supabase, row["from_user_id"], row["to_user_id"])
    other = row["from_user_id"]
    row_me = fetch_intro_row(supabase, current_user_id, other)
    row_them = fetch_intro_row(supabase, other, current_user_id)
    return {
        "intro": updated,
        "pair_state": compute_pair_state(current_user_id, other, row_me, row_them),
        "funnel": None,
    }


def respond_accept(supabase: Any, intro_id: str, current_user_id: str) -> Dict[str, Any]:
    """Accept incoming intro = express interest back (symmetric mutual path)."""
    r = supabase.table("roommate_intro_requests").select("*").eq("id", intro_id).limit(1).execute()
    if not r.data:
        raise ValueError("Intro request not found")
    row = r.data[0]
    if row.get("to_user_id") != current_user_id:
        raise ValueError("You can only respond to intros addressed to you")
    from_uid = row["from_user_id"]
    return express_interest(supabase, current_user_id, from_uid)


def build_inbox(supabase: Any, user_id: str) -> Dict[str, Any]:
    incoming = (
        supabase.table("roommate_intro_requests")
        .select("*")
        .eq("to_user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    outgoing = (
        supabase.table("roommate_intro_requests")
        .select("*")
        .eq("from_user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    def clean(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for row in rows or []:
            out.append(_maybe_mark_expired(supabase, row))
        return out

    return {
        "incoming": clean(incoming.data or []),
        "outgoing": clean(outgoing.data or []),
    }


def build_status_with(supabase: Any, my_user_id: str, counterparty_user_id: str) -> Dict[str, Any]:
    if my_user_id == counterparty_user_id:
        raise ValueError("Invalid counterparty")
    row_me = fetch_intro_row(supabase, my_user_id, counterparty_user_id)
    row_them = fetch_intro_row(supabase, counterparty_user_id, my_user_id)
    state = compute_pair_state(my_user_id, counterparty_user_id, row_me, row_them)
    funnel = None
    gid = _existing_result_group(row_me, row_them)
    if gid and state == PAIR_MUTUAL:
        a, b = my_user_id, counterparty_user_id
        if a > b:
            a, b = b, a
        funnel = _funnel_payload(group_id=gid, creator_user_id=a, current_user_id=my_user_id)
    elif (
        state == PAIR_MUTUAL
        and not gid
        and row_me
        and row_them
        and row_me.get("status") == INTRO_PENDING
        and row_them.get("status") == INTRO_PENDING
    ):
        for uid in (my_user_id, counterparty_user_id):
            block_gid = _blocking_non_solo_group(supabase, uid)
            if block_gid:
                state = PAIR_MANUAL
                funnel = {
                    "next_step": NEXT_MANUAL,
                    "group_id": block_gid,
                    "join_path": None,
                    "detail": (
                        "One or both users already belong to a non-solo group. "
                        "Leave or invite manually."
                    ),
                }
                break
    return {
        "counterparty_user_id": counterparty_user_id,
        "pair_state": state,
        "intro_outbound": row_me,
        "intro_inbound": row_them,
        "funnel": funnel,
    }
