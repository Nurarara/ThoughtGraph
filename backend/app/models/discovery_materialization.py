from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DiscoveryMaterialization(TimestampMixin, Base):
    __tablename__ = "discovery_materializations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(32), index=True)
    subject_node_id: Mapped[str | None] = mapped_column(ForeignKey("content_nodes.id"), nullable=True, index=True)
    query_text: Mapped[str | None] = mapped_column(String(280), nullable=True)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    explanation_summary: Mapped[str] = mapped_column(String(500), default="")
    results_json: Mapped[dict] = mapped_column(JSON, default=dict)
