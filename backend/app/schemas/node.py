from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator


class MediaInput(BaseModel):
    asset_id: str | None = None
    url: HttpUrl | None = None
    filename: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=120)
    size_bytes: int | None = Field(default=None, ge=1)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)


class NodeCreate(BaseModel):
    kind: str = Field(pattern="^(thought|image|video|link)$")
    title: str | None = Field(default=None, max_length=160)
    content_text: str | None = Field(default=None, max_length=4000)
    visibility: str = Field(default="private", pattern="^(private|friends|public)$")
    link_url: HttpUrl | None = None
    media: MediaInput | None = None
    reply_to_node_id: str | None = None
    quote_of_node_id: str | None = None

    @field_validator("content_text")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class NodeRead(BaseModel):
    id: str
    kind: str
    title: str | None
    content_text: str
    preview_text: str
    visibility: str
    created_at: datetime
    updated_at: datetime
    topics: list[str]
    cluster_id: str | None
    cluster_label: str | None
    cluster_color: str | None
    connection_count: int
    author_id: str
    author_display_name: str | None
    media_asset_id: str | None
    media_kind: str | None
    media_status: str | None
    thumbnail_url: str | None
    playback_url: str | None
    duration_seconds: float | None
    media_url: str | None
    link_url: str | None
    reply_to_node_id: str | None
    quote_of_node_id: str | None
    metadata_json: dict = Field(default_factory=dict)


class NodeListResponse(BaseModel):
    items: list[NodeRead]


class NodeThreadResponse(BaseModel):
    root: NodeRead
    replies: list[NodeRead]
    quoted_node: NodeRead | None = None
