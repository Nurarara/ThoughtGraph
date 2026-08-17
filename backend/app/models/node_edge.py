from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NodeEdge(TimestampMixin, Base):
    __tablename__ = "node_edges"
    __table_args__ = (UniqueConstraint("source_id", "target_id", "edge_type", name="uq_node_edge_source_target_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("content_nodes.id"), index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("content_nodes.id"), index=True)
    edge_type: Mapped[str] = mapped_column(String(32), index=True)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[dict] = mapped_column(JSON, default=dict)
