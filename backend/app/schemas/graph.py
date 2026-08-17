from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GraphEdgeRead(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str
    weight: float
    explanation: dict = Field(default_factory=dict)


class GraphNodeRead(BaseModel):
    id: str
    kind: str
    title: str | None
    content_text: str
    preview_text: str
    visibility: str
    created_at: datetime
    updated_at: datetime
    topics: list[str]
    cluster_id: str | None
    cluster_label: str | None
    cluster_color: str | None
    connection_count: int
    x: float
    y: float
    author_id: str | None = None
    author_display_name: str | None = None
    relationship_to_viewer: str | None = None
    is_social: bool = False
    media_asset_id: str | None = None
    media_kind: str | None = None
    media_status: str | None = None
    thumbnail_url: str | None = None
    playback_url: str | None = None
    duration_seconds: float | None = None
    media_url: str | None = None
    link_url: str | None = None
    reply_to_node_id: str | None = None
    quote_of_node_id: str | None = None


class GraphClusterRead(BaseModel):
    id: str
    label: str
    color: str
    summary: str
    node_count: int
    dominant_topics: list[str]
    centroid_x: float
    centroid_y: float
    owner_user_id: str | None = None
    is_social: bool = False


class GraphViewport(BaseModel):
    center_x: float
    center_y: float
    zoom_hint: float


class GraphExplanation(BaseModel):
    reason: str
    generated_at: datetime


class GraphResponse(BaseModel):
    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]
    clusters: list[GraphClusterRead]
    viewport: GraphViewport
    explanation: GraphExplanation
    social_mode: bool = False


class GraphSearchItem(BaseModel):
    node_id: str
    title: str | None
    preview_text: str
    cluster_label: str | None
    cluster_color: str | None
    score: float


class GraphSearchResponse(BaseModel):
    items: list[GraphSearchItem]
