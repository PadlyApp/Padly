"""Recommendation sessions, feedback, and passive engagement events."""

from __future__ import annotations

from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth import require_user_token
from app.dependencies.supabase import get_admin_client
from app.services.auth_helpers import resolve_current_user_id

from ._helpers import (
    build_session_response,
    get_recommendation_session,
    normalize_listing_ids,
    now_utc,
    recommendation_storage_missing,
    summarize_recommendation_events,
    update_session_aggregate_max,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.post("/recommendation-sessions")
async def create_recommendation_session(
    payload: RecommendationSessionCreate,
    token: str = Depends(require_user_token),
):
    """Create or refresh a recommendation session (idempotent per client_session_id)."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)
    now_iso = now_utc().isoformat()
    top_listing_ids = normalize_listing_ids(payload.top_listing_ids_shown)

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
            return build_session_response(supabase, session)

        created = (
            supabase.table("recommendation_sessions")
            .insert({
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
            })
            .execute()
        )
        if not created.data:
            raise HTTPException(status_code=500, detail="Recommendation session was not persisted")
        return build_session_response(supabase, created.data[0])
    except HTTPException:
        raise
    except Exception as e:
        if recommendation_storage_missing(e):
            raise HTTPException(status_code=503, detail="Recommendation feedback storage not configured. Run migration 20260406010000_recommendation_feedback_phase2.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to create recommendation session: {e}")


@router.patch("/recommendation-sessions/{session_id}")
async def update_recommendation_session(
    session_id: str,
    payload: RecommendationSessionUpdate,
    token: str = Depends(require_user_token),
):
    """Update counters and prompt lifecycle fields for a recommendation session."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)
    now_iso = now_utc().isoformat()

    try:
        session = get_recommendation_session(supabase, session_id=session_id, user_id=user_id)
        update_data: dict = {"updated_at": now_iso}

        if payload.recommendation_count_shown is not None:
            update_data["recommendation_count_shown"] = payload.recommendation_count_shown
        if payload.top_listing_ids_shown is not None:
            update_data["top_listing_ids_shown"] = normalize_listing_ids(payload.top_listing_ids_shown)
        if payload.detail_opens_count is not None:
            update_data["detail_opens_count"] = max(int(session.get("detail_opens_count") or 0), payload.detail_opens_count)
        if payload.saves_count is not None:
            update_data["saves_count"] = max(int(session.get("saves_count") or 0), payload.saves_count)
        if payload.likes_count is not None:
            update_data["likes_count"] = max(int(session.get("likes_count") or 0), payload.likes_count)
        if payload.surface_dwell_ms is not None:
            update_session_aggregate_max(update_data, "surface_dwell_ms", session.get("surface_dwell_ms"), payload.surface_dwell_ms)
        if payload.detail_dwell_ms is not None:
            update_session_aggregate_max(update_data, "detail_dwell_ms", session.get("detail_dwell_ms"), payload.detail_dwell_ms)
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
        if recommendation_storage_missing(e):
            raise HTTPException(status_code=503, detail="Recommendation feedback storage not configured. Run migration 20260406010000_recommendation_feedback_phase2.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to update recommendation session: {e}")


# ---------------------------------------------------------------------------
# Engagement events
# ---------------------------------------------------------------------------

@router.post("/recommendation-events")
async def create_recommendation_engagement_event(
    payload: RecommendationEngagementEventCreate,
    token: str = Depends(require_user_token),
):
    """Persist a passive engagement event tied to a recommendation session."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)
    now_iso = now_utc().isoformat()

    try:
        session = get_recommendation_session(supabase, session_id=payload.recommendation_session_id, user_id=user_id)

        existing = (
            supabase.table("recommendation_engagement_events")
            .select("event_id")
            .eq("actor_user_id", user_id)
            .eq("client_event_id", payload.client_event_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return {"status": "success", "duplicate_ignored": True, "event_id": existing.data[0]["event_id"]}

        created = (
            supabase.table("recommendation_engagement_events")
            .insert({
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
            })
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
            supabase.table("recommendation_sessions").update(session_update).eq("id", session["id"]).eq("actor_user_id", user_id).execute()

        return {"status": "success", "duplicate_ignored": False, "event_id": created.data[0]["event_id"]}
    except HTTPException:
        raise
    except Exception as e:
        if recommendation_storage_missing(e):
            raise HTTPException(status_code=503, detail="Recommendation passive metrics storage not configured. Run migration 20260406020000_recommendation_passive_metrics_phase3.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to store recommendation engagement event: {e}")


@router.get("/recommendation-sessions/{session_id}/passive-summary")
async def get_recommendation_passive_summary(
    session_id: str,
    token: str = Depends(require_user_token),
):
    """Return passive engagement metrics for one recommendation session."""
    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)

    try:
        session = get_recommendation_session(supabase, session_id=session_id, user_id=user_id)
        events_response = (
            supabase.table("recommendation_engagement_events")
            .select("event_type, position_in_feed, dwell_ms, listing_id, created_at")
            .eq("recommendation_session_id", session["id"])
            .eq("actor_user_id", user_id)
            .order("created_at", desc=False)
            .execute()
        )
        events = events_response.data or []
        summary = summarize_recommendation_events(events, session)
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
        if recommendation_storage_missing(e):
            raise HTTPException(status_code=503, detail="Recommendation passive metrics storage not configured. Run migration 20260406020000_recommendation_passive_metrics_phase3.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to fetch recommendation passive summary: {e}")


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

@router.post("/recommendation-feedback")
async def create_recommendation_feedback(
    payload: RecommendationFeedbackCreate,
    token: str = Depends(require_user_token),
):
    """Persist a single session-level usefulness response."""
    if payload.reason_label and payload.feedback_label != "not_useful":
        raise HTTPException(status_code=422, detail="A negative reason can only be attached to 'not_useful' feedback")

    supabase = get_admin_client()
    user_id = resolve_current_user_id(token)
    now_iso = now_utc().isoformat()

    try:
        session = get_recommendation_session(supabase, session_id=payload.recommendation_session_id, user_id=user_id)
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
            .insert({
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
            })
            .execute()
        )
        if not created.data:
            raise HTTPException(status_code=500, detail="Recommendation feedback was not persisted")

        supabase.table("recommendation_sessions").update({
            "feedback_submitted_at": now_iso,
            "ended_at": session.get("ended_at") or now_iso,
            "updated_at": now_iso,
        }).eq("id", session["id"]).eq("actor_user_id", user_id).execute()

        return {"status": "success", "duplicate_ignored": False, "data": created.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        if recommendation_storage_missing(e):
            raise HTTPException(status_code=503, detail="Recommendation feedback storage not configured. Run migration 20260406010000_recommendation_feedback_phase2.sql.")
        raise HTTPException(status_code=500, detail=f"Failed to store recommendation feedback: {e}")
