from __future__ import annotations

from collections import Counter

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.cluster import Cluster
from app.models.edge import Edge
from app.models.follow import Follow
from app.models.graph_snapshot import GraphSnapshot
from app.models.influence_score import InfluenceScore
from app.models.insight import Insight
from app.models.thought import Thought
from app.models.user import User
from app.models.weekly_report import WeeklyReport
from app.schemas.user import (
    NotificationPreferencesUpdate,
    UserProfileRead,
    UserProfileUpdate,
    UserSearchResult,
)


DEFAULT_NOTIFICATION_PREFS = {
    "email_weekly_report": True,
    "email_new_follower": False,
    "push_replies": True,
    "push_insights": True,
    "push_influence_updates": True,
    "push_new_follower": True,
    "push_weekly_report": True,
}


def ensure_user_exists(session: Session, user_id: str, display_name: str | None = None) -> User:
    user = session.get(User, user_id)
    if user:
        return user

    user = User(
        id=user_id,
        display_name=display_name or user_id.replace("-", " ").title(),
        bio="",
        is_public=True,
        serendipity_enabled=False,
        notification_prefs=DEFAULT_NOTIFICATION_PREFS.copy(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _top_clusters(session: Session, user_id: str, public_only: bool = False) -> list[str]:
    thoughts_query = select(Thought.cluster_id).where(Thought.user_id == user_id)
    if public_only:
        thoughts_query = thoughts_query.where(Thought.visibility == "public")

    cluster_ids = [cluster_id for cluster_id in session.scalars(thoughts_query) if cluster_id]
    if not cluster_ids:
        return []

    labels = {
        cluster.id: cluster.label
        for cluster in session.scalars(select(Cluster).where(Cluster.user_id == user_id))
    }
    counts = Counter(cluster_ids)
    return [labels[cluster_id] for cluster_id, _ in counts.most_common(3) if cluster_id in labels]


def get_user_profile(session: Session, user_id: str) -> UserProfileRead:
    user = ensure_user_exists(session, user_id)
    thought_count = session.scalar(select(func.count()).select_from(Thought).where(Thought.user_id == user_id)) or 0
    cluster_count = session.scalar(select(func.count()).select_from(Cluster).where(Cluster.user_id == user_id)) or 0
    return UserProfileRead(
        id=user.id,
        display_name=user.display_name,
        bio=user.bio,
        avatar_url=user.avatar_url,
        is_public=user.is_public,
        follower_count=user.follower_count,
        following_count=user.following_count,
        created_at_public=user.created_at_public,
        serendipity_enabled=user.serendipity_enabled,
        thought_count=thought_count,
        cluster_count=cluster_count,
        top_clusters=_top_clusters(session, user_id),
        notification_prefs={**DEFAULT_NOTIFICATION_PREFS, **(user.notification_prefs or {})},
        onboarding_v2_completed=user.onboarding_v2_completed,
        created_at=user.created_at,
    )


def get_public_user_profile(session: Session, current_user_id: str, user_id: str) -> UserProfileRead:
    user = ensure_user_exists(session, user_id)
    if user.is_public or current_user_id == user_id:
        public_thought_count = (
            session.scalar(
                select(func.count()).select_from(Thought).where(Thought.user_id == user_id, Thought.visibility == "public")
            )
            or 0
        )
        public_cluster_count = len(_top_clusters(session, user_id, public_only=True))
        return UserProfileRead(
            id=user.id,
            display_name=user.display_name,
            bio=user.bio,
            avatar_url=user.avatar_url,
            is_public=user.is_public,
            follower_count=user.follower_count,
            following_count=user.following_count,
            created_at_public=user.created_at_public,
            serendipity_enabled=user.serendipity_enabled if current_user_id == user_id else False,
            thought_count=public_thought_count,
            cluster_count=public_cluster_count,
            top_clusters=_top_clusters(session, user_id, public_only=True),
            notification_prefs={},
            onboarding_v2_completed=user.onboarding_v2_completed if current_user_id == user_id else False,
            created_at=user.created_at if user.created_at_public else None,
        )

    return UserProfileRead(
        id=user.id,
        display_name=user.display_name,
        bio="",
        avatar_url=user.avatar_url,
        is_public=user.is_public,
        follower_count=user.follower_count,
        following_count=user.following_count,
        created_at_public=user.created_at_public,
        serendipity_enabled=False,
        thought_count=0,
        cluster_count=0,
        top_clusters=[],
        notification_prefs={},
        onboarding_v2_completed=False,
        created_at=None,
    )


def update_user_profile(session: Session, user_id: str, payload: UserProfileUpdate) -> UserProfileRead:
    user = ensure_user_exists(session, user_id)
    for field in ("display_name", "bio", "avatar_url", "is_public", "created_at_public"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return get_user_profile(session, user_id)


def update_notification_preferences(
    session: Session,
    user_id: str,
    payload: NotificationPreferencesUpdate,
) -> dict:
    user = ensure_user_exists(session, user_id)
    next_prefs = {**DEFAULT_NOTIFICATION_PREFS, **(user.notification_prefs or {})}
    for key, value in payload.model_dump(exclude_none=True).items():
        next_prefs[key] = value
    user.notification_prefs = next_prefs
    session.add(user)
    session.commit()
    return next_prefs


def update_onboarding_state(session: Session, user_id: str, completed: bool) -> bool:
    user = ensure_user_exists(session, user_id)
    user.onboarding_v2_completed = completed
    session.add(user)
    session.commit()
    return user.onboarding_v2_completed


def update_discovery_settings(session: Session, user_id: str, *, serendipity_enabled: bool) -> bool:
    user = ensure_user_exists(session, user_id)
    user.serendipity_enabled = serendipity_enabled
    session.add(user)
    session.commit()
    return user.serendipity_enabled


def bulk_update_thought_visibility(session: Session, user_id: str, visibility: str) -> int:
    thoughts = list(session.scalars(select(Thought).where(Thought.user_id == user_id)))
    for thought in thoughts:
        thought.visibility = visibility
    session.add_all(thoughts)
    session.commit()
    return len(thoughts)


def export_user_data(session: Session, user_id: str) -> dict:
    profile = get_user_profile(session, user_id)
    thoughts = list(session.scalars(select(Thought).where(Thought.user_id == user_id).order_by(Thought.created_at.asc())))
    follows = {
        "followers": list(session.scalars(select(Follow.follower_id).where(Follow.following_id == user_id))),
        "following": list(session.scalars(select(Follow.following_id).where(Follow.follower_id == user_id))),
    }
    snapshots = list(session.scalars(select(GraphSnapshot).where(GraphSnapshot.user_id == user_id)))
    reports = list(session.scalars(select(WeeklyReport).where(WeeklyReport.user_id == user_id)))
    influence = list(session.scalars(select(InfluenceScore).where(InfluenceScore.user_id == user_id)))
    return {
        "profile": profile.model_dump(),
        "thoughts": [
            {
                "id": thought.id,
                "content": thought.content,
                "topics": thought.topics,
                "emotion": thought.emotion,
                "visibility": thought.visibility,
                "reply_to_id": thought.reply_to_id,
                "created_at": thought.created_at.isoformat(),
            }
            for thought in thoughts
        ],
        "follows": follows,
        "snapshots": [{"id": snapshot.id, "caption": snapshot.caption, "created_at": snapshot.created_at.isoformat()} for snapshot in snapshots],
        "reports": [{"id": report.id, "week_start": report.week_start.isoformat()} for report in reports],
        "influence": [{"target_user_id": row.target_user_id, "score": row.score} for row in influence],
    }


def delete_user_account(session: Session, user_id: str) -> None:
    session.execute(delete(Edge).where(Edge.user_id == user_id))
    session.execute(delete(Cluster).where(Cluster.user_id == user_id))
    session.execute(delete(Insight).where(Insight.user_id == user_id))
    session.execute(delete(GraphSnapshot).where(GraphSnapshot.user_id == user_id))
    session.execute(delete(WeeklyReport).where(WeeklyReport.user_id == user_id))
    session.execute(
        delete(InfluenceScore).where(
            (InfluenceScore.user_id == user_id) | (InfluenceScore.target_user_id == user_id)
        )
    )
    session.execute(delete(Follow).where((Follow.follower_id == user_id) | (Follow.following_id == user_id)))
    session.execute(delete(Thought).where(Thought.user_id == user_id))
    user = session.get(User, user_id)
    if user:
        session.delete(user)
    session.commit()


def search_users(session: Session, current_user_id: str, query: str) -> list[UserSearchResult]:
    normalized = query.strip().lower()
    users = list(session.scalars(select(User).order_by(User.follower_count.desc(), User.display_name.asc())))

    following_ids = set(
        session.scalars(
            select(Follow.following_id).where(Follow.follower_id == current_user_id)
        )
    )

    results: list[UserSearchResult] = []
    for user in users:
        if user.id == current_user_id:
            continue
        if normalized and normalized not in user.display_name.lower():
            continue
        if not user.is_public:
            continue
        results.append(
            UserSearchResult(
                id=user.id,
                display_name=user.display_name,
                bio=user.bio,
                avatar_url=user.avatar_url,
                follower_count=user.follower_count,
                following_count=user.following_count,
                top_clusters=_top_clusters(session, user.id, public_only=True),
                relationship_following=user.id in following_ids,
            )
        )
        if len(results) >= 20:
            break
    return results
