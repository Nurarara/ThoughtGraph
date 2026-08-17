from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Insight(TimestampMixin, Base):
    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    raw_content: Mapped[str] = mapped_column(Text)
    supporting_data: Mapped[dict] = mapped_column(JSON, default=dict)
    stable_key: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    feedback_json: Mapped[dict] = mapped_column(JSON, default=dict)
    feedback_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seen: Mapped[bool] = mapped_column(Boolean, default=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
