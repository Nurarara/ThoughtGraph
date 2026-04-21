from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: str
    type: str
    actor_id: str | None
    actor_display_name: str | None
    thought_id: str | None
    content: str
    read: bool
    created_at: datetime


class NotificationUpdate(BaseModel):
    read: bool
