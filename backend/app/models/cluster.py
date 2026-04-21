from __future__ import annotations

import uuid

from sqlalchemy import Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Cluster(TimestampMixin, Base):
    __tablename__ = "clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(120))
    color: Mapped[str] = mapped_column(String(16))
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    thought_count: Mapped[int] = mapped_column(default=0)
    trend: Mapped[str] = mapped_column(String(32), default="stable")
    dominant_themes: Mapped[list[str]] = mapped_column(JSON, default=list)
    emotion_distribution: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)

