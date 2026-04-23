from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _normalize_email(value: str) -> str:
    cleaned = value.strip().lower()
    if "@" not in cleaned or "." not in cleaned.split("@", 1)[-1] or " " in cleaned or len(cleaned) > 320:
        raise ValueError("invalid email")
    return cleaned


class MagicLinkRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return _normalize_email(value)


class MagicLinkResponse(BaseModel):
    email: str
    magic_link: str | None = None
    expires_in_seconds: int


class VerifyRequest(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class VerifyResponse(BaseModel):
    session_token: str
    user_id: str
    display_name: str
    email: str
    is_new_user: bool


class LogoutResponse(BaseModel):
    ok: bool = True
