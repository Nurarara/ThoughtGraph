from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services.auth_service import resolve_session_user
from app.services.user_service import ensure_user_exists


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_current_user_id(
    session: Session = Depends(get_db),
    authorization: Annotated[str | None, Header()] = None,
    x_thoughtgraph_user: Annotated[str | None, Header(alias="X-ThoughtGraph-User")] = None,
) -> str:
    bearer = _extract_bearer(authorization)
    if bearer:
        user = resolve_session_user(session, bearer)
        if user:
            return user.id

    settings = get_settings()
    user_id = x_thoughtgraph_user or settings.default_user_id
    ensure_user_exists(session, user_id)
    return user_id
