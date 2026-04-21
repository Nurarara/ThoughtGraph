from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services.user_service import ensure_user_exists


def get_current_user_id(
    session: Session = Depends(get_db),
    x_thoughtgraph_user: Annotated[str | None, Header(alias="X-ThoughtGraph-User")] = None,
) -> str:
    settings = get_settings()
    user_id = x_thoughtgraph_user or settings.default_user_id
    ensure_user_exists(session, user_id)
    return user_id

