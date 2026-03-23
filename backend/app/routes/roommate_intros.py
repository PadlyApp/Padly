"""
Phase 4: mutual roommate opt-in intros and funnel into roommate groups.
"""

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth import require_user_token
from app.dependencies.supabase import get_admin_client
from app.services import roommate_intros as intro_svc

router = APIRouter(prefix="/api/roommate-intros", tags=["roommate-intros"])


def _resolve_profile_user_id(token: str) -> str:
    supabase = get_admin_client()
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    auth_user_id = user_response.user.id
    user_record = supabase.table("users").select("id").eq("auth_id", auth_user_id).execute()
    if not user_record.data:
        raise HTTPException(status_code=404, detail="User profile not found")
    return user_record.data[0]["id"]


def _envelope(
    *,
    intro: Optional[Dict[str, Any]],
    pair_state: str,
    mutual_just_formed: Optional[bool] = None,
    funnel: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    intro_status = intro.get("status") if intro else None
    out: Dict[str, Any] = {
        "status": "success",
        "intro_status": intro_status,
        "pair_state": pair_state,
        "funnel": funnel,
    }
    if mutual_just_formed is not None:
        out["mutual_just_formed"] = mutual_just_formed
    if intro is not None:
        out["intro"] = intro
    if extra:
        out.update(extra)
    return out


class ExpressInterestBody(BaseModel):
    to_user_id: str = Field(..., description="Target user's users.id (profile id)")


@router.post("/express-interest", response_model=dict)
async def express_interest(body: ExpressInterestBody, token: str = Depends(require_user_token)):
    supabase = get_admin_client()
    me = _resolve_profile_user_id(token)
    try:
        result = intro_svc.express_interest(supabase, me, body.to_user_id.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _envelope(
        intro=result.get("intro"),
        pair_state=result["pair_state"],
        mutual_just_formed=result.get("mutual_just_formed"),
        funnel=result.get("funnel"),
    )


class RespondBody(BaseModel):
    action: Literal["accept", "decline"]


@router.post("/{intro_id}/respond", response_model=dict)
async def respond_to_intro(
    intro_id: str,
    body: RespondBody,
    token: str = Depends(require_user_token),
):
    supabase = get_admin_client()
    me = _resolve_profile_user_id(token)
    try:
        if body.action == "accept":
            result = intro_svc.respond_accept(supabase, intro_id, me)
        else:
            result = intro_svc.respond_decline(supabase, intro_id, me)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return _envelope(
        intro=result.get("intro"),
        pair_state=result["pair_state"],
        funnel=result.get("funnel"),
        mutual_just_formed=result.get("mutual_just_formed"),
    )


@router.get("/inbox", response_model=dict)
async def intro_inbox(token: str = Depends(require_user_token)):
    supabase = get_admin_client()
    me = _resolve_profile_user_id(token)
    data = intro_svc.build_inbox(supabase, me)
    return {"status": "success", **data}


@router.get("/status-with/{user_id}", response_model=dict)
async def status_with_user(user_id: str, token: str = Depends(require_user_token)):
    supabase = get_admin_client()
    me = _resolve_profile_user_id(token)
    try:
        data = intro_svc.build_status_with(supabase, me, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "success", **data}
