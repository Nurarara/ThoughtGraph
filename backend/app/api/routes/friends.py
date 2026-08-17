from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.social import FriendRequestCreate, FriendshipListsRead, SocialRelationshipRead
from app.services.friendship_service import list_friends, remove_friend, request_friend, respond_friend

router = APIRouter(prefix="/friends")


@router.get("", response_model=FriendshipListsRead)
def get_friends(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> FriendshipListsRead:
    return list_friends(session, current_user_id)


@router.post("/request", response_model=SocialRelationshipRead)
def request_friend_route(
    payload: FriendRequestCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SocialRelationshipRead:
    try:
        return request_friend(session, current_user_id, payload.user_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/{user_id}/accept", response_model=SocialRelationshipRead)
def accept_friend_route(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SocialRelationshipRead:
    try:
        return respond_friend(session, current_user_id, user_id, accept=True)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.post("/{user_id}/decline", response_model=SocialRelationshipRead)
def decline_friend_route(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SocialRelationshipRead:
    try:
        return respond_friend(session, current_user_id, user_id, accept=False)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.delete("/{user_id}", response_model=SocialRelationshipRead)
def remove_friend_route(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SocialRelationshipRead:
    return remove_friend(session, current_user_id, user_id)
