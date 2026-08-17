from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrustClaim(TimestampMixin, Base):
    __tablename__ = "trust_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id: Mapped[str | None] = mapped_column(ForeignKey("content_nodes.id"), nullable=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    canonical_text: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified", index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    current_rationale_version: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class TrustSource(TimestampMixin, Base):
    __tablename__ = "trust_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), default="url", index=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    credibility_score: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ClaimEvidence(TimestampMixin, Base):
    __tablename__ = "claim_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id: Mapped[str] = mapped_column(ForeignKey("trust_claims.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("trust_sources.id"), nullable=True, index=True)
    node_id: Mapped[str | None] = mapped_column(ForeignKey("content_nodes.id"), nullable=True, index=True)
    added_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(32), default="source", index=True)
    stance: Mapped[str] = mapped_column(String(24), default="context", index=True)
    summary: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class TrustRationaleVersion(TimestampMixin, Base):
    __tablename__ = "trust_rationale_versions"
    __table_args__ = (UniqueConstraint("claim_id", "version", name="uq_trust_rationale_claim_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id: Mapped[str] = mapped_column(ForeignKey("trust_claims.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    verification_status: Mapped[str] = mapped_column(String(32), index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    rationale_text: Mapped[str] = mapped_column(Text)
    factors_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ProvenanceSnapshot(TimestampMixin, Base):
    __tablename__ = "provenance_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("trust_claims.id"), nullable=True, index=True)
    node_id: Mapped[str | None] = mapped_column(ForeignKey("content_nodes.id"), nullable=True, index=True)
    assembled_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    summary: Mapped[str] = mapped_column(Text)
    graph_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ModerationReport(TimestampMixin, Base):
    __tablename__ = "moderation_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject_type: Mapped[str] = mapped_column(String(32), index=True)
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(String(64), index=True)
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ModerationEventLog(TimestampMixin, Base):
    __tablename__ = "moderation_event_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str | None] = mapped_column(ForeignKey("moderation_reports.id"), nullable=True, index=True)
    subject_type: Mapped[str] = mapped_column(String(32), index=True)
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    from_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ModerationEnforcementState(TimestampMixin, Base):
    __tablename__ = "moderation_enforcement_states"
    __table_args__ = (UniqueConstraint("subject_type", "subject_id", name="uq_moderation_subject_state"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_type: Mapped[str] = mapped_column(String(32), index=True)
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), default="no_action", index=True)
    blocked_from_discovery: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    enforced_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
