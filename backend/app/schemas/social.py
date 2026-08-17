from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.node import NodeRead


class SocialRelationshipRead(BaseModel):
    target_user_id: str
    following: bool = False
    followed_by: bool = False
    friendship_state: str = "none"
    blocked: bool = False
    muted: bool = False
    restricted: bool = False
    blocked_by_target: bool = False
    restricted_by_target: bool = False


class RestrictionUpdate(BaseModel):
    kind: str = Field(pattern="^(blocked|muted|restricted)$")
    active: bool


class FollowStateRead(BaseModel):
    following: bool


class FriendRequestCreate(BaseModel):
    user_id: str


class SocialProfileRead(BaseModel):
    id: str
    display_name: str
    bio: str
    is_public: bool
    node_count: int
    cluster_count: int
    top_clusters: list[str]
    created_at: datetime | None = None
    relationship: SocialRelationshipRead


class FriendshipListItem(BaseModel):
    id: str
    display_name: str
    bio: str
    top_clusters: list[str]
    friendship_state: str
    relationship: SocialRelationshipRead
    updated_at: datetime


class FriendshipListsRead(BaseModel):
    friends: list[FriendshipListItem]
    incoming: list[FriendshipListItem]
    outgoing: list[FriendshipListItem]
    suggestions: list[FriendshipListItem]


class SocialNeighborhoodItem(BaseModel):
    user_id: str
    display_name: str
    relationship: SocialRelationshipRead
    shared_cluster_labels: list[str]
    shared_topics: list[str]
    visible_node_count: int


class SocialNeighborhoodResponse(BaseModel):
    items: list[SocialNeighborhoodItem]


class ReplyBranchRead(BaseModel):
    root: NodeRead
    replies: list[NodeRead]
    quoted_node: NodeRead | None = None
