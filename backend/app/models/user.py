from __future__ import annotations

from sqlalchemy import Boolean, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    bio: Mapped[str] = mapped_column(Text, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    follower_count: Mapped[int] = mapped_column(default=0)
    following_count: Mapped[int] = mapped_column(default=0)
    created_at_public: Mapped[bool] = mapped_column(Boolean, default=True)
    serendipity_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notification_prefs: Mapped[dict] = mapped_column(JSON, default=dict)
    onboarding_v2_completed: Mapped[bool] = mapped_column(Boolean, default=False)
