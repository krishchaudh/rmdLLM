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
    upload_dir: str = "./data/uploads"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    admin_username: str = "admin"
    admin_password: str = "change-me"
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_expire_minutes: int = 720

    llm_provider: Literal["openai", "mock"] = "openai"
    embedding_provider: Literal["openai", "mock"] = "openai"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1024
    generation_model: str = "gpt-4.1-mini"
    verification_model: str = "gpt-4.1-mini"

    rate_limit_ask: str = "20/minute"
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
