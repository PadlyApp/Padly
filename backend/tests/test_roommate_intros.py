"""Tests for Phase 4 roommate intro mutual opt-in and group funnel."""

from unittest.mock import MagicMock, patch

import pytest

from app.services import roommate_intros as intro_svc


def _row(a, b, status, **extra):
    r = {
        "id": "intro-1",
        "from_user_id": a,
        "to_user_id": b,
        "status": status,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "expires_at": None,
        "result_group_id": None,
    }
    r.update(extra)
    return r


def test_compute_pair_state_none():
    assert (
        intro_svc.compute_pair_state("u1", "u2", None, None) == intro_svc.PAIR_NONE
    )


def test_compute_pair_state_waiting_on_them():
    assert (
        intro_svc.compute_pair_state("u1", "u2", _row("u1", "u2", intro_svc.INTRO_PENDING), None)
        == intro_svc.PAIR_WAITING_ON_THEM
    )


def test_compute_pair_state_waiting_on_me():
    assert (
        intro_svc.compute_pair_state("u1", "u2", None, _row("u2", "u1", intro_svc.INTRO_PENDING))
        == intro_svc.PAIR_WAITING_ON_ME
    )


def test_compute_pair_state_mutual_both_pending():
    assert (
        intro_svc.compute_pair_state(
            "u1",
            "u2",
            _row("u1", "u2", intro_svc.INTRO_PENDING),
            _row("u2", "u1", intro_svc.INTRO_PENDING),
        )
        == intro_svc.PAIR_MUTUAL
    )


def test_compute_pair_state_mutual_with_result_group():
    assert (
        intro_svc.compute_pair_state(
            "u1",
            "u2",
            _row("u1", "u2", intro_svc.INTRO_ACCEPTED, result_group_id="g99"),
            None,
        )
        == intro_svc.PAIR_MUTUAL
    )


def test_funnel_payload_creator_vs_other():
    p1 = intro_svc._funnel_payload(
        group_id="g1", creator_user_id="alice", current_user_id="alice"
    )
    assert p1["next_step"] == intro_svc.NEXT_OPEN_GROUP
    assert p1["group_id"] == "g1"
    assert p1["join_path"] == "/api/roommate-groups/g1/join"

    p2 = intro_svc._funnel_payload(
        group_id="g1", creator_user_id="alice", current_user_id="bob"
    )
    assert p2["next_step"] == intro_svc.NEXT_JOIN_GROUP


@patch.object(intro_svc, "finalize_mutual_pair")
@patch.object(intro_svc, "fetch_intro_row")
def test_express_interest_first_direction_only(mock_fetch, mock_finalize):
    mock_fetch.side_effect = [
        None,
        None,
    ]
    ins = MagicMock()
    ins.data = [_row("alice", "bob", intro_svc.INTRO_PENDING)]
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value = ins

    out = intro_svc.express_interest(supabase, "alice", "bob")
    assert out["pair_state"] == intro_svc.PAIR_WAITING_ON_THEM
    assert out["funnel"] is None
    mock_finalize.assert_not_called()


@patch.object(intro_svc, "finalize_mutual_pair")
@patch.object(intro_svc, "fetch_intro_row")
def test_express_interest_triggers_finalize_and_funnel(mock_fetch, mock_finalize):
    mock_fetch.side_effect = [
        None,
        _row("bob", "alice", intro_svc.INTRO_PENDING),
    ]
    new_row = _row("alice", "bob", intro_svc.INTRO_PENDING)
    ins = MagicMock()
    ins.data = [new_row]
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value = ins

    mock_finalize.return_value = {
        "created": True,
        "group_id": "group-uuid",
        "creator_user_id": "alice",
        "other_user_id": "bob",
    }

    out = intro_svc.express_interest(supabase, "alice", "bob")
    assert out["pair_state"] == intro_svc.PAIR_MUTUAL
    assert out["mutual_just_formed"] is True
    assert out["funnel"]["group_id"] == "group-uuid"
    assert out["funnel"]["next_step"] == intro_svc.NEXT_OPEN_GROUP
    mock_finalize.assert_called_once_with(supabase, "alice", "bob")


@patch.object(intro_svc, "finalize_mutual_pair")
@patch.object(intro_svc, "fetch_intro_row")
def test_express_interest_creator_is_lexicographically_smaller_uuid(mock_fetch, mock_finalize):
    """Creator id is min(adam, zara); expresser adam is creator -> open_group."""
    zara, adam = "zzzz", "aaaa"
    mock_fetch.side_effect = [
        None,
        _row(zara, adam, intro_svc.INTRO_PENDING),
    ]
    ins = MagicMock()
    ins.data = [_row(adam, zara, intro_svc.INTRO_PENDING)]
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value = ins
    mock_finalize.return_value = {
        "created": True,
        "group_id": "g2",
        "creator_user_id": adam,
        "other_user_id": zara,
    }

    out = intro_svc.express_interest(supabase, adam, zara)
    assert out["funnel"]["next_step"] == intro_svc.NEXT_OPEN_GROUP


@patch.object(intro_svc, "finalize_mutual_pair")
@patch.object(intro_svc, "fetch_intro_row")
def test_express_interest_funnel_blocked(mock_fetch, mock_finalize):
    mock_fetch.side_effect = [
        None,
        _row("bob", "alice", intro_svc.INTRO_PENDING),
    ]
    ins = MagicMock()
    ins.data = [_row("alice", "bob", intro_svc.INTRO_PENDING)]
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value = ins
    mock_finalize.side_effect = intro_svc.IntroFunnelBlocked("blocked", group_id="gx")

    out = intro_svc.express_interest(supabase, "alice", "bob")
    assert out["pair_state"] == intro_svc.PAIR_MANUAL
    assert out["funnel"]["next_step"] == intro_svc.NEXT_MANUAL
    assert out["funnel"]["group_id"] == "gx"


def test_express_interest_rejects_self():
    with pytest.raises(ValueError, match="yourself"):
        intro_svc.express_interest(MagicMock(), "same", "same")


@patch.object(intro_svc, "express_interest")
def test_respond_accept_delegates(mock_express):
    mock_express.return_value = {"ok": True}
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "intro-1",
                "from_user_id": "alice",
                "to_user_id": "bob",
                "status": intro_svc.INTRO_PENDING,
            }
        ]
    )
    intro_svc.respond_accept(supabase, "intro-1", "bob")
    mock_express.assert_called_once_with(supabase, "bob", "alice")


def test_finalize_mutual_pair_idempotent_when_group_exists():
    supabase = MagicMock()
    a, b = "user-a", "user-b"
    r_ab = _row(a, b, intro_svc.INTRO_ACCEPTED, result_group_id="existing-g")
    r_ba = _row(b, a, intro_svc.INTRO_ACCEPTED, result_group_id="existing-g")

    with patch.object(intro_svc, "_pair_rows", return_value=(r_ab, r_ba)):
        out = intro_svc.finalize_mutual_pair(supabase, a, b)
    assert out["group_id"] == "existing-g"
    assert out["created"] is False
    supabase.table.assert_not_called()
