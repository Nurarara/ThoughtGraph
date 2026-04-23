from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.thought import Thought
from app.models.user import User
from app.schemas.friendship import FriendResonanceRead
from app.services.text_analysis import cosine_similarity


def _topic_overlap(source_thoughts: list[Thought], target_thoughts: list[Thought]) -> tuple[float, list[str]]:
    source_topics = Counter(topic for thought in source_thoughts for topic in thought.topics)
    target_topics = Counter(topic for thought in target_thoughts for topic in thought.topics)
    if not source_topics or not target_topics:
        return 0.0, []

    shared = {
        topic: min(source_topics[topic], target_topics[topic])
        for topic in source_topics
        if topic in target_topics
    }
    total = max(sum(source_topics.values()), sum(target_topics.values()), 1)
    overlap = sum(shared.values()) / total
    shared_topics = [
        topic.replace("_", " ").title()
        for topic, _ in sorted(shared.items(), key=lambda item: item[1], reverse=True)[:3]
    ]
    return overlap, shared_topics


def _semantic_overlap(source_thoughts: list[Thought], target_thoughts: list[Thought]) -> float:
    if not source_thoughts or not target_thoughts:
        return 0.0
    sampled_source = source_thoughts[:24]
    sampled_target = target_thoughts[:24]
    scores: list[float] = []
    for source in sampled_source:
        best = max((cosine_similarity(source.vector, target.vector) for target in sampled_target), default=0.0)
        if best >= 0.24:
            scores.append(best)
    if not scores:
        return 0.0
    return sum(scores) / max(len(sampled_source), 1)


def _post_overlap(session: Session, source_user_id: str, target_user_id: str, allow_friend_visibility: bool) -> float:
    source_clusters = Counter(
        session.scalars(
            select(Post.cluster_key).where(Post.user_id == source_user_id)
        )
    )
    target_stmt = select(Post.cluster_key).where(Post.user_id == target_user_id, Post.visibility == "public")
    if allow_friend_visibility:
        target_stmt = select(Post.cluster_key).where(
            Post.user_id == target_user_id,
            Post.visibility.in_(("public", "friends")),
        )
    target_clusters = Counter(session.scalars(target_stmt))
    if not source_clusters or not target_clusters:
        return 0.0
    shared = sum(min(source_clusters[key], target_clusters[key]) for key in source_clusters if key in target_clusters)
    total = max(sum(source_clusters.values()), sum(target_clusters.values()), 1)
    return shared / total


def compute_resonance(
    session: Session,
    source_user_id: str,
    target_user_id: str,
    *,
    allow_friend_visibility: bool = False,
) -> FriendResonanceRead:
    source_thoughts = list(
        session.scalars(
            select(Thought).where(Thought.user_id == source_user_id).order_by(Thought.created_at.desc())
        )
    )
    target_stmt = select(Thought).where(Thought.user_id == target_user_id, Thought.visibility == "public")
    target_thoughts = list(session.scalars(target_stmt.order_by(Thought.created_at.desc())))

    topic_score, shared_topics = _topic_overlap(source_thoughts, target_thoughts)
    semantic_score = _semantic_overlap(source_thoughts, target_thoughts)
    post_score = _post_overlap(session, source_user_id, target_user_id, allow_friend_visibility)
    resonance = min(100, max(0, int(round(topic_score * 45 + semantic_score * 40 + post_score * 15))))

    user = session.get(User, target_user_id)
    return FriendResonanceRead(
        user_id=target_user_id,
        display_name=user.display_name if user else target_user_id,
        resonance_score=resonance,
        shared_topics=shared_topics,
    )

