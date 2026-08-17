from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserProfileRead(BaseModel):
    id: str
    display_name: str
    bio: str
    is_public: bool
    onboarding_v2_completed: bool = False
    node_count: int
    cluster_count: int
    top_clusters: list[str]
    follower_count: int = 0
    following_count: int = 0
    created_at: datetime | None = None


class UserProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=500)
    is_public: bool | None = None
    onboarding_v2_completed: bool | None = None


class UserSearchResult(BaseModel):
    id: str
    display_name: str
    bio: str
    is_public: bool
    top_clusters: list[str]
    relationship: dict = Field(default_factory=dict)
