from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.graph import GraphNodeRead
from app.schemas.social import SocialRelationshipRead


class DiscoveryFilters(BaseModel):
    q: str | None = None
    close_to_me: bool = False
    outside_my_bubble: bool = False
    high_evidence: bool = False
    new_low_spread: bool = False
    trusted_only: bool = False
    limit: int = Field(default=10, ge=1, le=25)


class DiscoveryScoreBreakdown(BaseModel):
    relevance: float
    novelty: float
    trust: float
    diversity: float
    social_proximity: float
    total: float


class DiscoveryExplanationRead(BaseModel):
    primary_reason: str
    summary: str
    matched_topics: list[str] = Field(default_factory=list)
    relationship_to_viewer: str | None = None
    signal_notes: list[str] = Field(default_factory=list)
    unavailable_filters: list[str] = Field(default_factory=list)
    score_breakdown: DiscoveryScoreBreakdown


class DiscoveryNodeItemRead(BaseModel):
    node: GraphNodeRead
    explanation: DiscoveryExplanationRead


class DiscoveryPersonItemRead(BaseModel):
    user_id: str
    display_name: str
    bio: str
    shared_topics: list[str] = Field(default_factory=list)
    shared_cluster_labels: list[str] = Field(default_factory=list)
    visible_node_count: int = 0
    relationship: SocialRelationshipRead
    explanation: DiscoveryExplanationRead


class DiscoveryFilterAvailability(BaseModel):
    close_to_me: bool = True
    outside_my_bubble: bool = True
    high_evidence: bool = True
    new_low_spread: bool = True
    trusted_only: bool = False


class DiscoveryExploreResponse(BaseModel):
    materialization_id: str
    generated_at: datetime
    filters: DiscoveryFilters
    filter_availability: DiscoveryFilterAvailability
    explanation_summary: str
    items: list[DiscoveryNodeItemRead]


class RelatedIdeasResponse(BaseModel):
    materialization_id: str
    generated_at: datetime
    subject: GraphNodeRead
    explanation_summary: str
    items: list[DiscoveryNodeItemRead]


class AdjacentPeopleResponse(BaseModel):
    materialization_id: str
    generated_at: datetime
    explanation_summary: str
    items: list[DiscoveryPersonItemRead]
