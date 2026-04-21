from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class InfluenceScore(TimestampMixin, Base):
    __tablename__ = "influence_scores"
    __table_args__ = (UniqueConstraint("user_id", "target_user_id", name="uq_influence_pair"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    edge_count: Mapped[int] = mapped_column(default=0)
    cluster_overlap: Mapped[float] = mapped_column(Float, default=0.0)
    reply_count: Mapped[int] = mapped_column(default=0)
    summary: Mapped[str] = mapped_column(String(300), default="")
