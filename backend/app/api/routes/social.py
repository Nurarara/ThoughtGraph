from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.social import FollowStateRead, RestrictionUpdate, SocialNeighborhoodResponse, SocialRelationshipRead
from app.services.social_service import (
    follow_user,
    get_relationship,
    social_neighborhood,
    set_restriction,
    unfollow_user,
)

router = APIRouter(prefix="/social")


@router.post("/follow/{user_id}", response_model=SocialRelationshipRead)
def follow(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SocialRelationshipRead:
    try:
        return follow_user(session, current_user_id, user_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete("/follow/{user_id}", response_model=SocialRelationshipRead)
def unfollow(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SocialRelationshipRead:
    return unfollow_user(session, current_user_id, user_id)


@router.get("/relationship/{user_id}", response_model=SocialRelationshipRead)
def relationship(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SocialRelationshipRead:
    return get_relationship(session, current_user_id, user_id)


@router.post("/restrictions/{user_id}", response_model=SocialRelationshipRead)
def update_restriction(
    user_id: str,
    payload: RestrictionUpdate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SocialRelationshipRead:
    try:
        return set_restriction(session, current_user_id, user_id, payload.kind, payload.active)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/neighborhood", response_model=SocialNeighborhoodResponse)
def neighborhood(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SocialNeighborhoodResponse:
    return social_neighborhood(session, current_user_id)
