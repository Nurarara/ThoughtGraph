from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models.post import Post
from app.models.user import User
from app.schemas.friend_overlay import FriendGhostNode, FriendOverlayResponse
from app.schemas.graph import GraphResponse
from app.services.friendship_service import accepted_friend_ids
from app.services.graph_pipeline import get_graph_response_with_options

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/graph", response_model=GraphResponse)
def get_graph(
    social: bool = False,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> GraphResponse:
    return get_graph_response_with_options(session, current_user_id, social=social)


@router.get("/graph/friends-overlay", response_model=FriendOverlayResponse)
def friends_overlay(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> FriendOverlayResponse:
    friend_ids = accepted_friend_ids(session, current_user_id)
    if not friend_ids:
        return FriendOverlayResponse(nodes=[])
    users = {
        user.id: user
        for user in session.scalars(select(User).where(User.id.in_(friend_ids)))
    }
    rows = session.execute(
        select(Post.user_id, Post.cluster_key).where(
            Post.user_id.in_(friend_ids),
            Post.visibility.in_(("public", "friends")),
        )
    ).all()
    counts: Counter[tuple[str, str]] = Counter((uid, ck) for uid, ck in rows)
    nodes: list[FriendGhostNode] = []
    for (user_id, cluster_key), count in counts.items():
        user = users.get(user_id)
        if user is None:
            continue
        nodes.append(
            FriendGhostNode(
                id=f"{user_id}:{cluster_key}",
                display_name=user.display_name,
                cluster_key=cluster_key,
                post_count=count,
            )
        )
    return FriendOverlayResponse(nodes=nodes)
