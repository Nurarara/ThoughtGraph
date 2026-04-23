from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProfileSummaryPost(BaseModel):
    id: str
    cluster_key: str
    caption: str
    media_url: str | None
    location: str | None
    created_at: datetime


class ProfileSummaryResponse(BaseModel):
    id: str
    display_name: str
    bio: str
    avatar_url: str | None
    top_clusters: list[str]
    friend_status: str
    mutual_friend_count: int
    public_post_count: int
    resonance_score: int | None = None
    shared_topics: list[str] = []
    recent_posts: list[ProfileSummaryPost]
    is_self: bool
