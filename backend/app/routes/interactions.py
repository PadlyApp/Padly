"""
Interactions routes

Phase 1 endpoint(s) for swipe event capture from Discover.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dependencies.auth import require_user_token
from app.dependencies.supabase import get_admin_client
from app.services.behavior_features import (
    build_group_behavior_vector,
    build_user_behavior_vector,
    get_swipe_health_summary,
)

router = APIRouter(prefix="/api/interactions", tags=["interactions"])


class SwipeEventCreate(BaseModel):
    listing_id: str
    action: Literal["like", "pass", "super_like"]
    group_id_at_time: Optional[str] = None
    surface: str = Field(default="discover", min_length=1, max_length=100)
    session_id: str = Field(..., min_length=1, max_length=128)
    position_in_feed: int = Field(default=0, ge=0)
    algorithm_version: str = Field(..., min_length=1, max_length=100)
    model_version: Optional[str] = Field(default=None, max_length=100)
    city_filter: Optional[str] = Field(default=None, max_length=100)
    preference_snapshot_hash: Optional[str] = Field(default=None, max_length=128)
    latency_ms: Optional[int] = Field(default=None, ge=0)


class RecommendationSessionCreate(BaseModel):
    client_session_id: str = Field(..., min_length=1, max_length=128)
    surface: Literal["matches", "discover"] = "matches"
    recommendation_count_shown: int = Field(default=0, ge=0)
    top_listing_ids_shown: list[str] = Field(default_factory=list)
    algorithm_version: Optional[str] = Field(default=None, max_length=100)
    model_version: Optional[str] = Field(default=None, max_length=100)
    experiment_name: Optional[str] = Field(default=None, max_length=100)
    experiment_variant: Optional[str] = Field(default=None, max_length=100)


class RecommendationSessionUpdate(BaseModel):
    recommendation_count_shown: Optional[int] = Field(default=None, ge=0)
    top_listing_ids_shown: Optional[list[str]] = None
    detail_opens_count: Optional[int] = Field(default=None, ge=0)
    saves_count: Optional[int] = Field(default=None, ge=0)
    likes_count: Optional[int] = Field(default=None, ge=0)
    surface_dwell_ms: Optional[int] = Field(default=None, ge=0)
    detail_dwell_ms: Optional[int] = Field(default=None, ge=0)
    prompt_presented: bool = False
    prompt_dismissed: bool = False
    mark_ended: bool = False
    algorithm_version: Optional[str] = Field(default=None, max_length=100)
    model_version: Optional[str] = Field(default=None, max_length=100)
    experiment_name: Optional[str] = Field(default=None, max_length=100)
    experiment_variant: Optional[str] = Field(default=None, max_length=100)


class RecommendationFeedbackCreate(BaseModel):
    recommendation_session_id: str = Field(..., min_length=1, max_length=128)
    feedback_label: Literal["not_useful", "somewhat_useful", "very_useful"]
    reason_label: Optional[
        Literal["too_expensive", "wrong_location", "not_my_style", "too_few_good_options", "other"]
    ] = None


class RecommendationEngagementEventCreate(BaseModel):
    recommendation_session_id: str = Field(..., min_length=1, max_length=128)
    client_event_id: str = Field(..., min_length=1, max_length=128)
    surface: Literal["matches", "discover"] = "matches"
    event_type: Literal["detail_open", "detail_view", "save", "unsave"]
    listing_id: Optional[str] = Field(default=None, max_length=128)
    position_in_feed: Optional[int] = Field(default=None, ge=0)
    dwell_ms: Optional[int] = Field(default=None, ge=0)
    metadata: dict = Field(default_factory=dict)


class InterestedListingCreate(BaseModel):
    source: Optional[str] = Field(default=None, max_length=100)


def _resolve_current_user_id(token: str) -> str:
    """
    Resolve authenticated user to internal users.id UUID.
    """
    supabase = get_admin_client()

    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    auth_user_id = user_response.user.id

    # Preferred mapping: users.auth_id == auth user id.
    user_record = supabase.table("users").select("id").eq("auth_id", auth_user_id).limit(1).execute()
    if user_record.data:
        return user_record.data[0]["id"]

    # Fallback for legacy rows where users.id may equal auth user id.
    fallback_record = supabase.table("users").select("id").eq("id", auth_user_id).limit(1).execute()
    if fallback_record.data:
        return fallback_record.data[0]["id"]

    raise HTTPException(status_code=404, detail="User profile not found")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_listing_ids(listing_ids: Optional[list[str]]) -> list[str]:
    cleaned: list[str] = []
    for listing_id in listing_ids or []:
        value = str(listing_id).strip()
        if value:
            cleaned.append(value)
    return cleaned[:100]


def _recommendation_storage_missing(exc: Exception) -> bool:
    err = str(exc).lower()
    return (
        "recommendation_sessions" in err and "does not exist" in err
    ) or (
        "user_recommendation_feedback" in err and "does not exist" in err
    ) or (
        "recommendation_engagement_events" in err and "does not exist" in err
    )


def _interested_storage_missing(exc: Exception) -> bool:
    err = str(exc).lower()
    return "user_interested_listings" in err and "does not exist" in err


def _get_recommendation_session(supabase, session_id: str, user_id: str) -> dict:
    session_response = (
        supabase.table("recommendation_sessions")
        .select("*")
        .eq("id", session_id)
        .eq("actor_user_id", user_id)
        .limit(1)
        .execute()
    )
    if not session_response.data:
        raise HTTPException(status_code=404, detail="Recommendation session not found")
    return session_response.data[0]


def _recommendation_prompt_allowed(
    supabase,
    user_id: str,
    current_session_id: Optional[str] = None,
    surface: Optional[str] = None,
) -> bool:
    if surface in {"discover", "matches"}:
        return True

    cooldown_since = (_now_utc() - timedelta(days=7)).isoformat()
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


def _build_session_response(supabase, session_row: dict) -> dict:
    session_completed = bool(
        session_row.get("feedback_submitted_at")
        or session_row.get("prompt_dismissed_at")
        or session_row.get("prompt_presented_at")
    )
    return {
        "status": "success",
        "data": session_row,
        "prompt_allowed": (not session_completed)
        and _recommendation_prompt_allowed(
            supabase,
            user_id=session_row["actor_user_id"],
            current_session_id=session_row["id"],
            surface=session_row.get("surface"),
        ),
    }


def _update_session_aggregate_max(update_data: dict, field: str, current_value: Optional[int], next_value: int) -> None:
    update_data[field] = max(int(current_value or 0), int(next_value))


def _summarize_recommendation_events(events: list[dict], session_row: dict) -> dict:
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
        summary["avg_detail_view_dwell_ms"] = round(summary["detail_view_dwell_ms"] / detail_view_count, 2)

    summary["detail_open_rate"] = round(summary["detail_open_events"] / recommendation_count, 4)
    summary["save_rate"] = round(summary["save_events"] / recommendation_count, 4)
    return summary


def _require_group_membership(group_id: str, user_id: str) -> None:
    """
    Require that user is an accepted member of the target group.
    """
    supabase = get_admin_client()
    membership = (
        supabase.table("group_members")
        .select("group_id")
        .eq("group_id", group_id)
        .eq("user_id", user_id)
        .eq("status", "accepted")
        .limit(1)
        .execute()
    )
    if not membership.data:
        raise HTTPException(status_code=403, detail="You are not a member of this group")


@router.post("/swipes")
async def create_swipe_event(
    payload: SwipeEventCreate,
    token: str = Depends(require_user_token),
):
    """
    Persist a single swipe event from Discover.

    This endpoint is idempotent per:
    actor_user_id + listing_id + session_id + position_in_feed
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        existing = (
            supabase.table("swipe_interactions")
            .select("event_id")
            .eq("actor_user_id", user_id)
            .eq("listing_id", payload.listing_id)
            .eq("session_id", payload.session_id)
            .eq("position_in_feed", payload.position_in_feed)
            .limit(1)
            .execute()
        )
        if existing.data:
            return {
                "status": "success",
                "duplicate_ignored": True,
                "event_id": existing.data[0]["event_id"],
            }

        insert_data = {
            "actor_type": "user",
            "actor_user_id": user_id,
            "group_id_at_time": payload.group_id_at_time,
            "listing_id": payload.listing_id,
            "action": payload.action,
            "surface": payload.surface,
            "session_id": payload.session_id,
            "position_in_feed": payload.position_in_feed,
            "algorithm_version": payload.algorithm_version,
            "model_version": payload.model_version,
            "city_filter": payload.city_filter,
            "preference_snapshot_hash": payload.preference_snapshot_hash,
            "latency_ms": payload.latency_ms,
        }

        created = supabase.table("swipe_interactions").insert(insert_data).execute()
        if not created.data:
            raise HTTPException(status_code=500, detail="Swipe event was not persisted")

        return {
            "status": "success",
            "duplicate_ignored": False,
            "event_id": created.data[0]["event_id"],
        }
    except HTTPException:
        raise
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        if "duplicate key value violates unique constraint" in err:
            # Edge race between duplicate check and insert.
            existing = (
                supabase.table("swipe_interactions")
                .select("event_id")
                .eq("actor_user_id", user_id)
                .eq("listing_id", payload.listing_id)
                .eq("session_id", payload.session_id)
                .eq("position_in_feed", payload.position_in_feed)
                .limit(1)
                .execute()
            )
            return {
                "status": "success",
                "duplicate_ignored": True,
                "event_id": existing.data[0]["event_id"] if existing.data else None,
            }
        raise HTTPException(status_code=500, detail=f"Failed to store swipe event: {e}")


@router.post("/recommendation-sessions")
async def create_recommendation_session(
    payload: RecommendationSessionCreate,
    token: str = Depends(require_user_token),
):
    """
    Create or refresh a recommendation session for the current user.

    Sessions are idempotent per actor_user_id + client_session_id so refetches on the
    same page visit update the same row instead of creating duplicates.
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    now_iso = _now_utc().isoformat()
    top_listing_ids = _normalize_listing_ids(payload.top_listing_ids_shown)

    try:
        existing = (
            supabase.table("recommendation_sessions")
            .select("*")
            .eq("actor_user_id", user_id)
            .eq("client_session_id", payload.client_session_id)
            .limit(1)
            .execute()
        )

        if existing.data:
            session = existing.data[0]
            update_data = {
                "updated_at": now_iso,
                "surface": payload.surface,
                "recommendation_count_shown": payload.recommendation_count_shown,
                "top_listing_ids_shown": top_listing_ids,
                "algorithm_version": payload.algorithm_version,
                "model_version": payload.model_version,
                "experiment_name": payload.experiment_name,
                "experiment_variant": payload.experiment_variant,
            }
            updated = (
                supabase.table("recommendation_sessions")
                .update(update_data)
                .eq("id", session["id"])
                .execute()
            )
            session = updated.data[0] if updated.data else {**session, **update_data}
            return _build_session_response(supabase, session)

        created = (
            supabase.table("recommendation_sessions")
            .insert(
                {
                    "actor_user_id": user_id,
                    "client_session_id": payload.client_session_id,
                    "surface": payload.surface,
                    "started_at": now_iso,
                    "recommendation_count_shown": payload.recommendation_count_shown,
                    "top_listing_ids_shown": top_listing_ids,
                    "algorithm_version": payload.algorithm_version,
                    "model_version": payload.model_version,
                    "experiment_name": payload.experiment_name,
                    "experiment_variant": payload.experiment_variant,
                    "updated_at": now_iso,
                }
            )
            .execute()
        )
        if not created.data:
            raise HTTPException(status_code=500, detail="Recommendation session was not persisted")
        return _build_session_response(supabase, created.data[0])
    except HTTPException:
        raise
    except Exception as e:
        if _recommendation_storage_missing(e):
            raise HTTPException(
                status_code=503,
                detail="Recommendation feedback storage not configured. Run migration 20260406010000_recommendation_feedback_phase2.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to create recommendation session: {e}")


@router.patch("/recommendation-sessions/{session_id}")
async def update_recommendation_session(
    session_id: str,
    payload: RecommendationSessionUpdate,
    token: str = Depends(require_user_token),
):
    """
    Update counters and prompt lifecycle fields for an existing recommendation session.
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    now_iso = _now_utc().isoformat()

    try:
        session = _get_recommendation_session(supabase, session_id=session_id, user_id=user_id)
        update_data = {"updated_at": now_iso}

        if payload.recommendation_count_shown is not None:
            update_data["recommendation_count_shown"] = payload.recommendation_count_shown
        if payload.top_listing_ids_shown is not None:
            update_data["top_listing_ids_shown"] = _normalize_listing_ids(payload.top_listing_ids_shown)
        if payload.detail_opens_count is not None:
            update_data["detail_opens_count"] = max(
                int(session.get("detail_opens_count") or 0),
                payload.detail_opens_count,
            )
        if payload.saves_count is not None:
            update_data["saves_count"] = max(
                int(session.get("saves_count") or 0),
                payload.saves_count,
            )
        if payload.likes_count is not None:
            update_data["likes_count"] = max(
                int(session.get("likes_count") or 0),
                payload.likes_count,
            )
        if payload.surface_dwell_ms is not None:
            _update_session_aggregate_max(
                update_data,
                "surface_dwell_ms",
                session.get("surface_dwell_ms"),
                payload.surface_dwell_ms,
            )
        if payload.detail_dwell_ms is not None:
            _update_session_aggregate_max(
                update_data,
                "detail_dwell_ms",
                session.get("detail_dwell_ms"),
                payload.detail_dwell_ms,
            )
        if payload.prompt_presented and not session.get("prompt_presented_at"):
            update_data["prompt_presented_at"] = now_iso
        if payload.prompt_dismissed and not session.get("prompt_dismissed_at"):
            update_data["prompt_dismissed_at"] = now_iso
        if payload.mark_ended:
            update_data["ended_at"] = now_iso
        if payload.algorithm_version is not None:
            update_data["algorithm_version"] = payload.algorithm_version
        if payload.model_version is not None:
            update_data["model_version"] = payload.model_version
        if payload.experiment_name is not None:
            update_data["experiment_name"] = payload.experiment_name
        if payload.experiment_variant is not None:
            update_data["experiment_variant"] = payload.experiment_variant

        updated = (
            supabase.table("recommendation_sessions")
            .update(update_data)
            .eq("id", session_id)
            .eq("actor_user_id", user_id)
            .execute()
        )
        if not updated.data:
            raise HTTPException(status_code=500, detail="Recommendation session update failed")
        return {"status": "success", "data": updated.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        if _recommendation_storage_missing(e):
            raise HTTPException(
                status_code=503,
                detail="Recommendation feedback storage not configured. Run migration 20260406010000_recommendation_feedback_phase2.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to update recommendation session: {e}")


@router.post("/recommendation-events")
async def create_recommendation_engagement_event(
    payload: RecommendationEngagementEventCreate,
    token: str = Depends(require_user_token),
):
    """
    Persist a passive engagement event tied to a recommendation session.
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    now_iso = _now_utc().isoformat()

    try:
        session = _get_recommendation_session(
            supabase,
            session_id=payload.recommendation_session_id,
            user_id=user_id,
        )

        existing = (
            supabase.table("recommendation_engagement_events")
            .select("event_id")
            .eq("actor_user_id", user_id)
            .eq("client_event_id", payload.client_event_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return {
                "status": "success",
                "duplicate_ignored": True,
                "event_id": existing.data[0]["event_id"],
            }

        created = (
            supabase.table("recommendation_engagement_events")
            .insert(
                {
                    "actor_user_id": user_id,
                    "recommendation_session_id": session["id"],
                    "client_event_id": payload.client_event_id,
                    "surface": payload.surface,
                    "event_type": payload.event_type,
                    "listing_id": payload.listing_id,
                    "position_in_feed": payload.position_in_feed,
                    "dwell_ms": payload.dwell_ms,
                    "metadata": payload.metadata or {},
                    "created_at": now_iso,
                }
            )
            .execute()
        )
        if not created.data:
            raise HTTPException(status_code=500, detail="Recommendation engagement event was not persisted")

        session_update: dict = {"updated_at": now_iso}
        if payload.event_type == "detail_open":
            session_update["detail_opens_count"] = int(session.get("detail_opens_count") or 0) + 1
        elif payload.event_type == "save":
            session_update["saves_count"] = int(session.get("saves_count") or 0) + 1
        elif payload.event_type == "detail_view" and payload.dwell_ms is not None:
            session_update["detail_dwell_ms"] = int(session.get("detail_dwell_ms") or 0) + int(payload.dwell_ms)

        if len(session_update) > 1:
            supabase.table("recommendation_sessions").update(session_update).eq(
                "id", session["id"]
            ).eq("actor_user_id", user_id).execute()

        return {
            "status": "success",
            "duplicate_ignored": False,
            "event_id": created.data[0]["event_id"],
        }
    except HTTPException:
        raise
    except Exception as e:
        if _recommendation_storage_missing(e):
            raise HTTPException(
                status_code=503,
                detail="Recommendation passive metrics storage not configured. Run migration 20260406020000_recommendation_passive_metrics_phase3.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to store recommendation engagement event: {e}")


@router.get("/recommendation-sessions/{session_id}/passive-summary")
async def get_recommendation_passive_summary(
    session_id: str,
    token: str = Depends(require_user_token),
):
    """
    Return passive engagement metrics for one recommendation session.
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        session = _get_recommendation_session(supabase, session_id=session_id, user_id=user_id)
        events_response = (
            supabase.table("recommendation_engagement_events")
            .select("event_type, position_in_feed, dwell_ms, listing_id, created_at")
            .eq("recommendation_session_id", session["id"])
            .eq("actor_user_id", user_id)
            .order("created_at", desc=False)
            .execute()
        )
        events = events_response.data or []
        summary = _summarize_recommendation_events(events, session)
        return {
            "status": "success",
            "data": {
                "session_id": session["id"],
                "surface": session.get("surface"),
                "recommendation_count_shown": int(session.get("recommendation_count_shown") or 0),
                "detail_opens_count": int(session.get("detail_opens_count") or 0),
                "saves_count": int(session.get("saves_count") or 0),
                "likes_count": int(session.get("likes_count") or 0),
                **summary,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        if _recommendation_storage_missing(e):
            raise HTTPException(
                status_code=503,
                detail="Recommendation passive metrics storage not configured. Run migration 20260406020000_recommendation_passive_metrics_phase3.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to fetch recommendation passive summary: {e}")


@router.post("/recommendation-feedback")
async def create_recommendation_feedback(
    payload: RecommendationFeedbackCreate,
    token: str = Depends(require_user_token),
):
    """
    Persist a single session-level usefulness response for the current user.
    """
    if payload.reason_label and payload.feedback_label != "not_useful":
        raise HTTPException(status_code=422, detail="A negative reason can only be attached to 'not_useful' feedback")

    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    now_iso = _now_utc().isoformat()

    try:
        session = _get_recommendation_session(
            supabase,
            session_id=payload.recommendation_session_id,
            user_id=user_id,
        )
        swipe_count = None
        if session.get("client_session_id"):
            try:
                swipe_count = (
                    supabase.table("swipe_interactions")
                    .select("event_id", count="exact")
                    .eq("actor_user_id", user_id)
                    .eq("session_id", session["client_session_id"])
                    .execute()
                    .count
                )
            except Exception:
                swipe_count = None
        existing = (
            supabase.table("user_recommendation_feedback")
            .select("*")
            .eq("recommendation_session_id", session["id"])
            .limit(1)
            .execute()
        )
        if existing.data:
            return {"status": "success", "duplicate_ignored": True, "data": existing.data[0]}

        created = (
            supabase.table("user_recommendation_feedback")
            .insert(
                {
                    "actor_user_id": user_id,
                    "recommendation_session_id": session["id"],
                    "surface": session["surface"],
                    "feedback_label": payload.feedback_label,
                    "reason_label": payload.reason_label,
                    "submitted_at": now_iso,
                    "algorithm_version": session.get("algorithm_version"),
                    "model_version": session.get("model_version"),
                    "experiment_name": session.get("experiment_name"),
                    "experiment_variant": session.get("experiment_variant"),
                    "swipes_in_session": int(swipe_count) if swipe_count is not None else None,
                    "likes_in_session": int(session.get("likes_count") or 0),
                    "saves_in_session": int(session.get("saves_count") or 0),
                    "detail_opens_in_session": int(session.get("detail_opens_count") or 0),
                    "recommendation_count_shown": int(session.get("recommendation_count_shown") or 0),
                    "top_listing_ids_shown": session.get("top_listing_ids_shown") or [],
                }
            )
            .execute()
        )
        if not created.data:
            raise HTTPException(status_code=500, detail="Recommendation feedback was not persisted")

        supabase.table("recommendation_sessions").update(
            {
                "feedback_submitted_at": now_iso,
                "ended_at": session.get("ended_at") or now_iso,
                "updated_at": now_iso,
            }
        ).eq("id", session["id"]).eq("actor_user_id", user_id).execute()

        return {"status": "success", "duplicate_ignored": False, "data": created.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        if _recommendation_storage_missing(e):
            raise HTTPException(
                status_code=503,
                detail="Recommendation feedback storage not configured. Run migration 20260406010000_recommendation_feedback_phase2.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to store recommendation feedback: {e}")


@router.get("/swipes/me")
async def get_my_swipe_events(
    limit: int = Query(50, ge=1, le=500),
    token: str = Depends(require_user_token),
):
    """
    Return recent swipe events for the current user (debug/inspection endpoint).
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        response = (
            supabase.table("swipe_interactions")
            .select("*")
            .eq("actor_user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        events = response.data or []
        return {"status": "success", "count": len(events), "data": events}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to fetch swipe events: {e}")


@router.get("/behavior/me")
async def get_my_behavior_vector(
    days: int = Query(180, ge=7, le=365),
    max_events: int = Query(2000, ge=100, le=10000),
    token: str = Depends(require_user_token),
):
    """
    Return Phase 2A behavior vector for the authenticated user.
    """
    user_id = _resolve_current_user_id(token)
    try:
        vector = build_user_behavior_vector(user_id=user_id, days=days, max_events=max_events)
        return {"status": "success", "data": vector}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to build user behavior vector: {e}")


@router.get("/behavior/groups/{group_id}")
async def get_group_behavior(
    group_id: str,
    days: int = Query(180, ge=7, le=365),
    max_events_per_user: int = Query(2000, ge=100, le=10000),
    token: str = Depends(require_user_token),
):
    """
    Return Phase 2A behavior vector for a group.
    Access is limited to accepted group members.
    """
    user_id = _resolve_current_user_id(token)
    _require_group_membership(group_id=group_id, user_id=user_id)
    try:
        vector = build_group_behavior_vector(
            group_id=group_id,
            days=days,
            max_events_per_user=max_events_per_user,
        )
        return {"status": "success", "data": vector}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to build group behavior vector: {e}")


@router.get("/swipes/groups/{group_id}/liked")
async def get_group_liked_listings(
    group_id: str,
    limit: int = Query(100, ge=1, le=500),
    action: Optional[str] = Query(None, description="Filter by action: 'like', 'group_save', or omit for both"),
    token: str = Depends(require_user_token),
):
    """
    Return listings interacted with by any accepted member of the group.
    Pass ?action=group_save to see only group-saved listings.
    Pass ?action=like to see only individually liked listings.
    Omit action to see both.
    Each item includes listing data plus a list of member names who saved/liked it.
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    _require_group_membership(group_id=group_id, user_id=user_id)

    try:
        # Get all accepted member user IDs
        members_resp = (
            supabase.table("group_members")
            .select("user_id")
            .eq("group_id", group_id)
            .eq("status", "accepted")
            .execute()
        )
        members = members_resp.data or []
        if not members:
            return {"status": "success", "data": []}

        member_ids = [m["user_id"] for m in members]

        # Fetch user details separately
        users_resp = (
            supabase.table("users")
            .select("id, full_name, email")
            .in_("id", member_ids)
            .execute()
        )
        member_map = {
            u["id"]: u.get("full_name") or u.get("email", "Member")
            for u in (users_resp.data or [])
        }

        # Determine which actions to fetch based on the optional filter param.
        if action == "group_save":
            actions_to_fetch = ["group_save"]
        elif action == "like":
            actions_to_fetch = ["like"]
        else:
            actions_to_fetch = ["like", "group_save"]

        swipes_resp = (
            supabase.table("swipe_interactions")
            .select("listing_id, actor_user_id, action, group_id_at_time")
            .in_("actor_user_id", member_ids)
            .in_("action", actions_to_fetch)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        raw_swipes = swipes_resp.data or []
        # group_save rows must belong to this specific group; likes are group-agnostic.
        swipes = []
        for s in raw_swipes:
            if s.get("action") == "like":
                swipes.append(s)
            elif s.get("action") == "group_save" and s.get("group_id_at_time") == group_id:
                swipes.append(s)
        if not swipes:
            return {"status": "success", "data": []}

        # Build mapping: listing_id -> list of member names who liked it
        liked_by: dict = {}
        for s in swipes:
            lid = s["listing_id"]
            name = member_map.get(s["actor_user_id"], "Member")
            liked_by.setdefault(lid, [])
            if name not in liked_by[lid]:
                liked_by[lid].append(name)

        unique_listing_ids = list(liked_by.keys())

        # Fetch listing details
        listings_resp = (
            supabase.table("listings")
            .select("*")
            .in_("id", unique_listing_ids)
            .execute()
        )
        listings = listings_resp.data or []
        listing_map = {str(l["id"]): l for l in listings}

        result = []
        for lid in unique_listing_ids:
            listing = listing_map.get(str(lid))
            if listing:
                result.append({**listing, "liked_by": liked_by[lid]})

        return {"status": "success", "data": result}

    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to fetch group liked listings: {e}")


@router.post("/swipes/groups/{group_id}/save/{listing_id}")
async def save_listing_to_group(
    group_id: str,
    listing_id: str,
    token: str = Depends(require_user_token),
):
    """Save a listing to the group (star/bookmark action from Discover)."""
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    _require_group_membership(group_id=group_id, user_id=user_id)

    try:
        # Delete any existing group_save for this user+listing+group, then insert fresh
        supabase.table("swipe_interactions").delete().eq(
            "actor_user_id", user_id
        ).eq("listing_id", listing_id).eq("action", "group_save").eq(
            "group_id_at_time", group_id
        ).execute()

        supabase.table("swipe_interactions").insert({
            "actor_user_id": user_id,
            "listing_id": listing_id,
            "action": "group_save",
            "group_id_at_time": group_id,
            "surface": "matches",
            "session_id": f"group-save-{user_id}-{group_id}-{listing_id}",
            "algorithm_version": "group-save-v1",
            "position_in_feed": 0,
        }).execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save listing: {e}")


@router.delete("/swipes/groups/{group_id}/save/{listing_id}")
async def unsave_listing_from_group(
    group_id: str,
    listing_id: str,
    token: str = Depends(require_user_token),
):
    """Remove a group-saved listing."""
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    _require_group_membership(group_id=group_id, user_id=user_id)

    try:
        supabase.table("swipe_interactions").delete().eq(
            "actor_user_id", user_id
        ).eq("listing_id", listing_id).eq("action", "group_save").execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unsave listing: {e}")


@router.get("/swipes/groups/{group_id}/saved")
async def get_my_saved_listings_for_group(
    group_id: str,
    token: str = Depends(require_user_token),
):
    """Return listing IDs the current user has starred for this group."""
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)
    _require_group_membership(group_id=group_id, user_id=user_id)

    try:
        resp = (
            supabase.table("swipe_interactions")
            .select("listing_id")
            .eq("actor_user_id", user_id)
            .eq("group_id_at_time", group_id)
            .eq("action", "group_save")
            .execute()
        )
        ids = [r["listing_id"] for r in (resp.data or [])]
        return {"status": "success", "saved_listing_ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch saved listings: {e}")


@router.get("/interested-listings")
async def get_my_interested_listings(token: str = Depends(require_user_token)):
    """Return the current user's interested listings with listing payloads."""
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        rows_resp = (
            supabase.table("user_interested_listings")
            .select("listing_id, source, created_at")
            .eq("actor_user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = rows_resp.data or []
        if not rows:
            return {"status": "success", "data": []}

        listing_ids = []
        seen = set()
        for row in rows:
            listing_id = str(row.get("listing_id") or "").strip()
            if listing_id and listing_id not in seen:
                seen.add(listing_id)
                listing_ids.append(listing_id)

        listings_resp = (
            supabase.table("listings")
            .select("*")
            .in_("id", listing_ids)
            .execute()
        )
        listing_map = {str(item["id"]): item for item in (listings_resp.data or [])}

        data = []
        for row in rows:
            listing_id = str(row.get("listing_id") or "")
            listing = listing_map.get(listing_id)
            if listing:
                data.append(
                    {
                        "interested_at": row.get("created_at"),
                        "interest_source": row.get("source"),
                        **listing,
                    }
                )

        return {"status": "success", "data": data}
    except Exception as e:
        if _interested_storage_missing(e):
            raise HTTPException(
                status_code=503,
                detail="Interested listing storage not configured. Run migration 20260406030000_user_interested_listings.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to fetch interested listings: {e}")


@router.get("/interested-listings/ids")
async def get_my_interested_listing_ids(token: str = Depends(require_user_token)):
    """Return listing IDs the current user marked as interested."""
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        rows_resp = (
            supabase.table("user_interested_listings")
            .select("listing_id")
            .eq("actor_user_id", user_id)
            .execute()
        )
        ids = [row["listing_id"] for row in (rows_resp.data or []) if row.get("listing_id")]
        return {"status": "success", "interested_listing_ids": ids}
    except Exception as e:
        if _interested_storage_missing(e):
            raise HTTPException(
                status_code=503,
                detail="Interested listing storage not configured. Run migration 20260406030000_user_interested_listings.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to fetch interested listing ids: {e}")


@router.post("/interested-listings/{listing_id}")
async def mark_listing_interested(
    listing_id: str,
    payload: InterestedListingCreate,
    token: str = Depends(require_user_token),
):
    """Mark a listing as personally interesting for the current user."""
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        existing_listing = (
            supabase.table("listings")
            .select("id")
            .eq("id", listing_id)
            .limit(1)
            .execute()
        )
        if not existing_listing.data:
            raise HTTPException(status_code=404, detail="Listing not found")

        existing_interested = (
            supabase.table("user_interested_listings")
            .select("id")
            .eq("actor_user_id", user_id)
            .eq("listing_id", listing_id)
            .limit(1)
            .execute()
        )
        if existing_interested.data:
            return {"status": "success", "listing_id": listing_id, "already_interested": True}

        supabase.table("user_interested_listings").insert(
            {
                "actor_user_id": user_id,
                "listing_id": listing_id,
                "source": payload.source,
            }
        ).execute()

        return {"status": "success", "listing_id": listing_id, "already_interested": False}
    except HTTPException:
        raise
    except Exception as e:
        if _interested_storage_missing(e):
            raise HTTPException(
                status_code=503,
                detail="Interested listing storage not configured. Run migration 20260406030000_user_interested_listings.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to mark listing interested: {e}")


@router.delete("/interested-listings/{listing_id}")
async def unmark_listing_interested(
    listing_id: str,
    token: str = Depends(require_user_token),
):
    """Remove a listing from the current user's interested list."""
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        supabase.table("user_interested_listings").delete().eq(
            "actor_user_id", user_id
        ).eq("listing_id", listing_id).execute()
        return {"status": "success", "listing_id": listing_id}
    except Exception as e:
        if _interested_storage_missing(e):
            raise HTTPException(
                status_code=503,
                detail="Interested listing storage not configured. Run migration 20260406030000_user_interested_listings.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to unmark listing interested: {e}")


# ---------------------------------------------------------------------------
# Data logging endpoints (analytics / AI training)
# All four are best-effort: failures are returned as 500 but callers should
# fire-and-forget these. They write to new tables and never touch existing ones.
# ---------------------------------------------------------------------------

class SwipeContextEventCreate(BaseModel):
    listing_id: str
    action: Literal["like", "pass", "super_like", "group_save"]
    session_id: str = Field(..., min_length=1, max_length=128)
    active_filters_snapshot: Optional[Dict[str, Any]] = None
    device_context: Optional[Dict[str, Any]] = None


class ListingViewEventCreate(BaseModel):
    listing_id: str
    surface: Literal["discover_card", "listing_detail", "matches_card"]
    session_id: str = Field(..., min_length=1, max_length=128)
    view_duration_ms: Optional[int] = Field(default=None, ge=0)
    expanded: bool = False
    photos_viewed_count: int = Field(default=0, ge=0)


class PageViewEventCreate(BaseModel):
    page: Literal[
        "discover", "matches", "listing_detail", "preferences",
        "account", "groups", "roommates", "onboarding"
    ]
    session_id: str = Field(..., min_length=1, max_length=128)
    duration_ms: Optional[int] = Field(default=None, ge=0)
    referrer_page: Optional[str] = Field(default=None, max_length=100)


class SearchQueryEventCreate(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    filter_snapshot: Dict[str, Any]
    results_returned: int = Field(default=0, ge=0)
    offset: int = Field(default=0, ge=0)


@router.post("/swipe-context")
async def create_swipe_context_event(
    payload: SwipeContextEventCreate,
    token: str = Depends(require_user_token),
):
    """
    Persist filter + device context alongside a swipe.

    Companion to POST /swipes — writes to swipe_context_events without
    touching the existing swipe_interactions table. Join the two tables on
    (actor_user_id, listing_id, session_id) to get the full swipe picture.
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        insert_data = {
            "actor_user_id": user_id,
            "listing_id": payload.listing_id,
            "session_id": payload.session_id,
            "action": payload.action,
            "active_filters_snapshot": payload.active_filters_snapshot,
            "device_context": payload.device_context,
        }
        created = supabase.table("swipe_context_events").insert(insert_data).execute()
        if not created.data:
            raise HTTPException(status_code=500, detail="Swipe context event was not persisted")
        return {"status": "success", "event_id": created.data[0]["event_id"]}
    except HTTPException:
        raise
    except Exception as e:
        err = str(e).lower()
        if "swipe_context_events" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="swipe_context_events table not found. Run migration 012.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to store swipe context: {e}")


@router.post("/listing-views")
async def create_listing_view_event(
    payload: ListingViewEventCreate,
    token: str = Depends(require_user_token),
):
    """
    Persist a listing view duration event.

    Fire on card mount (discover stack, matches grid) and on listing detail
    page unmount. Best-effort — callers should not block on this response.
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        insert_data = {
            "user_id": user_id,
            "listing_id": payload.listing_id,
            "surface": payload.surface,
            "session_id": payload.session_id,
            "view_duration_ms": payload.view_duration_ms,
            "expanded": payload.expanded,
            "photos_viewed_count": payload.photos_viewed_count,
        }
        created = supabase.table("listing_view_events").insert(insert_data).execute()
        if not created.data:
            raise HTTPException(status_code=500, detail="Listing view event was not persisted")
        return {"status": "success", "event_id": created.data[0]["event_id"]}
    except HTTPException:
        raise
    except Exception as e:
        err = str(e).lower()
        if "listing_view_events" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="listing_view_events table not found. Run migration 014.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to store listing view event: {e}")


@router.post("/page-views")
async def create_page_view_event(
    payload: PageViewEventCreate,
    token: str = Depends(require_user_token),
):
    """
    Persist a page view event for funnel analytics.

    Fire on page component mount; send duration_ms on unmount via keepalive fetch.
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        insert_data = {
            "user_id": user_id,
            "page": payload.page,
            "session_id": payload.session_id,
            "duration_ms": payload.duration_ms,
            "referrer_page": payload.referrer_page,
        }
        created = supabase.table("page_view_events").insert(insert_data).execute()
        if not created.data:
            raise HTTPException(status_code=500, detail="Page view event was not persisted")
        return {"status": "success", "event_id": created.data[0]["event_id"]}
    except HTTPException:
        raise
    except Exception as e:
        err = str(e).lower()
        if "page_view_events" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="page_view_events table not found. Run migration 016.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to store page view event: {e}")


@router.post("/search-queries")
async def create_search_query_event(
    payload: SearchQueryEventCreate,
    token: str = Depends(require_user_token),
):
    """
    Persist a search/filter event for demand intelligence.

    Fire each time the discover feed calls /api/recommendations, capturing
    the full filter state and how many results were returned.
    """
    supabase = get_admin_client()
    user_id = _resolve_current_user_id(token)

    try:
        insert_data = {
            "user_id": user_id,
            "session_id": payload.session_id,
            "filter_snapshot": payload.filter_snapshot,
            "results_returned": payload.results_returned,
            "offset": payload.offset,
        }
        created = supabase.table("search_query_events").insert(insert_data).execute()
        if not created.data:
            raise HTTPException(status_code=500, detail="Search query event was not persisted")
        return {"status": "success", "event_id": created.data[0]["event_id"]}
    except HTTPException:
        raise
    except Exception as e:
        err = str(e).lower()
        if "search_query_events" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="search_query_events table not found. Run migration 018.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to store search query event: {e}")


@router.get("/behavior/health")
async def get_behavior_health(
    days: int = Query(7, ge=1, le=90),
    max_events: int = Query(10000, ge=500, le=100000),
    token: str = Depends(require_user_token),
):
    """
    Return event quality and freshness summary for swipe interactions.
    """
    _ = _resolve_current_user_id(token)
    try:
        summary = get_swipe_health_summary(days=days, max_events=max_events)
        return {"status": "success", "data": summary}
    except Exception as e:
        err = str(e).lower()
        if "swipe_interactions" in err and "does not exist" in err:
            raise HTTPException(
                status_code=503,
                detail="Swipe storage not configured. Run migration 004_swipe_interactions.sql.",
            )
        raise HTTPException(status_code=500, detail=f"Failed to build behavior health summary: {e}")
