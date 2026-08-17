from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EventDispatchOutcome(BaseModel):
    event_id: str
    consumer_name: str
    status: str
    attempts: int
    idempotent_skip: bool = False
    error: str | None = None


class EventFanoutResponse(BaseModel):
    dispatched: int
    outcomes: list[EventDispatchOutcome] = Field(default_factory=list)


class DeadLetterRead(BaseModel):
    id: str
    event_id: str
    consumer_name: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    error: str
    attempts: int
    replay_status: str
    last_failed_at: datetime
    replayed_at: datetime | None

    model_config = {"from_attributes": True}


class ReplayRequest(BaseModel):
    dead_letter_ids: list[str] | None = None
    consumer_names: list[str] | None = None
    limit: int = Field(default=50, ge=1, le=500)


class ReplayResponse(BaseModel):
    attempted: int
    replayed: int
    failed: int
    outcomes: list[EventDispatchOutcome] = Field(default_factory=list)


class SearchRebuildResponse(BaseModel):
    indexed: int
    deleted: int
    source_tables: list[str]
    user_id: str | None = None


class SearchExplainScore(BaseModel):
    lexical: float
    semantic: float
    total: float
    matched_terms: list[str]
    semantic_available: bool


class SearchResultItem(BaseModel):
    document_id: str
    source_table: str
    source_id: str
    title: str | None
    preview_text: str
    topics: list[str]
    score: SearchExplainScore
    explanation: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    items: list[SearchResultItem]
    explanation_summary: str


class GraphReadModelNodeRead(BaseModel):
    source_node_id: str
    kind: str
    title: str | None
    preview_text: str
    topics: list[str]
    cluster_id: str | None
    degree: int
    position_x: float
    position_y: float
    derived_from: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class GraphReadModelEdgeRead(BaseModel):
    source_node_id: str
    target_node_id: str
    edge_type: str
    weight: float
    explanation: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class GraphProjectionResponse(BaseModel):
    projection_id: str
    status: str
    nodes: int
    edges: int
    user_id: str | None = None
    source_high_watermark: str | None = None
    explanation: str


class GraphReadModelResponse(BaseModel):
    nodes: list[GraphReadModelNodeRead]
    edges: list[GraphReadModelEdgeRead]
    projection_version: str | None
    explanation: str


class PartitionStatus(BaseModel):
    name: str
    partition_key: str
    partitions: dict[str, int]
    total_records: int
    status: str


class SLOStatus(BaseModel):
    name: str
    target_seconds: int
    observed_seconds: int | None
    status: str
    detail: str


class ReplayReadiness(BaseModel):
    ready: bool
    pending_dead_letters: int
    registered_consumers: list[str]
    blockers: list[str]


class OpsStatusResponse(BaseModel):
    generated_at: datetime
    partitions: list[PartitionStatus]
    slos: list[SLOStatus]
    replay_readiness: ReplayReadiness
