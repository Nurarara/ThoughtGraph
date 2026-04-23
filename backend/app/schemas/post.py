from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


CLUSTER_KEYS = {"technology", "growth", "purpose"}
VISIBILITY_VALUES = {"public", "friends", "private"}


class PostCreate(BaseModel):
    cluster_key: str = Field(pattern=r"^(technology|growth|purpose)$")
    caption: str = Field(max_length=500, default="")
    media_url: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=200)
    visibility: str = Field(default="friends", pattern=r"^(public|friends|private)$")


class PostRead(BaseModel):
    id: str
    user_id: str
    display_name: str
    cluster_key: str
    caption: str
    media_url: str | None
    location: str | None
    visibility: str
    created_at: datetime
    reaction_count: int = 0
    viewer_liked: bool = False
    comment_count: int = 0


class PostListResponse(BaseModel):
    cluster_key: str
    posts: list[PostRead]
