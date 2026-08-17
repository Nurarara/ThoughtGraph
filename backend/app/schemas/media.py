from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MediaUploadCreate(BaseModel):
    kind: str = Field(pattern="^(image|video)$")
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=1, le=1_500_000_000)


class MediaUploadTarget(BaseModel):
    method: str = "PUT"
    upload_url: str
    expires_at: datetime
    headers: dict[str, str] = Field(default_factory=dict)


class MediaRenditionRead(BaseModel):
    label: str
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    url: str
    size_bytes: int | None = None


class MediaAssetRead(BaseModel):
    id: str
    kind: str
    source_kind: str
    filename: str | None
    mime_type: str | None
    size_bytes: int | None
    width: int | None
    height: int | None
    duration_seconds: float | None
    status: str
    moderation_status: str
    original_url: str | None
    playback_url: str | None
    thumbnail_url: str | None
    renditions: list[MediaRenditionRead] = Field(default_factory=list)
    error_message: str | None = None
    metadata_json: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class MediaUploadCreateResponse(BaseModel):
    asset: MediaAssetRead
    upload: MediaUploadTarget
