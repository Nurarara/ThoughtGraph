from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserRestriction(TimestampMixin, Base):
    __tablename__ = "user_restrictions"
    __table_args__ = (
        UniqueConstraint("source_user_id", "target_user_id", "kind", name="uq_user_restriction_source_target_kind"),
        CheckConstraint("source_user_id != target_user_id", name="ck_user_restriction_not_self"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
