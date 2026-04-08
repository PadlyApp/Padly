"""
Shared pytest fixtures for Padly backend tests.

Environment bootstrap
---------------------
``os.environ.setdefault`` calls below guarantee that ``app.config.Settings``
can be constructed even when no ``.env`` file exists (e.g. in CI).  The
values are the standard Supabase *local-dev* JWTs — they embed the correct
``role`` claims but carry no real secrets.
"""

from __future__ import annotations

import os

# Must run BEFORE any app import triggers Settings construction.
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9."
    "CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0",
)
os.environ.setdefault(
    "SUPABASE_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0."
    "EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IQ",
)
os.environ.setdefault("ADMIN_SECRET", "test-admin-secret-for-ci")

from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    """Vanilla FastAPI ``TestClient`` — no dependency overrides."""
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def mock_supabase_admin(monkeypatch) -> MagicMock:
    """Replace the admin ``Client`` singleton so no network I/O occurs.

    Patches every import-site that captured a reference to
    ``supabase_admin`` at module level.
    """
    mock = MagicMock()
    monkeypatch.setattr("app.db.supabase_admin", mock)
    monkeypatch.setattr("app.db.supabase", mock)
    monkeypatch.setattr("app.dependencies.supabase.supabase_admin", mock)
    return mock
