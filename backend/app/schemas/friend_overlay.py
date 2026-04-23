from __future__ import annotations

from pydantic import BaseModel


class FriendGhostNode(BaseModel):
    id: str
    display_name: str
    cluster_key: str
    post_count: int


class FriendOverlayResponse(BaseModel):
    nodes: list[FriendGhostNode]
