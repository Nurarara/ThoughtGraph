from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.social import FriendshipListsRead, SocialRelationshipRead
from app.services.social_service import (
    accepted_friend_ids,
    list_friendships,
    remove_friendship,
    request_friendship,
    respond_friendship,
)


def request_friend(session: Session, requester_id: str, addressee_id: str) -> SocialRelationshipRead:
    return request_friendship(session, requester_id, addressee_id)


def respond_friend(session: Session, current_user_id: str, requester_id: str, accept: bool) -> SocialRelationshipRead:
    return respond_friendship(session, current_user_id, requester_id, accept=accept)


def remove_friend(session: Session, current_user_id: str, target_user_id: str) -> SocialRelationshipRead:
    return remove_friendship(session, current_user_id, target_user_id)


def list_friends(session: Session, current_user_id: str) -> FriendshipListsRead:
    return list_friendships(session, current_user_id)
