from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
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
    session_token_query: Annotated[str | None, Query(alias="session_token")] = None,
) -> str:
    bearer = _extract_bearer(authorization) or session_token_query
    if bearer:
        user = resolve_session_user(session, bearer)
        if user:
            return user.id

    settings = get_settings()
    if settings.auth_mode != "development" or not settings.allow_dev_auth_bypass:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    user_id = settings.default_user_id
    if x_thoughtgraph_user:
        if (
            x_thoughtgraph_user != settings.default_user_id
            and not settings.allow_dev_user_header_impersonation
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="development user impersonation is disabled",
            )
        user_id = x_thoughtgraph_user
    ensure_user_exists(session, user_id)
    return user_id


def require_admin_user_id(
    current_user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
) -> str:
    settings = get_settings()
    user = session.get(User, current_user_id)
    if (
        current_user_id in settings.admin_user_ids
        or bool(user and user.is_admin)
        or (settings.auth_mode == "development" and current_user_id == settings.default_user_id)
    ):
        return current_user_id
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin privileges required")
