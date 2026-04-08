"""FastAPI TestClient tests for critical routes and auth guards."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Root / health — basic smoke tests that the app boots
# ---------------------------------------------------------------------------

class TestRootEndpoints:
    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == "1.0.0"
        assert "health" in body

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# Admin secret guard
# ---------------------------------------------------------------------------

class TestAdminGuard:
    def test_missing_secret_header(self, client):
        r = client.get("/api/admin/users")
        assert r.status_code in (401, 503)

    def test_wrong_secret(self, client):
        r = client.get(
            "/api/admin/users",
            headers={"X-Admin-Secret": "definitely-wrong"},
        )
        assert r.status_code == 401

    def test_valid_secret_passes_guard(self, client):
        from app.config import settings

        if not settings.admin_secret:
            pytest.skip("ADMIN_SECRET not configured")

        r = client.get(
            "/api/admin/users",
            headers={"X-Admin-Secret": settings.admin_secret},
        )
        # Guard passed → route runs (may 500 without live Supabase)
        assert r.status_code not in (401, 503)


# ---------------------------------------------------------------------------
# Token extraction dependencies (unit tests)
# ---------------------------------------------------------------------------

class TestTokenDependencies:
    @pytest.mark.asyncio
    async def test_get_user_token_extracts_bearer(self):
        from app.dependencies.auth import get_user_token

        assert await get_user_token("Bearer my-jwt") == "my-jwt"

    @pytest.mark.asyncio
    async def test_get_user_token_none_without_header(self):
        from app.dependencies.auth import get_user_token

        assert await get_user_token(None) is None

    @pytest.mark.asyncio
    async def test_get_user_token_rejects_non_bearer(self):
        from app.dependencies.auth import get_user_token

        with pytest.raises(HTTPException) as exc:
            await get_user_token("Basic abc123")
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_user_token_rejects_empty_bearer(self):
        from app.dependencies.auth import get_user_token

        with pytest.raises(HTTPException) as exc:
            await get_user_token("Bearer ")
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_require_user_token_raises_without_token(self):
        from app.dependencies.auth import require_user_token

        with pytest.raises(HTTPException) as exc:
            await require_user_token(None)
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Request-body validation (no Supabase needed)
# ---------------------------------------------------------------------------

class TestRequestValidation:
    def test_signup_invalid_email(self, client):
        r = client.post(
            "/api/auth/signup",
            json={"email": "not-an-email", "password": "s3cr3t", "full_name": "X"},
        )
        assert r.status_code == 422

    def test_signup_missing_fields(self, client):
        r = client.post("/api/auth/signup", json={"email": "a@b.com"})
        assert r.status_code == 422

    def test_signin_missing_fields(self, client):
        r = client.post("/api/auth/signin", json={})
        assert r.status_code == 422

    def test_refresh_missing_token(self, client):
        r = client.post("/api/auth/refresh", json={})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Protected route access (no mocked Supabase — just verifies the 401 guard)
# ---------------------------------------------------------------------------

class TestProtectedRoutes:
    def test_me_requires_token(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_users_list_requires_token(self, client):
        r = client.get("/api/users")
        assert r.status_code == 401

    def test_signout_requires_token(self, client):
        r = client.post("/api/auth/signout")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Settings sanity
# ---------------------------------------------------------------------------

class TestSettings:
    def test_settings_loaded(self):
        from app.config import settings

        assert settings.supabase_url
        assert settings.supabase_anon_key
        assert settings.supabase_service_key

    def test_is_dev_is_bool(self):
        from app.config import settings

        assert isinstance(settings.is_dev, bool)

    def test_bool_flags_are_bools(self):
        from app.config import settings

        assert isinstance(settings.padly_group_neural_ranking_enabled, bool)
        assert isinstance(settings.padly_group_neural_kill_switch, bool)
        assert isinstance(settings.padly_stable_group_listing_writes_enabled, bool)


# ---------------------------------------------------------------------------
# Supabase facade (SupabaseHTTPClient) unit tests
# ---------------------------------------------------------------------------

class TestSupabaseFacade:
    """Verify the rewritten facade delegates to supabase-py correctly."""

    def _make_facade(self, mock_client):
        """Build a facade whose internal client is *mock_client*."""
        with patch(
            "app.dependencies.supabase.get_admin_client",
            return_value=mock_client,
        ):
            from app.services.supabase_client import SupabaseHTTPClient

            return SupabaseHTTPClient(is_admin=True)

    @pytest.mark.asyncio
    async def test_select_basic(self):
        mock_client = MagicMock()
        result = MagicMock(data=[{"id": "1"}])
        mock_client.table.return_value.select.return_value.execute.return_value = (
            result
        )

        facade = self._make_facade(mock_client)
        rows = await facade.select("users")

        assert rows == [{"id": "1"}]
        mock_client.table.assert_called_with("users")

    @pytest.mark.asyncio
    async def test_select_with_filter(self):
        mock_client = MagicMock()
        result = MagicMock(data=[{"id": "2"}])
        mock_client.table.return_value.select.return_value.filter.return_value.execute.return_value = (
            result
        )

        facade = self._make_facade(mock_client)
        rows = await facade.select("users", filters={"status": "eq.active"})

        assert rows == [{"id": "2"}]
        mock_client.table.return_value.select.return_value.filter.assert_called_with(
            "status", "eq", "active"
        )

    @pytest.mark.asyncio
    async def test_select_with_or_filter(self):
        mock_client = MagicMock()
        result = MagicMock(data=[{"id": "3"}])
        mock_client.table.return_value.select.return_value.or_.return_value.execute.return_value = (
            result
        )

        facade = self._make_facade(mock_client)
        rows = await facade.select(
            "users",
            filters={"or": "(name.ilike.*test*,email.ilike.*test*)"},
        )

        assert rows == [{"id": "3"}]
        mock_client.table.return_value.select.return_value.or_.assert_called_with(
            "name.ilike.*test*,email.ilike.*test*"
        )

    @pytest.mark.asyncio
    async def test_select_empty(self):
        mock_client = MagicMock()
        result = MagicMock(data=None)
        mock_client.table.return_value.select.return_value.execute.return_value = (
            result
        )

        facade = self._make_facade(mock_client)
        rows = await facade.select("users")
        assert rows == []

    @pytest.mark.asyncio
    async def test_select_one_found(self):
        mock_client = MagicMock()
        result = MagicMock(data=[{"id": "10", "name": "Alice"}])
        mock_client.table.return_value.select.return_value.filter.return_value.limit.return_value.execute.return_value = (
            result
        )

        facade = self._make_facade(mock_client)
        row = await facade.select_one("users", "10")
        assert row == {"id": "10", "name": "Alice"}

    @pytest.mark.asyncio
    async def test_select_one_not_found(self):
        mock_client = MagicMock()
        result = MagicMock(data=[])
        mock_client.table.return_value.select.return_value.filter.return_value.limit.return_value.execute.return_value = (
            result
        )

        facade = self._make_facade(mock_client)
        row = await facade.select_one("users", "999")
        assert row is None

    @pytest.mark.asyncio
    async def test_insert(self):
        mock_client = MagicMock()
        result = MagicMock(data=[{"id": "new", "name": "Bob"}])
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            result
        )

        facade = self._make_facade(mock_client)
        row = await facade.insert("users", {"name": "Bob"})

        assert row == {"id": "new", "name": "Bob"}
        mock_client.table.return_value.insert.assert_called_with({"name": "Bob"})

    @pytest.mark.asyncio
    async def test_update(self):
        mock_client = MagicMock()
        result = MagicMock(data=[{"id": "1", "name": "Updated"}])
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            result
        )

        facade = self._make_facade(mock_client)
        row = await facade.update("users", "1", {"name": "Updated"})

        assert row == {"id": "1", "name": "Updated"}

    @pytest.mark.asyncio
    async def test_delete(self):
        mock_client = MagicMock()
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = (
            MagicMock()
        )

        facade = self._make_facade(mock_client)
        ok = await facade.delete("users", "1")
        assert ok is True

    @pytest.mark.asyncio
    async def test_count(self):
        mock_client = MagicMock()
        result = MagicMock(count=42)
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = (
            result
        )

        facade = self._make_facade(mock_client)
        n = await facade.count("users")
        assert n == 42

    @pytest.mark.asyncio
    async def test_select_propagates_error(self):
        mock_client = MagicMock()
        mock_client.table.return_value.select.side_effect = RuntimeError("boom")

        facade = self._make_facade(mock_client)

        with pytest.raises(HTTPException) as exc:
            await facade.select("users")
        assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# get_supabase_admin_client alias
# ---------------------------------------------------------------------------

class TestAdminClientAlias:
    def test_alias_returns_client(self):
        mock = MagicMock()
        with patch(
            "app.dependencies.supabase.get_admin_client", return_value=mock
        ):
            from app.services.supabase_client import get_supabase_admin_client

            assert get_supabase_admin_client() is mock
