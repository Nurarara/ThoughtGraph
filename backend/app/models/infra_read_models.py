from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, utcnow


class InfraEventConsumerState(TimestampMixin, Base):
    __tablename__ = "infra_event_consumer_states"
    __table_args__ = (
        UniqueConstraint("consumer_name", "idempotency_key", name="uq_infra_consumer_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    consumer_name: Mapped[str] = mapped_column(String(120), index=True)
    event_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), index=True)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)


class InfraDeadLetterRecord(TimestampMixin, Base):
    __tablename__ = "infra_dead_letter_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), index=True)
    consumer_name: Mapped[str] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(64), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    replay_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    last_failed_at: Mapped[datetime] = mapped_column(default=utcnow)
    replayed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SearchIndexDocument(TimestampMixin, Base):
    __tablename__ = "search_index_documents"
    __table_args__ = (
        UniqueConstraint("source_table", "source_id", name="uq_search_source_document"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_table: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str | None] = mapped_column(String(180), nullable=True)
    body: Mapped[str] = mapped_column(Text, default="")
    preview_text: Mapped[str] = mapped_column(String(280), default="")
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    embedding: Mapped[list[float]] = mapped_column(JSON, default=list)
    lexeme_text: Mapped[str] = mapped_column(Text, default="")
    source_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    index_version: Mapped[int] = mapped_column(Integer, default=1)
    explanation: Mapped[dict] = mapped_column(JSON, default=dict)


class GraphReadModelNode(TimestampMixin, Base):
    __tablename__ = "graph_read_model_nodes"
    __table_args__ = (
        UniqueConstraint("source_node_id", name="uq_graph_read_model_source_node"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_node_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str | None] = mapped_column(String(180), nullable=True)
    preview_text: Mapped[str] = mapped_column(String(280), default="")
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    cluster_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    degree: Mapped[int] = mapped_column(Integer, default=0)
    position_x: Mapped[float] = mapped_column(Float, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, default=0.0)
    source_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    projection_version: Mapped[str] = mapped_column(String(64), index=True)
    derived_from: Mapped[dict] = mapped_column(JSON, default=dict)


class GraphReadModelEdge(TimestampMixin, Base):
    __tablename__ = "graph_read_model_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_edge_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    source_node_id: Mapped[str] = mapped_column(String(64), index=True)
    target_node_id: Mapped[str] = mapped_column(String(64), index=True)
    edge_type: Mapped[str] = mapped_column(String(32), index=True)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[dict] = mapped_column(JSON, default=dict)
    projection_version: Mapped[str] = mapped_column(String(64), index=True)


class GraphProjectionRun(TimestampMixin, Base):
    __tablename__ = "graph_projection_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    rebuild_reason: Mapped[str] = mapped_column(String(120), default="manual")
    source_high_watermark: Mapped[str | None] = mapped_column(String(80), nullable=True)
    projected_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
