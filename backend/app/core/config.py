from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ThoughtGraph API"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./thoughtgraph.db"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
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
    model_config = SettingsConfigDict(
        env_prefix="THOUGHTGRAPH_",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
