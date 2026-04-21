from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Edge(TimestampMixin, Base):
    __tablename__ = "edges"
    __table_args__ = (UniqueConstraint("source_id", "target_id", name="uq_edge_source_target"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("thoughts.id"))
    target_id: Mapped[str] = mapped_column(ForeignKey("thoughts.id"))
    kind: Mapped[str] = mapped_column(String(32), default="semantic_link")
    weight: Mapped[float] = mapped_column(Float, default=0.0)

