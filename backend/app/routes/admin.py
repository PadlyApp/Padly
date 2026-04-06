"""
Admin routes
Admin-only operations using service role (bypasses RLS).

All routes here require the X-Admin-Secret header to match the ADMIN_SECRET
environment variable. Never expose these endpoints to the frontend.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from typing import Any, Optional
from app.dependencies.auth import require_admin_key, require_user_token
from app.dependencies.supabase import get_admin_client
from app.services.supabase_client import SupabaseHTTPClient

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_key)],
)

authenticated_router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
)


@router.get("/users")
async def admin_list_users(
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
):
    """
    Admin: List ALL users (bypasses RLS).
    
    ⚠️ Uses service role key - never expose to frontend
    """
    client = SupabaseHTTPClient(is_admin=True)
    
    users = await client.select(
        table="users",
        limit=limit,
        offset=offset,
        order="created_at.desc"
    )
    
    return {
        "status": "success",
        "count": len(users),
        "data": users
    }


@router.get("/users/{user_id}")
async def admin_get_user(user_id: str):
    """Admin: Get any user by ID (bypasses RLS)"""
    client = SupabaseHTTPClient(is_admin=True)
    
    user = await client.select_one(
        table="users",
        id_value=user_id
    )
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "status": "success",
        "data": user
    }


@router.delete("/users/{user_id}")
async def admin_delete_user(user_id: str):
    """Admin: Force delete any user (bypasses RLS)"""
    client = SupabaseHTTPClient(is_admin=True)
    
    await client.delete(
        table="users",
        id_value=user_id
    )
    
    return {
        "status": "success",
        "message": "User deleted successfully"
    }


@router.get("/listings")
async def admin_list_listings(
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
):
    """Admin: List ALL listings (bypasses RLS)"""
    client = SupabaseHTTPClient(is_admin=True)
    
    listings = await client.select(
        table="listings",
        limit=limit,
        offset=offset,
        order="created_at.desc"
    )
    
    return {
        "status": "success",
        "count": len(listings),
        "data": listings
    }


@router.delete("/listings/{listing_id}")
async def admin_delete_listing(listing_id: str):
    """Admin: Force delete any listing (bypasses RLS)"""
    client = SupabaseHTTPClient(is_admin=True)
    
    await client.delete(
        table="listings",
        id_value=listing_id
    )
    
    return {
        "status": "success",
        "message": "Listing deleted successfully"
    }


@router.get("/stats")
async def admin_stats():
    """Admin: Get platform statistics"""
    client = SupabaseHTTPClient(is_admin=True)
    
    # Count users
    users_count = await client.count("users")
    
    # Count listings
    listings_count = await client.count("listings")
    
    # Count active listings
    active_listings_count = await client.count(
        "listings",
        filters={"status": "eq.active"}
    )
    
    return {
        "status": "success",
        "data": {
            "total_users": users_count,
            "total_listings": listings_count,
            "active_listings": active_listings_count
        }
    }


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _pct(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _date_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        return None


def _parse_iso_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _csv_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    if any(ch in text for ch in [",", "\"", "\n"]):
        return f"\"{text.replace('\"', '\"\"')}\""
    return text


async def _fetch_all_rows(
    client: SupabaseHTTPClient,
    table: str,
    *,
    columns: str = "*",
    filters: Optional[dict[str, Any]] = None,
    order: Optional[str] = None,
    batch_size: int = 1000,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        batch = await client.select(
            table=table,
            columns=columns,
            filters=filters,
            order=order,
            limit=batch_size,
            offset=offset if offset > 0 else None,
        )
        rows.extend(batch)
        if len(batch) < batch_size:
            break
        offset += batch_size

    return rows


def _build_group_summary(
    group_label: str,
    session_rows: list[dict[str, Any]],
    feedback_by_session: dict[str, dict[str, Any]],
    label_key: str = "variant",
) -> dict[str, Any]:
    total_sessions = len(session_rows)
    feedback_rows = [
        feedback_by_session[session["id"]]
        for session in session_rows
        if session.get("id") in feedback_by_session
    ]
    feedback_count = len(feedback_rows)
    usefulness_counts = Counter(row.get("feedback_label") for row in feedback_rows if row.get("feedback_label"))

    recommendation_total = sum(_int(row.get("recommendation_count_shown")) for row in session_rows)
    detail_open_total = sum(_int(row.get("detail_opens_count")) for row in session_rows)
    save_total = sum(_int(row.get("saves_count")) for row in session_rows)

    return {
        label_key: group_label,
        "total_sessions": total_sessions,
        "feedback_count": feedback_count,
        "feedback_rate": _pct(feedback_count, total_sessions),
        "very_useful_rate": _pct(usefulness_counts.get("very_useful", 0), feedback_count),
        "not_useful_rate": _pct(usefulness_counts.get("not_useful", 0), feedback_count),
        "avg_recommendation_count": _avg([_int(row.get("recommendation_count_shown")) for row in session_rows]),
        "avg_detail_opens": _avg([_int(row.get("detail_opens_count")) for row in session_rows]),
        "avg_saves": _avg([_int(row.get("saves_count")) for row in session_rows]),
        "avg_surface_dwell_ms": _avg([_int(row.get("surface_dwell_ms")) for row in session_rows]),
        "avg_detail_dwell_ms": _avg([_int(row.get("detail_dwell_ms")) for row in session_rows]),
        "detail_open_rate": _pct(detail_open_total, recommendation_total),
        "save_rate": _pct(save_total, recommendation_total),
    }


def _user_history_bucket(prior_sessions: int) -> str:
    if prior_sessions <= 0:
        return "new_user"
    if prior_sessions < 5:
        return "returning_user"
    return "experienced_user"


def _build_summary_export_csv(summary: dict[str, Any]) -> str:
    lines = ["section,label,metric,value"]

    for key, value in (summary.get("overview") or {}).items():
        lines.append(f"overview,overall,{_csv_escape(key)},{_csv_escape(value)}")

    for row in summary.get("usefulness_distribution") or []:
        label = row.get("label")
        lines.append(f"usefulness,{_csv_escape(label)},count,{_csv_escape(row.get('count'))}")
        lines.append(f"usefulness,{_csv_escape(label)},pct,{_csv_escape(row.get('pct'))}")

    for row in summary.get("negative_reasons") or []:
        label = row.get("label")
        lines.append(f"negative_reasons,{_csv_escape(label)},count,{_csv_escape(row.get('count'))}")
        lines.append(f"negative_reasons,{_csv_escape(label)},pct,{_csv_escape(row.get('pct'))}")

    for section_name, label_key in [
        ("variant_comparison", "variant"),
        ("model_version_comparison", "model_version"),
        ("user_history_buckets", "bucket"),
    ]:
        for row in summary.get(section_name) or []:
            label = row.get(label_key)
            for metric, value in row.items():
                if metric == label_key:
                    continue
                lines.append(f"{section_name},{_csv_escape(label)},{_csv_escape(metric)},{_csv_escape(value)}")

    for row in summary.get("position_breakdown") or []:
        label = row.get("position")
        lines.append(f"position_breakdown,{_csv_escape(label)},detail_open_count,{_csv_escape(row.get('detail_open_count'))}")
        lines.append(f"position_breakdown,{_csv_escape(label)},save_count,{_csv_escape(row.get('save_count'))}")

    for row in summary.get("daily_trends") or []:
        label = row.get("date")
        for metric, value in row.items():
            if metric == "date":
                continue
            lines.append(f"daily_trends,{_csv_escape(label)},{_csv_escape(metric)},{_csv_escape(value)}")

    return "\n".join(lines)


def _require_admin_user(token: str) -> dict[str, Any]:
    supabase = get_admin_client()
    user_response = supabase.auth.get_user(token)
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    auth_user_id = user_response.user.id
    profile_response = (
        supabase.table("users")
        .select("id,email,full_name,role")
        .eq("auth_id", auth_user_id)
        .limit(1)
        .execute()
    )
    if not profile_response.data:
        raise HTTPException(status_code=404, detail="User profile not found")

    profile = profile_response.data[0]
    if profile.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return profile


async def _evaluation_summary_payload(
    days: int = 30,
    surface: Optional[str] = None,
    variant: Optional[str] = None,
    user_mode: str = "all_sessions",
) -> dict[str, Any]:
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="days must be between 1 and 365")
    if user_mode not in {"all_sessions", "latest_per_user"}:
        raise HTTPException(status_code=422, detail="user_mode must be all_sessions or latest_per_user")

    normalized_surface = None if not surface or surface == "all" else surface
    normalized_variant = None if not variant or variant == "all" else variant
    if normalized_surface and normalized_surface not in {"matches", "discover"}:
        raise HTTPException(status_code=422, detail="surface must be matches, discover, or all")

    client = SupabaseHTTPClient(is_admin=True)
    since_iso = (_now_utc() - timedelta(days=days)).isoformat()

    session_filters: dict[str, Any] = {"started_at": f"gte.{since_iso}"}
    feedback_filters: dict[str, Any] = {"submitted_at": f"gte.{since_iso}"}
    event_filters: dict[str, Any] = {"created_at": f"gte.{since_iso}"}

    if normalized_surface:
        session_filters["surface"] = f"eq.{normalized_surface}"
        feedback_filters["surface"] = f"eq.{normalized_surface}"
        event_filters["surface"] = f"eq.{normalized_surface}"

    if normalized_variant:
        session_filters["experiment_variant"] = f"eq.{normalized_variant}"
        feedback_filters["experiment_variant"] = f"eq.{normalized_variant}"

    sessions = await _fetch_all_rows(
        client,
        "recommendation_sessions",
        columns=(
            "id,actor_user_id,surface,started_at,ended_at,recommendation_count_shown,"
            "experiment_name,experiment_variant,algorithm_version,model_version,"
            "prompt_presented_at,prompt_dismissed_at,feedback_submitted_at,"
            "detail_opens_count,saves_count,likes_count,surface_dwell_ms,detail_dwell_ms"
        ),
        filters=session_filters,
        order="started_at.desc",
    )

    all_sessions_for_history = await _fetch_all_rows(
        client,
        "recommendation_sessions",
        columns="id,actor_user_id,started_at,model_version",
        order="started_at.asc",
    )

    if user_mode == "latest_per_user":
        latest_sessions_by_user: dict[str, dict[str, Any]] = {}
        for session in sessions:
            actor_user_id = session.get("actor_user_id")
            if not actor_user_id:
                continue

            existing = latest_sessions_by_user.get(actor_user_id)
            if not existing or _parse_iso_datetime(session.get("started_at")) > _parse_iso_datetime(existing.get("started_at")):
                latest_sessions_by_user[actor_user_id] = session

        sessions = list(latest_sessions_by_user.values())

    session_ids = {row["id"] for row in sessions if row.get("id")}

    feedback_rows = await _fetch_all_rows(
        client,
        "user_recommendation_feedback",
        columns=(
            "recommendation_session_id,feedback_label,reason_label,submitted_at,"
            "surface,experiment_name,experiment_variant"
        ),
        filters=feedback_filters,
        order="submitted_at.desc",
    )
    feedback_rows = [
        row for row in feedback_rows
        if row.get("recommendation_session_id") in session_ids
    ]

    prior_session_counts_by_id: dict[str, int] = {}
    running_session_counts_by_user: dict[str, int] = defaultdict(int)
    for session in all_sessions_for_history:
        session_id = session.get("id")
        actor_user_id = session.get("actor_user_id")
        if not session_id or not actor_user_id:
            continue
        prior_session_counts_by_id[session_id] = running_session_counts_by_user[actor_user_id]
        running_session_counts_by_user[actor_user_id] += 1

    event_rows = await _fetch_all_rows(
        client,
        "recommendation_engagement_events",
        columns="recommendation_session_id,event_type,position_in_feed,dwell_ms,created_at",
        filters=event_filters,
        order="created_at.desc",
    )
    event_rows = [
        row for row in event_rows
        if row.get("recommendation_session_id") in session_ids
    ]

    feedback_by_session = {
        row["recommendation_session_id"]: row
        for row in feedback_rows
        if row.get("recommendation_session_id")
    }

    usefulness_counts = Counter(row.get("feedback_label") for row in feedback_rows if row.get("feedback_label"))
    reason_counts = Counter(row.get("reason_label") for row in feedback_rows if row.get("reason_label"))
    event_counts = Counter(row.get("event_type") for row in event_rows if row.get("event_type"))
    position_counts: dict[int, dict[str, int]] = defaultdict(lambda: {"detail_open": 0, "save": 0})
    total_detail_view_dwell = 0
    total_detail_view_events = 0

    for event in event_rows:
        event_type = event.get("event_type")
        position = event.get("position_in_feed")
        if event_type == "detail_view":
            total_detail_view_events += 1
            total_detail_view_dwell += _int(event.get("dwell_ms"))
        if event_type in {"detail_open", "save"} and position is not None:
            position_counts[_int(position)][event_type] += 1

    total_sessions = len(sessions)
    unique_users = len({row.get("actor_user_id") for row in sessions if row.get("actor_user_id")})
    feedback_count = len(feedback_rows)
    prompts_presented = sum(1 for row in sessions if row.get("prompt_presented_at"))
    prompts_dismissed = sum(1 for row in sessions if row.get("prompt_dismissed_at"))
    recommendation_total = sum(_int(row.get("recommendation_count_shown")) for row in sessions)
    detail_open_total = sum(_int(row.get("detail_opens_count")) for row in sessions)
    save_total = sum(_int(row.get("saves_count")) for row in sessions)

    daily_rollup: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "date": "",
            "total_sessions": 0,
            "feedback_count": 0,
            "very_useful_count": 0,
            "not_useful_count": 0,
            "somewhat_useful_count": 0,
            "avg_surface_dwell_ms": 0.0,
            "avg_saves": 0.0,
            "_surface_dwell_values": [],
            "_save_values": [],
        }
    )

    for session in sessions:
        day = _date_key(session.get("started_at"))
        if not day:
            continue
        bucket = daily_rollup[day]
        bucket["date"] = day
        bucket["total_sessions"] += 1
        bucket["_surface_dwell_values"].append(_int(session.get("surface_dwell_ms")))
        bucket["_save_values"].append(_int(session.get("saves_count")))

        feedback = feedback_by_session.get(session.get("id"))
        if feedback:
            bucket["feedback_count"] += 1
            label = feedback.get("feedback_label")
            if label == "very_useful":
                bucket["very_useful_count"] += 1
            elif label == "not_useful":
                bucket["not_useful_count"] += 1
            elif label == "somewhat_useful":
                bucket["somewhat_useful_count"] += 1

    daily_trends = []
    for day in sorted(daily_rollup.keys()):
        bucket = daily_rollup[day]
        bucket["avg_surface_dwell_ms"] = _avg(bucket.pop("_surface_dwell_values"))
        bucket["avg_saves"] = _avg(bucket.pop("_save_values"))
        daily_trends.append(bucket)

    variant_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in sessions:
        variant_label = session.get("experiment_variant") or "unassigned"
        variant_groups[variant_label].append(session)

    variant_comparison = [
        _build_group_summary(variant_label, grouped_sessions, feedback_by_session, label_key="variant")
        for variant_label, grouped_sessions in sorted(
            variant_groups.items(),
            key=lambda item: item[0],
        )
    ]

    model_version_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    user_history_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in sessions:
        model_version_label = session.get("model_version") or "unassigned"
        model_version_groups[model_version_label].append(session)

        bucket = _user_history_bucket(prior_session_counts_by_id.get(session.get("id"), 0))
        user_history_groups[bucket].append(session)

    model_version_comparison = [
        _build_group_summary(label, grouped_sessions, feedback_by_session, label_key="model_version")
        for label, grouped_sessions in sorted(model_version_groups.items(), key=lambda item: item[0])
    ]

    bucket_order = {"new_user": 0, "returning_user": 1, "experienced_user": 2}
    user_history_buckets = [
        _build_group_summary(label, grouped_sessions, feedback_by_session, label_key="bucket")
        for label, grouped_sessions in sorted(
            user_history_groups.items(),
            key=lambda item: bucket_order.get(item[0], 99),
        )
    ]

    usefulness_distribution = [
        {
            "label": label,
            "count": usefulness_counts.get(label, 0),
            "pct": _pct(usefulness_counts.get(label, 0), feedback_count),
        }
        for label in ["not_useful", "somewhat_useful", "very_useful"]
    ]

    negative_reasons = [
        {
            "label": label,
            "count": count,
            "pct": _pct(count, reason_counts.total()),
        }
        for label, count in reason_counts.most_common()
    ]

    position_breakdown = [
        {
            "position": position,
            "detail_open_count": counts["detail_open"],
            "save_count": counts["save"],
        }
        for position, counts in sorted(position_counts.items(), key=lambda item: item[0])
    ]

    return {
        "status": "success",
        "data": {
            "filters": {
                "days": days,
                "since": since_iso,
                "surface": normalized_surface or "all",
                "variant": normalized_variant or "all",
                "user_mode": user_mode,
            },
            "overview": {
                "total_sessions": total_sessions,
                "unique_users": unique_users,
                "feedback_count": feedback_count,
                "feedback_rate": _pct(feedback_count, total_sessions),
                "prompt_presented_count": prompts_presented,
                "prompt_dismissed_count": prompts_dismissed,
                "prompt_dismiss_rate": _pct(prompts_dismissed, prompts_presented),
                "very_useful_rate": _pct(usefulness_counts.get("very_useful", 0), feedback_count),
                "avg_recommendation_count": _avg([_int(row.get("recommendation_count_shown")) for row in sessions]),
                "avg_detail_opens": _avg([_int(row.get("detail_opens_count")) for row in sessions]),
                "avg_saves": _avg([_int(row.get("saves_count")) for row in sessions]),
                "avg_surface_dwell_ms": _avg([_int(row.get("surface_dwell_ms")) for row in sessions]),
                "avg_detail_dwell_ms": _avg([_int(row.get("detail_dwell_ms")) for row in sessions]),
                "avg_detail_view_dwell_ms": _avg(
                    [total_detail_view_dwell / total_detail_view_events] if total_detail_view_events else []
                ),
                "detail_open_rate": _pct(detail_open_total, recommendation_total),
                "save_rate": _pct(save_total, recommendation_total),
            },
            "usefulness_distribution": usefulness_distribution,
            "variant_comparison": variant_comparison,
            "model_version_comparison": model_version_comparison,
            "user_history_buckets": user_history_buckets,
            "negative_reasons": negative_reasons,
            "event_breakdown": {
                "detail_open": event_counts.get("detail_open", 0),
                "detail_view": event_counts.get("detail_view", 0),
                "save": event_counts.get("save", 0),
                "unsave": event_counts.get("unsave", 0),
            },
            "position_breakdown": position_breakdown,
            "daily_trends": daily_trends,
            "research_notes": {
                "sample_size_sessions": total_sessions,
                "sample_size_feedback": feedback_count,
                "counting_mode": user_mode,
                "exposure_bias_note": "Observed behavior is influenced by what the ranker chose to show.",
                "repeat_user_note": (
                    "Use latest_per_user when you want one contribution per participant; "
                    "use all_sessions when you want every recommendation session."
                ),
            },
        },
    }


@router.get("/evaluation/summary")
async def admin_evaluation_summary(
    days: int = 30,
    surface: Optional[str] = None,
    variant: Optional[str] = None,
    user_mode: str = "all_sessions",
):
    """
    Admin: Recommendation evaluation summary for dashboarding.

    Aggregates Phase 2/3 recommendation sessions, explicit feedback, and
    passive engagement into one dashboard-friendly payload.
    """
    return await _evaluation_summary_payload(days=days, surface=surface, variant=variant, user_mode=user_mode)


@authenticated_router.get("/evaluation/summary/authenticated")
async def authenticated_admin_evaluation_summary(
    days: int = 30,
    surface: Optional[str] = None,
    variant: Optional[str] = None,
    user_mode: str = "all_sessions",
    token: str = Depends(require_user_token),
):
    """
    Authenticated admin summary endpoint for the frontend dashboard.

    This keeps aggregation server-side with service-role access while allowing
    the dashboard to authenticate via a signed-in user whose role is admin.
    """
    _require_admin_user(token)
    return await _evaluation_summary_payload(days=days, surface=surface, variant=variant, user_mode=user_mode)


@authenticated_router.get("/evaluation/export/authenticated")
async def authenticated_admin_evaluation_export(
    days: int = 30,
    surface: Optional[str] = None,
    variant: Optional[str] = None,
    user_mode: str = "all_sessions",
    format: str = "json",
    token: str = Depends(require_user_token),
):
    """
    Export the aggregated evaluation summary for research reporting.
    """
    _require_admin_user(token)
    payload = await _evaluation_summary_payload(days=days, surface=surface, variant=variant, user_mode=user_mode)
    summary = payload["data"]

    if format == "json":
        return payload
    if format == "csv":
        csv_text = _build_summary_export_csv(summary)
        return PlainTextResponse(
            csv_text,
            headers={
                "Content-Disposition": "attachment; filename=evaluation-summary.csv",
                "Content-Type": "text/csv; charset=utf-8",
            },
        )

    raise HTTPException(status_code=422, detail="format must be json or csv")
