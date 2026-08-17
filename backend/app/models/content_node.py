from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.vector import EmbeddingVector
from app.models.base import Base, TimestampMixin


class ContentNode(TimestampMixin, Base):
    __tablename__ = "content_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    content_text: Mapped[str] = mapped_column(Text, default="")
    preview_text: Mapped[str] = mapped_column(String(280), default="")
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_asset_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"), nullable=True)
    visibility: Mapped[str] = mapped_column(String(24), default="private", index=True)
    status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVector(256), default=list)
    cluster_id: Mapped[str | None] = mapped_column(ForeignKey("node_clusters.id"), nullable=True, index=True)
    connection_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_to_node_id: Mapped[str | None] = mapped_column(ForeignKey("content_nodes.id"), nullable=True, index=True)
    quote_of_node_id: Mapped[str | None] = mapped_column(ForeignKey("content_nodes.id"), nullable=True, index=True)
