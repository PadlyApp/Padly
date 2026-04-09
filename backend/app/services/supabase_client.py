"""
Supabase client facade.

Provides an async CRUD helper (``SupabaseHTTPClient``) that delegates to the
single supabase-py ``Client`` rather than hand-rolling raw httpx requests.
All existing call-sites keep their ``await client.select(…)`` interface
unchanged.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_filters(query: Any, filters: Dict[str, str]) -> Any:
    """Translate PostgREST query-param style filters to supabase-py calls."""
    for column, expr in filters.items():
        if column == "or":
            value = expr.strip()
            if value.startswith("(") and value.endswith(")"):
                value = value[1:-1]
            query = query.or_(value)
        else:
            op, _, value = expr.partition(".")
            query = query.filter(column, op, value)
    return query


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------

class SupabaseHTTPClient:
    """Thin async facade over the supabase-py ``Client``.

    Construction mirrors the original interface:

    * ``SupabaseHTTPClient(is_admin=True)`` — service-role (bypasses RLS)
    * ``SupabaseHTTPClient(token=jwt)``     — user-scoped (respects RLS)
    """

    def __init__(
        self,
        token: Optional[str] = None,
        is_admin: bool = False,
    ) -> None:
        from app.dependencies.supabase import get_admin_client, get_user_client

        if is_admin:
            self._client = get_admin_client()
        else:
            self._client = get_user_client(token)

    # -- SELECT --------------------------------------------------------

    async def select(
        self,
        table: str,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        def _run() -> List[Dict[str, Any]]:
            q = self._client.table(table).select(columns)
            if filters:
                q = _apply_filters(q, filters)
            if order:
                col, _, direction = order.partition(".")
                q = q.order(col, desc=(direction == "desc"))
            if limit is not None:
                q = q.limit(limit)
            if offset is not None:
                q = q.offset(offset)
            return q.execute().data or []

        try:
            return await asyncio.to_thread(_run)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Supabase query failed: {e}"
            ) from e

    async def select_one(
        self,
        table: str,
        id_value: str,
        id_column: str = "id",
        columns: str = "*",
    ) -> Optional[Dict[str, Any]]:
        results = await self.select(
            table,
            columns=columns,
            filters={id_column: f"eq.{id_value}"},
            limit=1,
        )
        return results[0] if results else None

    # -- INSERT --------------------------------------------------------

    async def insert(
        self, table: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            result = self._client.table(table).insert(data).execute()
            rows = result.data or []
            return rows[0] if rows else {}

        try:
            return await asyncio.to_thread(_run)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Insert failed: {e}"
            ) from e

    # -- UPDATE --------------------------------------------------------

    async def update(
        self,
        table: str,
        id_value: str,
        data: Dict[str, Any],
        id_column: str = "id",
    ) -> Dict[str, Any]:
        def _run() -> Dict[str, Any]:
            result = (
                self._client.table(table)
                .update(data)
                .eq(id_column, id_value)
                .execute(
            )
            rows = result.data or []
            return rows[0] if rows else {}

        try:
            return await asyncio.to_thread(_run)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Update failed: {e}"
            ) from e

    # -- DELETE --------------------------------------------------------

    async def delete(
        self,
        table: str,
        id_value: str,
        id_column: str = "id",
    ) -> bool:
        def _run() -> bool:
            self._client.table(table).delete().eq(id_column, id_value).execute()
            return True

        try:
            return await asyncio.to_thread(_run)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Delete failed: {e}"
            ) from e

    # -- COUNT ---------------------------------------------------------

    async def count(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        def _run() -> int:
            q = self._client.table(table).select("*", count="exact").limit(0)
            if filters:
                q = _apply_filters(q, filters)
            return q.execute().count or 0

        try:
            return await asyncio.to_thread(_run)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Count failed: {e}"
            ) from e


# ---------------------------------------------------------------------------
# Convenience alias expected by group_rematching_service
# ---------------------------------------------------------------------------

def get_supabase_admin_client():
    """Return the shared admin supabase-py ``Client``."""
    from app.dependencies.supabase import get_admin_client

    return get_admin_client()
