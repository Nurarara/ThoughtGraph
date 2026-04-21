from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ThoughtCreate(BaseModel):
    content: str = Field(min_length=3, max_length=2000)
    visibility: str = Field(default="public", pattern="^(public|private)$")
    reply_to_id: str | None = None


class ThoughtRead(BaseModel):
    id: str
    content: str
    created_at: datetime
    emotion: str
    topics: list[str]
    cluster_id: str | None
    connection_count: int
    activity_score: int
    visibility: str
    reply_to_id: str | None
    reply_to_user_id: str | None = None
    author_id: str | None = None

    model_config = {"from_attributes": True}
