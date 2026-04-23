from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FriendRequestCreate(BaseModel):
    user_id: str


class FriendSummary(BaseModel):
    id: str
    display_name: str
    avatar_url: str | None = None
    bio: str = ""
    top_clusters: list[str] = []
    status: str
    since: datetime | None = None
    resonance_score: int | None = None
    shared_topics: list[str] = []


class FriendsListResponse(BaseModel):
    friends: list[FriendSummary]
    incoming: list[FriendSummary]
    outgoing: list[FriendSummary]


class FriendResonanceRead(BaseModel):
    user_id: str
    display_name: str
    resonance_score: int
    shared_topics: list[str]
