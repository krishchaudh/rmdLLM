import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://rmd:rmd@localhost:5433/rmd"
    redis_url: str = "redis://localhost:6380/0"
    # auto: use the RQ worker when one is listening, otherwise run jobs in-process (free tier)
    ingest_mode: Literal["auto", "inline", "rq"] = "auto"
    upload_dir: str = "./data/uploads"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    admin_username: str = "admin"
    admin_password: str = "change-me"
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_expire_minutes: int = 720

    # End-user accounts (Supabase Auth). Tokens are verified against the project's JWKS
    # (asymmetric keys) or, for legacy projects, the shared JWT secret.
    supabase_url: str = ""
    supabase_jwt_secret: str = ""

    llm_provider: Literal["openai", "mock"] = "openai"
    embedding_provider: Literal["openai", "mock"] = "openai"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1024
    generation_model: str = "gpt-4.1-mini"
    rerank_enabled: bool = True
    rerank_candidates: int = 16
    kind_floor: int = 3
    verification_model: str = "gpt-4.1-mini"

    rate_limit_ask: str = "20/minute"  # per IP / per account burst limit
    rate_limit_ask_guest_daily: str = "40/day"  # per IP, not signed in
    rate_limit_ask_user_daily: str = "300/day"  # per account
    rate_limit_ask_global_daily: str = "3000/day"  # whole site, cost safety net
    max_upload_mb: int = 200

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env in ("staging", "production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
