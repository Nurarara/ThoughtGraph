from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    content: str
    preview: str
    created_at: datetime
    emotion: str
    topics: list[str]
    cluster_id: str | None
    cluster_label: str | None
    color: str
    size: float
    connection_count: int
    activity_score: int
    author_id: str | None = None
    author_display_name: str | None = None
    visibility: str | None = None
    is_social: bool = False


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: str
    weight: float


class GraphCluster(BaseModel):
    id: str
    label: str
    color: str
    percentage: float
    thought_count: int
    trend: str
    dominant_themes: list[str]
    emotion_distribution: dict[str, int]


class GraphAuthor(BaseModel):
    user_id: str
    display_name: str
    avatar_url: str | None
    color: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    clusters: list[GraphCluster]
    mood: str
    first_thought_at: datetime | None
    last_thought_at: datetime | None
    social_enabled: bool = False
    social_nodes: list[GraphNode] = []
    social_edges: list[GraphEdge] = []
    social_profiles: list[GraphAuthor] = []
