from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class WeeklyReportRead(BaseModel):
    id: str
    user_id: str
    user_display_name: str
    week_start: date
    week_end: date
    content: dict
    image_url: str | None
    seen: bool
    created_at: datetime

    model_config = {"from_attributes": True}
