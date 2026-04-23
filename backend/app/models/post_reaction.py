from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PostReaction(TimestampMixin, Base):
    __tablename__ = "post_reactions"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_post_reaction_per_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    emoji: Mapped[str] = mapped_column(String(8), default="♡")
