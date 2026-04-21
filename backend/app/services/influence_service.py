from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.follow import Follow
from app.models.influence_score import InfluenceScore
from app.models.thought import Thought
from app.models.user import User
from app.schemas.social import InfluenceScoreRead
from app.services.text_analysis import cosine_similarity


def _topic_overlap(source_thoughts: list[Thought], target_thoughts: list[Thought]) -> float:
    source_topics = Counter(topic for thought in source_thoughts for topic in thought.topics)
    target_topics = Counter(topic for thought in target_thoughts for topic in thought.topics)
    if not source_topics or not target_topics:
        return 0.0
    shared = sum(min(source_topics[topic], target_topics[topic]) for topic in source_topics if topic in target_topics)
    total = max(sum(source_topics.values()), sum(target_topics.values()), 1)
    return round(shared / total, 4)


def _render_summary(target_name: str, score: float, edge_count: int, cluster_overlap: float, reply_count: int) -> str:
    tone = "quiet but real" if score < 0.45 else "meaningful" if score < 0.7 else "strong"
    return (
        f"{target_name} is a {tone} influence: {edge_count} cross-links, "
        f"{int(cluster_overlap * 100)}% topic overlap, {reply_count} replies."
    )


def compute_influence_pair(
    session: Session,
    user_id: str,
    target_user_id: str,
    *,
    create_milestone: bool = False,
) -> tuple[InfluenceScoreRead, bool]:
    source_thoughts = list(
        session.scalars(select(Thought).where(Thought.user_id == user_id).order_by(Thought.created_at.desc()))
    )
    target_thoughts = list(
        session.scalars(
            select(Thought)
            .where(Thought.user_id == target_user_id, Thought.visibility == "public")
            .order_by(Thought.created_at.desc())
        )
    )
    target = session.get(User, target_user_id)
    target_name = target.display_name if target else target_user_id

    if not source_thoughts or not target_thoughts:
        score = 0.0
        edge_count = 0
        cluster_overlap = 0.0
        reply_count = 0
    else:
        edge_count = 0
        weighted_similarity = 0.0
        for source in source_thoughts[:40]:
            best = 0.0
            for target_thought in target_thoughts[:40]:
                if target_thought.created_at > source.created_at:
                    continue
                best = max(best, cosine_similarity(source.vector, target_thought.vector))
            if best >= 0.3:
                weighted_similarity += best
                edge_count += 1
        reply_count = sum(1 for thought in source_thoughts if thought.reply_to_user_id == target_user_id)
        cluster_overlap = _topic_overlap(source_thoughts[:40], target_thoughts[:40])
        similarity_component = (weighted_similarity / edge_count) if edge_count else 0.0
        score = round(min(1.0, similarity_component * 0.65 + cluster_overlap * 0.2 + min(reply_count, 5) * 0.05), 4)

    summary = _render_summary(target_name, score, edge_count, cluster_overlap, reply_count)
    existing = session.scalar(
        select(InfluenceScore).where(
            InfluenceScore.user_id == user_id,
            InfluenceScore.target_user_id == target_user_id,
        )
    )
    previous_score = existing.score if existing else 0.0
    model = existing or InfluenceScore(user_id=user_id, target_user_id=target_user_id)
    model.score = score
    model.edge_count = edge_count
    model.cluster_overlap = cluster_overlap
    model.reply_count = reply_count
    model.summary = summary
    session.add(model)
    session.commit()
    session.refresh(model)

    return (
        InfluenceScoreRead(
            user_id=user_id,
            target_user_id=target_user_id,
            target_display_name=target_name,
            score=model.score,
            edge_count=model.edge_count,
            cluster_overlap=model.cluster_overlap,
            reply_count=model.reply_count,
            summary=model.summary,
            computed_at=model.updated_at,
        ),
        create_milestone and score >= 0.65 and previous_score < 0.65,
    )


def list_influence_scores(session: Session, user_id: str) -> list[InfluenceScoreRead]:
    target_ids = set(session.scalars(select(Follow.following_id).where(Follow.follower_id == user_id)))
    target_ids.update(
        thought.reply_to_user_id
        for thought in session.scalars(select(Thought).where(Thought.user_id == user_id))
        if thought.reply_to_user_id
    )
    payload = [compute_influence_pair(session, user_id, target_id)[0] for target_id in sorted(target_ids)]
    return sorted(payload, key=lambda item: item.score, reverse=True)
