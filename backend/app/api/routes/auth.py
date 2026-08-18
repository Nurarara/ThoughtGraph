from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth import (
    LogoutResponse,
    MagicLinkRequest,
    MagicLinkResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.services.email_service import email_provider_configured, send_magic_link_email
from app.services.auth_service import (
    issue_guest_session,
    issue_magic_link,
    revoke_session,
    verify_magic_and_issue_session,
)

router = APIRouter(prefix="/auth")


@router.post("/guest", response_model=VerifyResponse)
def enter_as_guest(session: Session = Depends(get_db)) -> VerifyResponse:
    settings = get_settings()
    if settings.auth_mode != "development" or not settings.allow_guest_access:
        raise HTTPException(status_code=403, detail="guest preview access is disabled")
    issued = issue_guest_session(session)
    return VerifyResponse(
        session_token=issued.session_token,
        user_id=issued.user.id,
        display_name=issued.user.display_name,
        email="",
        is_new_user=True,
    )


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
    settings = get_settings()
    if settings.auth_mode == "production" and not email_provider_configured(settings):
        raise HTTPException(status_code=503, detail="email delivery is not configured")
    issued = issue_magic_link(session, payload.email)
    base = str(request.base_url).rstrip("/")
    link = f"{base}/api/auth/verify?token={issued.token}"
    if email_provider_configured(settings):
        try:
            send_magic_link_email(payload.email, link)
        except Exception as err:
            raise HTTPException(status_code=502, detail="failed to send sign-in email") from err
    return MagicLinkResponse(
        email=payload.email,
        magic_link=link if settings.auth_mode != "production" else None,
        expires_in_seconds=issued.expires_in_seconds,
    )


@router.get("/verify")
def verify_link_redirect(token: str) -> RedirectResponse:
    target = f"{get_settings().app_url.rstrip('/')}/?token={quote(token)}"
    return RedirectResponse(url=target, status_code=307)


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
