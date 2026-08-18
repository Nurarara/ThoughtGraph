from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.magic_token import MagicToken
from app.models.session_token import SessionToken
from app.models.user import User
from app.services.user_service import DEFAULT_NOTIFICATION_PREFS

MAGIC_TTL = timedelta(minutes=15)
SESSION_TTL = timedelta(days=30)


def normalize_email(email: str) -> str:
    cleaned = email.strip().casefold()
    if len(cleaned) > 320 or cleaned.count("@") != 1:
        raise ValueError("invalid email")
    local_part, domain = cleaned.rsplit("@", 1)
    if not local_part or not domain or len(local_part) > 64 or len(domain) > 255:
        raise ValueError("invalid email")
    if any(char.isspace() or ord(char) < 33 for char in cleaned):
        raise ValueError("invalid email")
    labels = domain.split(".")
    if len(labels) < 2:
        raise ValueError("invalid email")
    for label in labels:
        if not label or label.startswith("-") or label.endswith("-"):
            raise ValueError("invalid email")
        if not all(char.isalnum() or char == "-" for char in label):
            raise ValueError("invalid email")
    return cleaned


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _derive_user_id(email: str) -> str:
    handle = email.split("@", 1)[0].lower()
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in handle).strip("-") or "user"
    return f"u-{cleaned}-{uuid.uuid4().hex[:6]}"


def _find_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(
        select(User)
        .where(func.lower(User.email) == email)
        .order_by(User.created_at.asc(), User.id.asc())
    )


@dataclass
class IssuedMagicLink:
    token: str
    expires_in_seconds: int


def issue_magic_link(session: Session, email: str) -> IssuedMagicLink:
    normalized_email = normalize_email(email)
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = utcnow() + MAGIC_TTL
    record = MagicToken(
        email=normalized_email,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(record)
    session.commit()
    return IssuedMagicLink(token=raw_token, expires_in_seconds=int(MAGIC_TTL.total_seconds()))


@dataclass
class VerifiedSession:
    session_token: str
    user: User
    is_new_user: bool


def _issue_session(
    session: Session,
    user: User,
    *,
    is_new_user: bool,
    ttl: timedelta = SESSION_TTL,
) -> VerifiedSession:
    raw_session = secrets.token_urlsafe(32)
    session.add(
        SessionToken(
            user_id=user.id,
            token_hash=_hash_token(raw_session),
            expires_at=utcnow() + ttl,
        )
    )
    session.commit()
    session.refresh(user)
    return VerifiedSession(session_token=raw_session, user=user, is_new_user=is_new_user)


def verify_magic_and_issue_session(session: Session, raw_token: str) -> VerifiedSession | None:
    token_hash = _hash_token(raw_token)
    record = session.scalar(select(MagicToken).where(MagicToken.token_hash == token_hash))
    if record is None or record.used_at is not None:
        return None
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone

        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < utcnow():
        return None

    record.used_at = utcnow()
    session.add(record)

    email = normalize_email(record.email)
    user = _find_user_by_email(session, email)
    is_new = False
    if user is None:
        user = User(
            id=_derive_user_id(email),
            email=email,
            display_name=email.split("@", 1)[0].title(),
            bio="",
            is_public=True,
            serendipity_enabled=False,
            notification_prefs=DEFAULT_NOTIFICATION_PREFS.copy(),
        )
        session.add(user)
        is_new = True
    elif user.email != email and session.scalar(select(User).where(User.email == email)) is None:
        user.email = email
        session.add(user)

    return _issue_session(session, user, is_new_user=is_new)


def resolve_session_user(session: Session, raw_token: str) -> User | None:
    token_hash = _hash_token(raw_token)
    record = session.scalar(select(SessionToken).where(SessionToken.token_hash == token_hash))
    if record is None or record.revoked_at is not None:
        return None
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone

        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < utcnow():
        return None
    return session.get(User, record.user_id)


def revoke_session(session: Session, raw_token: str) -> bool:
    token_hash = _hash_token(raw_token)
    record = session.scalar(select(SessionToken).where(SessionToken.token_hash == token_hash))
    if record is None:
        return False
    record.revoked_at = utcnow()
    session.add(record)
    session.commit()
    return True
