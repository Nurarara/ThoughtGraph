from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.cluster import Cluster
from app.models.edge import Edge
from app.models.follow import Follow
from app.models.thought import Thought
from app.models.user import User
from app.schemas.graph import GraphAuthor, GraphCluster, GraphEdge, GraphNode, GraphResponse
from app.services.text_analysis import (
    calculate_activity_score,
    cosine_similarity,
    embed_text,
    infer_emotion,
    infer_topics,
    summarize_preview,
)


PALETTE = [
    "#7c5bf5",
    "#4a8eff",
    "#22d3ee",
    "#f471b5",
    "#34d399",
    "#fb923c",
]


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def analyze_thought_content(content: str) -> tuple[list[float], str, list[str]]:
    vector = embed_text(content)
    emotion = infer_emotion(content)
    topics = infer_topics(content)
    return vector, emotion, topics


def _build_edges(thoughts: list[Thought], threshold: float, limit: int) -> list[tuple[str, str, float]]:
    edges: list[tuple[str, str, float]] = []
    for index, thought in enumerate(thoughts):
        scored = []
        for candidate in thoughts[index + 1 :]:
            similarity = cosine_similarity(thought.vector, candidate.vector)
            if similarity >= threshold:
                scored.append((candidate.id, similarity))
        scored.sort(key=lambda item: item[1], reverse=True)
        for target_id, score in scored[:limit]:
            edges.append((thought.id, target_id, round(score, 4)))
    return edges


def _connected_components(node_ids: list[str], links: list[tuple[str, str, float]]) -> list[list[str]]:
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for source_id, target_id, _ in links:
        adjacency[source_id].add(target_id)
        adjacency[target_id].add(source_id)

    seen: set[str] = set()
    components: list[list[str]] = []
    for node_id in node_ids:
        if node_id in seen:
            continue
        stack = [node_id]
        component = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            stack.extend(adjacency[current] - seen)
        components.append(component)
    return components


def _cluster_label(thoughts: list[Thought]) -> str:
    topic_counts = Counter(topic for thought in thoughts for topic in thought.topics)
    if not topic_counts:
        return "General Reflection"
    top_topics = [topic.replace("_", " ").title() for topic, _ in topic_counts.most_common(2)]
    return " / ".join(top_topics)


def _calculate_trends(
    thoughts_by_cluster: dict[str, list[Thought]],
    now: datetime,
) -> dict[str, str]:
    trends: dict[str, str] = {}
    current_start = now - timedelta(days=7)
    previous_start = now - timedelta(days=14)
    for cluster_id, thoughts in thoughts_by_cluster.items():
        current_count = sum(ensure_utc(thought.created_at) >= current_start for thought in thoughts)
        previous_count = sum(previous_start <= ensure_utc(thought.created_at) < current_start for thought in thoughts)
        if current_count > previous_count:
            trends[cluster_id] = "growing"
        elif current_count < previous_count:
            trends[cluster_id] = "shrinking"
        else:
            trends[cluster_id] = "stable"
    return trends


def recompute_graph(session: Session, user_id: str) -> None:
    settings = get_settings()
    thoughts = list(
        session.scalars(
            select(Thought).where(Thought.user_id == user_id).order_by(Thought.created_at.asc())
        )
    )
    session.execute(delete(Edge).where(Edge.user_id == user_id))
    session.execute(delete(Cluster).where(Cluster.user_id == user_id))
    if not thoughts:
        session.commit()
        return

    edge_specs = _build_edges(thoughts, settings.semantic_link_threshold, settings.semantic_link_limit)
    node_ids = [thought.id for thought in thoughts]
    components = _connected_components(node_ids, edge_specs)
    now = datetime.now(timezone.utc)

    thoughts_by_id = {thought.id: thought for thought in thoughts}
    component_ids: dict[str, str] = {}
    cluster_models: list[Cluster] = []
    thoughts_by_cluster: dict[str, list[Thought]] = {}
    total_thoughts = len(thoughts)

    sorted_components = sorted(components, key=len, reverse=True)
    for index, component in enumerate(sorted_components):
        cluster_id = f"{user_id}-cluster-{index + 1}"
        component_thoughts = [thoughts_by_id[thought_id] for thought_id in component]
        label = _cluster_label(component_thoughts)
        color = PALETTE[index % len(PALETTE)]
        emotion_distribution = Counter(thought.emotion for thought in component_thoughts)
        dominant_themes = [
            topic
            for topic, _ in Counter(topic for thought in component_thoughts for topic in thought.topics).most_common(3)
        ]
        thoughts_by_cluster[cluster_id] = component_thoughts
        cluster_models.append(
            Cluster(
                id=cluster_id,
                user_id=user_id,
                label=label,
                color=color,
                percentage=round(len(component_thoughts) / total_thoughts, 3),
                thought_count=len(component_thoughts),
                dominant_themes=dominant_themes,
                emotion_distribution=dict(emotion_distribution),
            )
        )
        for thought in component_thoughts:
            component_ids[thought.id] = cluster_id

    trend_map = _calculate_trends(thoughts_by_cluster, now)
    for cluster in cluster_models:
        cluster.trend = trend_map.get(cluster.id, "stable")
    session.add_all(cluster_models)

    connection_counts = Counter()
    for source_id, target_id, weight in edge_specs:
        session.add(
            Edge(
                user_id=user_id,
                source_id=source_id,
                target_id=target_id,
                weight=weight,
                kind="semantic_link",
            )
        )
        connection_counts[source_id] += 1
        connection_counts[target_id] += 1

    for thought in thoughts:
        thought.cluster_id = component_ids.get(thought.id)
        thought.connection_count = connection_counts.get(thought.id, 0)
        thought.activity_score = calculate_activity_score(thought.created_at, thought.connection_count)

    session.commit()


def get_graph_response(session: Session, user_id: str) -> GraphResponse:
    return get_graph_response_with_options(session, user_id, social=False)


def get_graph_response_with_options(session: Session, user_id: str, *, social: bool) -> GraphResponse:
    settings = get_settings()
    thoughts = list(
        session.scalars(
            select(Thought).where(Thought.user_id == user_id).order_by(Thought.created_at.asc())
        )
    )
    edges = list(session.scalars(select(Edge).where(Edge.user_id == user_id)))
    clusters = {
        cluster.id: cluster
        for cluster in session.scalars(select(Cluster).where(Cluster.user_id == user_id))
    }
    users = {user.id: user for user in session.scalars(select(User))}
    current_user = users.get(user_id)

    nodes = [
        GraphNode(
            id=thought.id,
            content=thought.content,
            preview=summarize_preview(thought.content),
            created_at=ensure_utc(thought.created_at),
            emotion=thought.emotion,
            topics=thought.topics,
            cluster_id=thought.cluster_id,
            cluster_label=clusters[thought.cluster_id].label if thought.cluster_id in clusters else None,
            color=clusters[thought.cluster_id].color if thought.cluster_id in clusters else PALETTE[0],
            size=float(min(max(4 + thought.connection_count * 1.3 + thought.activity_score * 0.6, 4), 16)),
            connection_count=thought.connection_count,
            activity_score=thought.activity_score,
            author_id=thought.user_id,
            author_display_name=current_user.display_name if current_user else None,
            visibility=thought.visibility,
            is_social=False,
        )
        for thought in thoughts
    ]

    cluster_payload = [
        GraphCluster(
            id=cluster.id,
            label=cluster.label,
            color=cluster.color,
            percentage=cluster.percentage,
            thought_count=cluster.thought_count,
            trend=cluster.trend,
            dominant_themes=cluster.dominant_themes,
            emotion_distribution=cluster.emotion_distribution,
        )
        for cluster in sorted(clusters.values(), key=lambda item: item.thought_count, reverse=True)
    ]

    recent_thoughts = [
        thought
        for thought in thoughts
        if ensure_utc(thought.created_at) >= datetime.now(timezone.utc) - timedelta(days=7)
    ]
    negative_recent = sum(thought.emotion in {"fear", "anger", "sadness"} for thought in recent_thoughts)
    if recent_thoughts and negative_recent / len(recent_thoughts) > 0.5:
        mood = "chaotic"
    elif recent_thoughts and any(thought.emotion in {"growth", "joy"} for thought in recent_thoughts):
        mood = "focused"
    else:
        mood = "neutral"

    social_nodes: list[GraphNode] = []
    social_edges: list[GraphEdge] = []
    social_profiles: list[GraphAuthor] = []
    if social and thoughts:
        following_ids = list(session.scalars(select(Follow.following_id).where(Follow.follower_id == user_id)))
        own_thoughts = thoughts[-50:]
        own_thought_ids = {thought.id for thought in own_thoughts}
        author_colors: dict[str, str] = {}
        added_social_ids: set[str] = set()

        for index, followed_id in enumerate(following_ids):
            author = users.get(followed_id)
            if not author or not author.is_public:
                continue

            author_color = PALETTE[(index + len(clusters)) % len(PALETTE)]
            author_colors[followed_id] = author_color
            social_profiles.append(
                GraphAuthor(
                    user_id=author.id,
                    display_name=author.display_name,
                    avatar_url=author.avatar_url,
                    color=author_color,
                )
            )

            followed_thoughts = list(
                session.scalars(
                    select(Thought)
                    .where(
                        Thought.user_id == followed_id,
                        Thought.visibility == "public",
                    )
                    .order_by(Thought.created_at.desc())
                    .limit(50)
                )
            )

            linked: list[tuple[Thought, Thought, float]] = []
            for foreign in followed_thoughts:
                best_source: Thought | None = None
                best_score = 0.0
                for own in own_thoughts:
                    score = cosine_similarity(own.vector, foreign.vector)
                    if score > best_score:
                        best_score = score
                        best_source = own
                if best_source and best_score >= max(settings.semantic_link_threshold, 0.3):
                    linked.append((best_source, foreign, best_score))

            linked.sort(key=lambda item: item[2], reverse=True)
            if not linked and own_thoughts and followed_thoughts:
                linked = [(own_thoughts[-1], foreign, 0.25) for foreign in followed_thoughts[:3]]
            for source, foreign, score in linked[:12]:
                if foreign.id not in added_social_ids:
                    social_nodes.append(
                        GraphNode(
                            id=foreign.id,
                            content=foreign.content,
                            preview=summarize_preview(foreign.content),
                            created_at=ensure_utc(foreign.created_at),
                            emotion=foreign.emotion,
                            topics=foreign.topics,
                            cluster_id=foreign.cluster_id,
                            cluster_label=None,
                            color=author_color,
                            size=float(min(max(4 + foreign.connection_count * 0.8 + foreign.activity_score * 0.4, 4), 12)),
                            connection_count=foreign.connection_count,
                            activity_score=foreign.activity_score,
                            author_id=foreign.user_id,
                            author_display_name=author.display_name,
                            visibility=foreign.visibility,
                            is_social=True,
                        )
                    )
                    added_social_ids.add(foreign.id)
                social_edges.append(
                    GraphEdge(
                        id=f"cross-{source.id}-{foreign.id}",
                        source=source.id,
                        target=foreign.id,
                        kind="cross_semantic_link",
                        weight=round(score, 4),
                    )
                )
                if foreign.reply_to_id and (foreign.reply_to_id in own_thought_ids or foreign.reply_to_user_id == user_id):
                    social_edges.append(
                        GraphEdge(
                            id=f"reply-{foreign.id}-{foreign.reply_to_id}",
                            source=foreign.id,
                            target=foreign.reply_to_id,
                            kind="reply_link",
                            weight=1.0,
                        )
                    )

    return GraphResponse(
        nodes=nodes,
        edges=[
            GraphEdge(
                id=edge.id,
                source=edge.source_id,
                target=edge.target_id,
                kind=edge.kind,
                weight=edge.weight,
            )
            for edge in edges
        ],
        clusters=cluster_payload,
        mood=mood,
        first_thought_at=ensure_utc(thoughts[0].created_at) if thoughts else None,
        last_thought_at=ensure_utc(thoughts[-1].created_at) if thoughts else None,
        social_enabled=social,
        social_nodes=social_nodes,
        social_edges=social_edges,
        social_profiles=social_profiles,
    )
