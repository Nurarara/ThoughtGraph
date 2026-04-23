from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FollowState(BaseModel):
    following: bool


class SocialRelationship(BaseModel):
    following: bool
    followed_by: bool


class FollowListItem(BaseModel):
    user_id: str
    display_name: str
    avatar_url: str | None
    top_clusters: list[str]
    followed_at: datetime


class SocialReplyRead(BaseModel):
    id: str
    content: str
    created_at: datetime
    emotion: str
    topics: list[str]
    author_id: str
    author_display_name: str
    visibility: str
    reply_to_id: str | None
    reply_to_user_id: str | None


class ReplyThreadRead(BaseModel):
    root: SocialReplyRead
    replies: list[SocialReplyRead]


class InfluenceScoreRead(BaseModel):
    user_id: str
    target_user_id: str
    target_display_name: str
    score: float
    edge_count: int
    cluster_overlap: float
    reply_count: int
    summary: str
    computed_at: datetime


class TrendingClusterRead(BaseModel):
    label: str
    growth_percentage: float
    user_count: int
    thought_count: int
    sample_thoughts: list[str]


class SocialFeedItem(BaseModel):
    thought: SocialReplyRead
    relationship: str


class SerendipityMatchRead(BaseModel):
    id: str
    alias: str
    thought_preview: str
    shared_topics: list[str]
    similarity_score: int
    created_at: datetime


class SerendipityResponse(BaseModel):
    enabled: bool
    latest_thought_preview: str | None = None
    matches: list[SerendipityMatchRead]
