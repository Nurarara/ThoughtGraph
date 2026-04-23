from __future__ import annotations

from collections import Counter

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.cluster import Cluster
from app.models.friendship import Friendship
from app.models.post import Post
from app.models.thought import Thought
from app.models.user import User
from app.schemas.profile_summary import ProfileSummaryPost, ProfileSummaryResponse
from app.services.friendship_service import accepted_friend_ids
from app.services.resonance_service import compute_resonance


def _public_top_clusters(session: Session, user_id: str) -> list[str]:
    rows = list(
        session.scalars(
            select(Thought.cluster_id).where(
                Thought.user_id == user_id, Thought.visibility == "public"
            )
        )
    )
    post_clusters = list(
        session.scalars(
            select(Post.cluster_key).where(
                Post.user_id == user_id,
                or_(Post.visibility == "public", Post.visibility == "friends"),
            )
        )
    )
    counter: Counter[str] = Counter(post_clusters)
    labels = {
        cluster.id: cluster.label
        for cluster in session.scalars(select(Cluster).where(Cluster.user_id == user_id))
    }
    for cluster_id in rows:
        if cluster_id and cluster_id in labels:
            counter[labels[cluster_id].lower()] += 1
    return [name.title() for name, _ in counter.most_common(3)]


def _friend_status(session: Session, viewer_id: str, target_id: str) -> str:
    if viewer_id == target_id:
        return "self"
    record = session.scalar(
        select(Friendship).where(
            or_(
                (Friendship.requester_id == viewer_id) & (Friendship.addressee_id == target_id),
                (Friendship.requester_id == target_id) & (Friendship.addressee_id == viewer_id),
            )
        )
    )
    if record is None:
        return "none"
    if record.status == "accepted":
        return "friends"
    if record.status == "pending":
        if record.requester_id == viewer_id:
            return "outgoing"
        return "incoming"
    return record.status


def get_profile_summary(
    session: Session, viewer_id: str, target_id: str
) -> ProfileSummaryResponse | None:
    target = session.get(User, target_id)
    if target is None:
        return None
    status = _friend_status(session, viewer_id, target_id)
    is_self = viewer_id == target_id

    viewer_friends = set(accepted_friend_ids(session, viewer_id))
    target_friends = set(accepted_friend_ids(session, target_id))
    mutual = len(viewer_friends & target_friends) if not is_self else 0

    visibility_allowed: list[str] = ["public"]
    if is_self:
        visibility_allowed.extend(["friends", "private"])
    elif status == "friends":
        visibility_allowed.append("friends")

    post_query = (
        select(Post)
        .where(Post.user_id == target_id, Post.visibility.in_(visibility_allowed))
        .order_by(Post.created_at.desc())
        .limit(12)
    )
    posts = list(session.scalars(post_query))
    public_post_count = int(
        session.scalar(
            select(func.count())
            .select_from(Post)
            .where(
                Post.user_id == target_id, Post.visibility.in_(visibility_allowed)
            )
        )
        or 0
    )
    resonance_score: int | None = None
    shared_topics: list[str] = []
    if not is_self:
        resonance = compute_resonance(session, viewer_id, target_id, allow_friend_visibility=status == "friends")
        resonance_score = resonance.resonance_score
        shared_topics = resonance.shared_topics

    return ProfileSummaryResponse(
        id=target.id,
        display_name=target.display_name,
        bio=target.bio,
        avatar_url=target.avatar_url,
        top_clusters=_public_top_clusters(session, target_id),
        friend_status=status,
        mutual_friend_count=mutual,
        public_post_count=public_post_count,
        resonance_score=resonance_score,
        shared_topics=shared_topics,
        recent_posts=[
            ProfileSummaryPost(
                id=post.id,
                cluster_key=post.cluster_key,
                caption=post.caption,
                media_url=post.media_url,
                location=post.location,
                created_at=post.created_at,
            )
            for post in posts
        ],
        is_self=is_self,
    )
