from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.social import SocialProfileRead
from app.schemas.user import UserProfileRead, UserProfileUpdate, UserSearchResult
from app.services.event_service import emit_event
from app.services.social_service import get_profile, search_users
from app.services.user_service import get_user_profile, update_user_profile

router = APIRouter(prefix="/users")


@router.get("/me", response_model=UserProfileRead)
def get_me(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> UserProfileRead:
    return get_user_profile(session, current_user_id)


@router.patch("/me", response_model=UserProfileRead)
def update_me(
    payload: UserProfileUpdate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> UserProfileRead:
    profile = update_user_profile(session, current_user_id, payload)
    emit_event(
        session,
        event_type="profile_updated",
        aggregate_type="profile",
        aggregate_id=current_user_id,
        actor_id=current_user_id,
        payload=payload.model_dump(exclude_none=True),
    )
    session.commit()
    return profile


@router.get("/search", response_model=list[UserSearchResult])
def search(
    q: str = "",
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> list[UserSearchResult]:
    return search_users(session, current_user_id, q)


@router.get("/{user_id}", response_model=SocialProfileRead)
def get_user(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SocialProfileRead:
    try:
        return get_profile(session, current_user_id, user_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
