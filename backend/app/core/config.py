from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ThoughtGraph API"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./thoughtgraph.db"
    auth_mode: Literal["development", "production"] = "development"
    admin_user_ids: list[str] = Field(default_factory=list)
    allow_dev_auth_bypass: bool = True
    allow_dev_user_header_impersonation: bool = False
    allow_guest_access: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )
    default_user_id: str = "local-user"
    semantic_link_threshold: float = 0.23
    semantic_link_limit: int = 5
    graph_window_days: int = 30
    graph_search_limit: int = 12
    discovery_default_limit: int = 10
    discovery_candidate_limit: int = 80
    vector_dimensions: int = 256
    run_jobs_inline: bool = True
    app_url: str = "http://127.0.0.1:5174"
    media_storage_dir: str = "./storage"
    media_upload_url_ttl_seconds: int = 900
    max_image_upload_bytes: int = 25_000_000
    max_video_upload_bytes: int = 250_000_000
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_from_email: str | None = None
    smtp_from_name: str = "ThoughtGraph"
    model_config = SettingsConfigDict(
        env_prefix="THOUGHTGRAPH_",
        case_sensitive=False,
    )

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def _parse_admin_user_ids(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            if cleaned.startswith("["):
                return json.loads(cleaned)
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
