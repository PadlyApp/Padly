"""Shared helpers for the interactions sub-package."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_listing_ids(listing_ids: Optional[list[str]]) -> list[str]:
    cleaned: list[str] = []
    for listing_id in listing_ids or []:
        value = str(listing_id).strip()
        if value:
            cleaned.append(value)
    return cleaned[:100]


def recommendation_storage_missing(exc: Exception) -> bool:
    err = str(exc).lower()
    return (
        "recommendation_sessions" in err and "does not exist" in err
    ) or (
        "user_recommendation_feedback" in err and "does not exist" in err
    ) or (
        "recommendation_engagement_events" in err and "does not exist" in err
    )


def interested_storage_missing(exc: Exception) -> bool:
    err = str(exc).lower()
    return "user_interested_listings" in err and "does not exist" in err


def get_recommendation_session(supabase, session_id: str, user_id: str) -> dict:
    session_response = (
        supabase.table("recommendation_sessions")
        .select("*")
        .eq("id", session_id)
        .eq("actor_user_id", user_id)
        .limit(1)
        .execute()
    )
    if not session_response.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Recommendation session not found")
    return session_response.data[0]


def recommendation_prompt_allowed(
    supabase,
    user_id: str,
    current_session_id: Optional[str] = None,
    surface: Optional[str] = None,
) -> bool:
    if surface in {"discover", "matches"}:
        return True

    cooldown_since = (now_utc() - timedelta(days=7)).isoformat()
    recent = (
        supabase.table("recommendation_sessions")
        .select("id, prompt_presented_at, prompt_dismissed_at, feedback_submitted_at")
        .eq("actor_user_id", user_id)
        .gte("started_at", cooldown_since)
        .order("started_at", desc=True)
        .limit(50)
        .execute()
    )

    for row in recent.data or []:
        if current_session_id and row.get("id") == current_session_id:
            continue
        if row.get("prompt_presented_at") or row.get("prompt_dismissed_at") or row.get("feedback_submitted_at"):
            return False
    return True


def build_session_response(supabase, session_row: dict) -> dict:
    session_completed = bool(
        session_row.get("feedback_submitted_at")
        or session_row.get("prompt_dismissed_at")
        or session_row.get("prompt_presented_at")
    )
    return {
        "status": "success",
        "data": session_row,
        "prompt_allowed": (not session_completed)
        and recommendation_prompt_allowed(
            supabase,
            user_id=session_row["actor_user_id"],
            current_session_id=session_row["id"],
            surface=session_row.get("surface"),
        ),
    }


def update_session_aggregate_max(
    update_data: dict, field: str, current_value: Optional[int], next_value: int
) -> None:
    update_data[field] = max(int(current_value or 0), int(next_value))


def summarize_recommendation_events(events: list[dict], session_row: dict) -> dict:
    summary = {
        "detail_open_events": 0,
        "save_events": 0,
        "unsave_events": 0,
        "detail_view_events": 0,
        "detail_view_dwell_ms": 0,
        "avg_detail_view_dwell_ms": 0,
        "surface_dwell_ms": int(session_row.get("surface_dwell_ms") or 0),
        "detail_dwell_ms": int(session_row.get("detail_dwell_ms") or 0),
        "detail_open_rate": 0.0,
        "save_rate": 0.0,
        "detail_opens_by_position": {},
        "saves_by_position": {},
    }

    detail_view_count = 0
    recommendation_count = max(int(session_row.get("recommendation_count_shown") or 0), 1)

    for event in events:
        event_type = event.get("event_type")
        position = event.get("position_in_feed")
        position_key = str(position) if position is not None else None

        if event_type == "detail_open":
            summary["detail_open_events"] += 1
            if position_key is not None:
                summary["detail_opens_by_position"][position_key] = (
                    summary["detail_opens_by_position"].get(position_key, 0) + 1
                )
        elif event_type == "save":
            summary["save_events"] += 1
            if position_key is not None:
                summary["saves_by_position"][position_key] = (
                    summary["saves_by_position"].get(position_key, 0) + 1
                )
        elif event_type == "unsave":
            summary["unsave_events"] += 1
        elif event_type == "detail_view":
            detail_view_count += 1
            summary["detail_view_events"] += 1
            summary["detail_view_dwell_ms"] += int(event.get("dwell_ms") or 0)

    if detail_view_count > 0:
        summary["avg_detail_view_dwell_ms"] = round(
            summary["detail_view_dwell_ms"] / detail_view_count, 2
        )

    summary["detail_open_rate"] = round(summary["detail_open_events"] / recommendation_count, 4)
    summary["save_rate"] = round(summary["save_events"] / recommendation_count, 4)
    return summary
