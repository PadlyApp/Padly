"""
Shared authentication / authorization helpers used across multiple route modules.

Centralises the ``auth-user → users.id`` resolution and group-membership
guard that were previously duplicated in ``groups.py`` and ``interactions.py``.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException

from app.dependencies.auth import resolve_auth_user
from app.dependencies.supabase import get_admin_client


def resolve_current_user_id(token: str) -> str:
    """Map an authenticated JWT to the internal ``users.id`` UUID.

    Tries ``users.auth_id`` first, then falls back to ``users.id`` for
    legacy rows where the two happen to match.
    """
    supabase = get_admin_client()
    auth_user = resolve_auth_user(supabase, token)
    auth_user_id = auth_user.id

    user_record = (
        supabase.table("users")
        .select("id")
        .eq("auth_id", auth_user_id)
        .limit(1)
        .execute()
    )
    if user_record.data:
        return user_record.data[0]["id"]

    fallback_record = (
        supabase.table("users")
        .select("id")
        .eq("id", auth_user_id)
        .limit(1)
        .execute()
    )
    if fallback_record.data:
        return fallback_record.data[0]["id"]

    raise HTTPException(status_code=404, detail="User profile not found")


def require_group_membership(group_id: str, user_id: str) -> None:
    """Raise 403 unless *user_id* is an accepted member of *group_id*."""
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
        raise HTTPException(
            status_code=403, detail="You are not a member of this group"
        )


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default
