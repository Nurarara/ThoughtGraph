from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.friendship import FriendRequestCreate, FriendsListResponse, FriendSummary
from app.services.friendship_service import (
    list_friends,
    request_friend,
    respond_friend,
    suggest_friends,
)

router = APIRouter(prefix="/friends")


@router.get("/", response_model=FriendsListResponse)
def get_friends(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> FriendsListResponse:
    return list_friends(session, current_user_id)


@router.post("/request", response_model=FriendSummary)
def create_request(
    payload: FriendRequestCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> FriendSummary:
    try:
        return request_friend(session, current_user_id, payload.user_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/suggestions", response_model=list[FriendSummary])
def suggestions(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> list[FriendSummary]:
    return suggest_friends(session, current_user_id)


@router.post("/{user_id}/accept", response_model=FriendSummary)
def accept(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> FriendSummary:
    result = respond_friend(session, current_user_id, user_id, accept=True)
    if result is None:
        raise HTTPException(status_code=404, detail="request not found")
    return result


@router.post("/{user_id}/decline", response_model=FriendSummary)
def decline(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> FriendSummary:
    result = respond_friend(session, current_user_id, user_id, accept=False)
    if result is None:
        raise HTTPException(status_code=404, detail="request not found")
    return result
