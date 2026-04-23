from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.social import (
    FollowListItem,
    FollowState,
    InfluenceScoreRead,
    ReplyThreadRead,
    SerendipityResponse,
    SocialFeedItem,
    SocialRelationship,
    TrendingClusterRead,
)
from app.services.influence_service import compute_influence_pair, list_influence_scores
from app.services.social_service import (
    follow_user,
    get_reply_thread,
    get_relationship,
    get_serendipity_matches,
    get_suggested_users,
    get_trending_clusters,
    list_followers,
    list_social_feed,
    list_following,
    unfollow_user,
)

router = APIRouter(prefix="/social")


@router.post("/follow/{user_id}", response_model=FollowState)
async def follow(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> FollowState:
    await follow_user(session, current_user_id, user_id)
    return FollowState(following=True)


@router.delete("/follow/{user_id}", response_model=FollowState)
def unfollow(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> FollowState:
    unfollow_user(session, current_user_id, user_id)
    return FollowState(following=False)


@router.get("/followers/{user_id}", response_model=list[FollowListItem])
def followers(user_id: str, session: Session = Depends(get_db)) -> list[FollowListItem]:
    return list_followers(session, user_id)


@router.get("/following/{user_id}", response_model=list[FollowListItem])
def following(user_id: str, session: Session = Depends(get_db)) -> list[FollowListItem]:
    return list_following(session, user_id)


@router.get("/relationship/{user_id}", response_model=SocialRelationship)
def relationship(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SocialRelationship:
    return get_relationship(session, current_user_id, user_id)


@router.get("/replies/{thought_id}", response_model=ReplyThreadRead)
def reply_thread(
    thought_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> ReplyThreadRead:
    return get_reply_thread(session, current_user_id, thought_id)


@router.get("/feed", response_model=list[SocialFeedItem])
def feed(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> list[SocialFeedItem]:
    return list_social_feed(session, current_user_id)


@router.get("/influence", response_model=list[InfluenceScoreRead])
def influence(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> list[InfluenceScoreRead]:
    return list_influence_scores(session, current_user_id)


@router.get("/influence/{user_id}", response_model=InfluenceScoreRead)
def influence_for_user(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> InfluenceScoreRead:
    return compute_influence_pair(session, current_user_id, user_id)[0]


@router.get("/trending-clusters", response_model=list[TrendingClusterRead])
def trending_clusters(session: Session = Depends(get_db)) -> list[TrendingClusterRead]:
    return get_trending_clusters(session)


@router.get("/suggested-users", response_model=list[FollowListItem])
def suggested_users(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> list[FollowListItem]:
    return get_suggested_users(session, current_user_id)


@router.get("/serendipity", response_model=SerendipityResponse)
def serendipity(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SerendipityResponse:
    return get_serendipity_matches(session, current_user_id)
