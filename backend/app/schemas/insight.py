from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class InsightRead(BaseModel):
    id: str
    kind: str
    content: str
    raw_content: str
    supporting_data: dict
    seen: bool
    dismissed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InsightUpdate(BaseModel):
    seen: bool | None = None
    dismissed: bool | None = None

