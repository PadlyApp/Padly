"""
Guest interactions route

POST /api/interactions/guest-events

Logs behavioural events from unauthenticated (guest) users.
Used for funnel analytics: understanding where guests drop off,
what they browse, and what triggers signup.

All data is anonymous — only a hashed IP is stored, never the raw address.
"""

import hashlib
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.dependencies.rate_limit import guest_rate_limit

router = APIRouter(prefix="/api/interactions", tags=["guest-interactions"])


class GuestEvent(BaseModel):
    guest_session_id: str
    event_type: str          # swipe_right | swipe_left | listing_view | signup_prompt_shown | signup_prompt_dismissed | signup_prompt_clicked
    listing_id: Optional[str] = None
    position_in_feed: Optional[int] = None
    guest_prefs_snapshot: Optional[Dict[str, Any]] = None
    device_context: Optional[Dict[str, Any]] = None


@router.post("/guest-events", status_code=201)
async def log_guest_event(
    event: GuestEvent,
    request: Request,
    _: None = Depends(guest_rate_limit),
):
    """
    Record a single guest interaction event.

    This endpoint is intentionally lenient — it always returns 201 even if
    the DB write fails, so a backend hiccup never breaks the guest UX.
    """
    try:
        from app.dependencies.supabase import get_admin_client
        supabase = get_admin_client()

        # Hash the IP for privacy — we only need it for deduplication, not identity
        from app.dependencies.rate_limit import _get_client_ip
        raw_ip = _get_client_ip(request)
        ip_hash = hashlib.sha256(raw_ip.encode()).hexdigest()[:16] if raw_ip != "unknown" else None

        supabase.table("guest_interactions").insert({
            "guest_session_id": event.guest_session_id,
            "event_type": event.event_type,
            "listing_id": event.listing_id or None,
            "position_in_feed": event.position_in_feed,
            "guest_prefs_snapshot": event.guest_prefs_snapshot,
            "device_context": event.device_context,
            "ip_hash": ip_hash,
        }).execute()

    except Exception as e:
        # Best-effort: log the error but never surface it to the guest
        print(f"[guest-events] insert error: {e}")

    return {"status": "ok"}
