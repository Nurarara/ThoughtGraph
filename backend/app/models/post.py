from __future__ import annotations

import uuid

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Post(TimestampMixin, Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    cluster_key: Mapped[str] = mapped_column(String(32), index=True)
    caption: Mapped[str] = mapped_column(Text, default="")
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="friends")
