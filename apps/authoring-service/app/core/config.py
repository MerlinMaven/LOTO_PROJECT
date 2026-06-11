"""
Application settings loaded from environment variables.

All secrets come from the environment — never from source code.
pydantic-settings validates and coerces types at startup, failing fast
if required variables are missing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "SmartLOTO API"
    APP_VERSION: str = "2.0.0"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8501"]

    # ── Database ──────────────────────────────────────────────────────────────
    # Async URL used by SQLAlchemy at runtime (asyncpg driver)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/smartloto"
    # Synchronous URL used by Alembic only (psycopg2 or psycopg driver)
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/smartloto"

    # SQLAlchemy pool settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # ── Security (JWT-ready — auth deferred to Phase 3) ───────────────────────
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_64_RANDOM_HEX_CHARS"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Supabase (SUPABASE_KEY = service-role or anon key from dashboard) ────────
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    STORAGE_BUCKET: str = "smartloto-assets"

    # ── LLM providers ──────────────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "qwen/qwen-2.5-7b-instruct"
    MISTRAL_API_KEY: str = ""
    MISTRAL_MODEL: str = "mistral-small-latest"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    # vLLM self-hosted endpoint (optional — leave blank to skip)
    VLLM_BASE_URL: str = ""
    VLLM_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.3"
    HF_TOKEN: str = ""

    # ── Pagination ────────────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — call this everywhere instead of instantiating Settings."""
    return Settings()
