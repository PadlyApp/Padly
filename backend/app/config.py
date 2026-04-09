"""
Centralized application settings via pydantic-settings.

All environment variables are declared once here.  Other modules import
``settings`` (the singleton instance) rather than calling ``os.getenv``
directly.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _extract_jwt_role(jwt_token: str) -> str | None:
    """Best-effort JWT payload parse to read the Supabase key role claim."""
    try:
        parts = jwt_token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(
            (payload + padding).encode("utf-8")
        ).decode("utf-8")
        return json.loads(decoded).get("role")
    except Exception:
        return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Supabase ----
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    # ---- Application ----
    environment: str = "development"
    cors_origins: str = ""
    admin_secret: str = ""

    # ---- ML service ----
    ml_service_url: str = ""

    # ---- Phase 3B serving controls ----
    padly_group_neural_ranking_enabled: bool = False
    padly_group_neural_kill_switch: bool = False
    padly_stable_group_listing_writes_enabled: bool = False

    # ---- Derived helpers ----
    @property
    def is_dev(self) -> bool:
        return self.environment.lower() in ("development", "dev", "local")

    # ---- Validators ----
    @model_validator(mode="after")
    def _validate_supabase_keys(self) -> "Settings":
        if self.supabase_service_key == self.supabase_anon_key:
            raise ValueError(
                "Invalid configuration: SUPABASE_SERVICE_KEY matches SUPABASE_ANON_KEY"
            )
        role = _extract_jwt_role(self.supabase_service_key)
        if role != "service_role":
            raise ValueError(
                f"Invalid SUPABASE_SERVICE_KEY role: expected 'service_role', "
                f"got '{role or 'unknown'}'"
            )
        return self


settings = Settings()
