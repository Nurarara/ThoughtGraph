from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import (
    LogoutResponse,
    MagicLinkRequest,
    MagicLinkResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.services.auth_service import (
    issue_magic_link,
    revoke_session,
    verify_magic_and_issue_session,
)

router = APIRouter(prefix="/auth")


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


@router.post("/request-link", response_model=MagicLinkResponse)
def request_link(
    payload: MagicLinkRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> MagicLinkResponse:
    issued = issue_magic_link(session, payload.email)
    base = str(request.base_url).rstrip("/")
    link = f"{base}/api/auth/verify?token={issued.token}"
    return MagicLinkResponse(
        email=payload.email,
        magic_link=link,
        expires_in_seconds=issued.expires_in_seconds,
    )


@router.post("/verify", response_model=VerifyResponse)
def verify(
    payload: VerifyRequest,
    session: Session = Depends(get_db),
) -> VerifyResponse:
    verified = verify_magic_and_issue_session(session, payload.token)
    if verified is None:
        raise HTTPException(status_code=400, detail="invalid or expired magic token")
    return VerifyResponse(
        session_token=verified.session_token,
        user_id=verified.user.id,
        display_name=verified.user.display_name,
        email=verified.user.email or "",
        is_new_user=verified.is_new_user,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db),
) -> LogoutResponse:
    token = _extract_bearer(authorization)
    if token:
        revoke_session(session, token)
    return LogoutResponse(ok=True)
