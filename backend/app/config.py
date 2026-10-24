"""Runtime settings, read from environment variables (or a local .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="production", description="'production' or 'development'")
    log_level: str = "INFO"
    data_dir: Path = REPO_ROOT / "data" / "processed"
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"

    # Optional: data.gov.in key for live mandi prices. Without it that feature is simply off.
    data_gov_in_api_key: SecretStr | None = None

    # Comma-separated origins allowed to call the API from another site (empty = same-origin only).
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    live_rate_limit_per_minute: int = Field(default=60, ge=1, le=10_000)
    weather_cache_seconds: int = Field(default=1800, ge=60)
    market_cache_seconds: int = Field(default=6 * 3600, ge=300)
    upstream_timeout_seconds: float = Field(default=10.0, gt=0, le=60)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @field_validator("data_gov_in_api_key", mode="before")
    @classmethod
    def _empty_key_is_none(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def market_prices_enabled(self) -> bool:
        return self.data_gov_in_api_key is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
