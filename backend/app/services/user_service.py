from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.content_node import ContentNode
from app.models.node_cluster import NodeCluster
from app.models.user import User
from app.schemas.user import UserProfileRead, UserProfileUpdate


DEFAULT_NOTIFICATION_PREFS = {
    "email_weekly_report": False,
    "email_new_follower": False,
    "push_replies": False,
}


def ensure_user_exists(session: Session, user_id: str, display_name: str | None = None) -> User:
    user = session.get(User, user_id)
    if user is not None:
        return user

    user = User(
        id=user_id,
        display_name=display_name or user_id.replace("-", " ").title(),
        bio="",
        is_public=True,
        notification_prefs=DEFAULT_NOTIFICATION_PREFS.copy(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_profile(session: Session, user_id: str) -> UserProfileRead:
    user = ensure_user_exists(session, user_id)
    node_count = session.scalar(
        select(func.count()).select_from(ContentNode).where(ContentNode.user_id == user_id)
    ) or 0
    cluster_count = session.scalar(
        select(func.count()).select_from(NodeCluster).where(NodeCluster.user_id == user_id)
    ) or 0
    top_clusters = _top_clusters(session, user_id)
    return UserProfileRead(
        id=user.id,
        display_name=user.display_name,
        bio=user.bio,
        is_public=user.is_public,
        onboarding_v2_completed=user.onboarding_v2_completed,
        node_count=node_count,
        cluster_count=cluster_count,
        top_clusters=top_clusters,
        follower_count=user.follower_count,
        following_count=user.following_count,
        created_at=user.created_at,
    )


def update_user_profile(session: Session, user_id: str, payload: UserProfileUpdate) -> UserProfileRead:
    user = ensure_user_exists(session, user_id)
    for field in ("display_name", "bio", "is_public", "onboarding_v2_completed"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return get_user_profile(session, user_id)


def _top_clusters(session: Session, user_id: str) -> list[str]:
    nodes = list(session.scalars(select(ContentNode.cluster_id).where(ContentNode.user_id == user_id)))
    cluster_ids = [cluster_id for cluster_id in nodes if cluster_id]
    if not cluster_ids:
        return []
    counts = Counter(cluster_ids)
    labels = {
        cluster.id: cluster.label
        for cluster in session.scalars(select(NodeCluster).where(NodeCluster.user_id == user_id))
    }
    return [labels[cluster_id] for cluster_id, _ in counts.most_common(3) if cluster_id in labels]
