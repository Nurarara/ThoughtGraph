from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Thought(TimestampMixin, Base):
    __tablename__ = "thoughts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text)
    emotion: Mapped[str] = mapped_column(String(32), default="neutral")
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    vector: Mapped[list[float]] = mapped_column(JSON, default=list)
    cluster_id: Mapped[str | None] = mapped_column(ForeignKey("clusters.id"), nullable=True)
    connection_count: Mapped[int] = mapped_column(Integer, default=0)
    activity_score: Mapped[int] = mapped_column(Integer, default=1)
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    reply_to_id: Mapped[str | None] = mapped_column(ForeignKey("thoughts.id"), nullable=True)
    reply_to_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
