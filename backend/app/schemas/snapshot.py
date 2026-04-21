from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SnapshotCreate(BaseModel):
    caption: str = Field(default="", max_length=500)
    is_public: bool = True


class SnapshotRead(BaseModel):
    id: str
    user_id: str
    user_display_name: str
    image_url: str
    thumbnail_url: str | None
    metadata: dict
    caption: str
    is_public: bool
    created_at: datetime

    model_config = {"from_attributes": True}
