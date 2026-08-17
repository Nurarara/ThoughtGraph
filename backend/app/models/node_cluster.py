from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NodeCluster(TimestampMixin, Base):
    __tablename__ = "node_clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(160))
    color: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text, default="")
    centroid_hint: Mapped[dict] = mapped_column(JSON, default=dict)
    node_count: Mapped[int] = mapped_column(default=0)
    density_score: Mapped[float] = mapped_column(Float, default=0.0)
    dominant_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
