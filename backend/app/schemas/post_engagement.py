from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReactionToggleResponse(BaseModel):
    post_id: str
    liked: bool
    reaction_count: int


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class CommentRead(BaseModel):
    id: str
    post_id: str
    user_id: str
    display_name: str
    content: str
    created_at: datetime


class CommentListResponse(BaseModel):
    post_id: str
    comments: list[CommentRead]


class PostEngagementSummary(BaseModel):
    post_id: str
    reaction_count: int
    viewer_liked: bool
    comment_count: int
