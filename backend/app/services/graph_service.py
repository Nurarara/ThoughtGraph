from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timezone
from math import cos, pi, sin
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.content_node import ContentNode
from app.models.media_asset import MediaAsset
from app.models.node_cluster import NodeCluster
from app.models.node_edge import NodeEdge
from app.models.user import User
from app.models.workflow_job import WorkflowJob
from app.schemas.graph import (
    GraphClusterRead,
    GraphEdgeRead,
    GraphExplanation,
    GraphNodeRead,
    GraphResponse,
    GraphSearchItem,
    GraphSearchResponse,
    GraphViewport,
)
from app.services.event_service import emit_event
from app.services.media_service import to_media_asset_read
from app.services.social_service import get_relationship, get_visible_social_user_ids, visible_nodes_for_owner
from app.services.text_analysis import cosine_similarity, infer_topics, summarize_preview
from app.services.workflow_service import complete_job, fail_job, start_job


PALETTE = [
    "#2f7be5",
    "#f37f52",
    "#2aa876",
    "#d1498b",
    "#7d6bff",
    "#c7942f",
]


def reconcile_user_graph_projection(session: Session, user_id: str) -> dict[str, int]:
    """Deterministically reconcile canonical edges, clusters, and counts.

    This is intended for historical imports. It deliberately creates no jobs or
    domain events; callers own the surrounding transaction.
    """
    settings = get_settings()
    nodes = list(
        session.scalars(
            select(ContentNode).where(ContentNode.user_id == user_id).order_by(ContentNode.created_at, ContentNode.id)
        )
    )
    node_ids = {node.id for node in nodes}
    desired: dict[tuple[str, str], tuple[float, list[str]]] = {}
    for node in nodes:
        candidates: list[tuple[ContentNode, float]] = []
        for candidate in nodes:
            if candidate.id == node.id:
                continue
            score = cosine_similarity(node.embedding, candidate.embedding)
            if score >= settings.semantic_link_threshold:
                candidates.append((candidate, score))
        candidates.sort(key=lambda item: (-item[1], item[0].id))
        for candidate, score in candidates[: settings.semantic_link_limit]:
            pair = tuple(sorted((node.id, candidate.id)))
            current = desired.get(pair)
            if current is None or score > current[0]:
                desired[pair] = (round(score, 4), sorted(set(node.topics).intersection(candidate.topics)))

    semantic_edges = list(
        session.scalars(
            select(NodeEdge).where(NodeEdge.user_id == user_id, NodeEdge.edge_type == "semantic_similarity")
        )
    )
    existing_by_pair = {(edge.source_id, edge.target_id): edge for edge in semantic_edges}
    for pair, edge in existing_by_pair.items():
        if pair not in desired:
            session.delete(edge)
    for (source_id, target_id), (score, shared_topics) in desired.items():
        edge = existing_by_pair.get((source_id, target_id))
        if edge is None:
            edge = NodeEdge(
                id=str(uuid5(NAMESPACE_URL, f"thoughtgraph:semantic:{user_id}:{source_id}:{target_id}")),
                user_id=user_id,
                source_id=source_id,
                target_id=target_id,
                edge_type="semantic_similarity",
            )
        edge.weight = score
        edge.explanation = {"reason": "semantic_overlap", "shared_topics": shared_topics, "score": score}
        session.add(edge)
    session.flush()

    all_edges = list(
        session.scalars(
            select(NodeEdge).where(
                NodeEdge.user_id == user_id,
                NodeEdge.source_id.in_(node_ids),
                NodeEdge.target_id.in_(node_ids),
            )
        )
    ) if node_ids else []
    adjacency = {node.id: set() for node in nodes}
    counts: Counter[str] = Counter()
    for edge in all_edges:
        adjacency[edge.source_id].add(edge.target_id)
        adjacency[edge.target_id].add(edge.source_id)
        counts[edge.source_id] += 1
        counts[edge.target_id] += 1

    existing_clusters = {
        cluster.id: cluster
        for cluster in session.scalars(select(NodeCluster).where(NodeCluster.user_id == user_id))
    }
    node_map = {node.id: node for node in nodes}
    components: list[list[str]] = []
    remaining = set(node_ids)
    while remaining:
        anchor = min(remaining)
        component = _component_for_anchor(anchor, adjacency)
        components.append(sorted(component))
        remaining.difference_update(component)

    used_cluster_ids: set[str] = set()
    for component in sorted(components, key=lambda item: item[0]):
        members = [node_map[node_id] for node_id in component]
        reusable = sorted({node.cluster_id for node in members if node.cluster_id in existing_clusters})
        cluster_id = reusable[0] if reusable else str(
            uuid5(NAMESPACE_URL, f"thoughtgraph:cluster:{user_id}:{component[0]}")
        )
        cluster = existing_clusters.get(cluster_id)
        if cluster is None:
            cluster = NodeCluster(id=cluster_id, user_id=user_id, label="", color=PALETTE[len(used_cluster_ids) % len(PALETTE)])
            existing_clusters[cluster_id] = cluster
        topic_counts = Counter(topic for node in members for topic in node.topics)
        dominant_topics = [topic for topic, _ in topic_counts.most_common(3)] or ["general"]
        cluster.label = _cluster_label(dominant_topics)
        cluster.summary = _cluster_summary(dominant_topics, len(members))
        cluster.node_count = len(members)
        cluster.dominant_topics = dominant_topics
        cluster.density_score = round(sum(counts[node.id] for node in members) / max(len(members), 1), 3)
        session.add(cluster)
        for node in members:
            node.cluster_id = cluster_id
            node.connection_count = counts[node.id]
            session.add(node)
        used_cluster_ids.add(cluster_id)
    session.flush()
    for cluster_id, cluster in existing_clusters.items():
        if cluster_id not in used_cluster_ids:
            session.delete(cluster)
    session.flush()
    return {"nodes": len(nodes), "semantic_edges": len(desired), "clusters": len(components)}


def recompute_local_graph_projection(session: Session, job: WorkflowJob) -> None:
    start_job(session, job)
    node = session.get(ContentNode, job.aggregate_id)
    if node is None:
        fail_job(session, job, "target node not found")
        session.commit()
        return

    try:
        settings = get_settings()
        existing_nodes = list(
            session.scalars(
                select(ContentNode)
                .where(ContentNode.user_id == node.user_id, ContentNode.id != node.id)
                .order_by(ContentNode.created_at.asc())
            )
        )

        session.execute(
            delete(NodeEdge).where(
                NodeEdge.user_id == node.user_id,
                NodeEdge.edge_type == "semantic_similarity",
                or_(NodeEdge.source_id == node.id, NodeEdge.target_id == node.id),
            )
        )

        candidates: list[tuple[ContentNode, float]] = []
        for existing in existing_nodes:
            score = cosine_similarity(node.embedding, existing.embedding)
            if score >= settings.semantic_link_threshold:
                candidates.append((existing, score))
        candidates.sort(key=lambda item: item[1], reverse=True)
        candidates = candidates[: settings.semantic_link_limit]

        for existing, score in candidates:
            source_id, target_id = sorted((node.id, existing.id))
            shared_topics = sorted(set(node.topics).intersection(existing.topics))
            edge = NodeEdge(
                user_id=node.user_id,
                source_id=source_id,
                target_id=target_id,
                edge_type="semantic_similarity",
                weight=round(score, 4),
                explanation={
                    "reason": "semantic_overlap",
                    "shared_topics": shared_topics,
                    "score": round(score, 4),
                },
            )
            session.add(edge)
            session.flush()
            emit_event(
                session,
                event_type="edge_created",
                aggregate_type="node_edge",
                aggregate_id=edge.id,
                actor_id=node.user_id,
                payload=edge.explanation,
            )

        _refresh_connection_counts(session, node.user_id)
        _refresh_clusters_for_node(session, node.user_id, node.id)
        emit_event(
            session,
            event_type="graph_projection_refreshed",
            aggregate_type="content_node",
            aggregate_id=node.id,
            actor_id=node.user_id,
            payload={"user_id": node.user_id},
        )
        complete_job(session, job, {"node_id": node.id})
        session.commit()
    except Exception as exc:  # pragma: no cover - defensive workflow state
        fail_job(session, job, str(exc))
        session.commit()
        raise


def _refresh_connection_counts(session: Session, user_id: str) -> None:
    nodes = list(session.scalars(select(ContentNode).where(ContentNode.user_id == user_id)))
    counts = Counter()
    edges = list(session.scalars(select(NodeEdge).where(NodeEdge.user_id == user_id)))
    for edge in edges:
        counts[edge.source_id] += 1
        counts[edge.target_id] += 1
    for node in nodes:
        node.connection_count = counts.get(node.id, 0)
        session.add(node)
    session.flush()


def _refresh_clusters_for_node(session: Session, user_id: str, anchor_node_id: str) -> None:
    nodes = list(session.scalars(select(ContentNode).where(ContentNode.user_id == user_id)))
    node_map = {node.id: node for node in nodes}
    edges = list(session.scalars(select(NodeEdge).where(NodeEdge.user_id == user_id)))
    adjacency: dict[str, set[str]] = {node.id: set() for node in nodes}
    for edge in edges:
        adjacency.setdefault(edge.source_id, set()).add(edge.target_id)
        adjacency.setdefault(edge.target_id, set()).add(edge.source_id)

    component_ids = _component_for_anchor(anchor_node_id, adjacency)
    component_nodes = [node_map[node_id] for node_id in component_ids if node_id in node_map]
    if not component_nodes:
        component_nodes = [node_map[anchor_node_id]]

    related_cluster_ids = {node.cluster_id for node in component_nodes if node.cluster_id}
    seen_ids = {item.id for item in component_nodes}
    for cluster_id in list(related_cluster_ids):
        related_nodes = list(
            session.scalars(
                select(ContentNode).where(ContentNode.user_id == user_id, ContentNode.cluster_id == cluster_id)
            )
        )
        for related in related_nodes:
            if related.id not in seen_ids:
                component_nodes.append(related)
                seen_ids.add(related.id)

    component_nodes.sort(key=lambda item: item.created_at)
    primary_cluster_id = _primary_cluster_id_for_merge(session, related_cluster_ids)
    if primary_cluster_id:
        cluster = session.get(NodeCluster, primary_cluster_id)
    else:
        cluster = NodeCluster(user_id=user_id, label="", color=PALETTE[0], summary="")
        session.add(cluster)
        session.flush()
    if cluster is None:
        cluster = NodeCluster(user_id=user_id, label="", color=PALETTE[0], summary="")
        session.add(cluster)
        session.flush()

    topic_counts = Counter(topic for node in component_nodes for topic in node.topics)
    dominant_topics = [topic for topic, _ in topic_counts.most_common(3)] or ["general"]
    cluster.label = _cluster_label(dominant_topics)
    cluster.summary = _cluster_summary(dominant_topics, len(component_nodes))
    cluster.node_count = len(component_nodes)
    cluster.dominant_topics = dominant_topics
    if not cluster.color:
        cluster.color = PALETTE[(len(dominant_topics) + len(component_nodes)) % len(PALETTE)]
    cluster.density_score = round(sum(node.connection_count for node in component_nodes) / max(len(component_nodes), 1), 3)
    session.add(cluster)
    session.flush()

    for node in component_nodes:
        node.cluster_id = cluster.id
        session.add(node)

    for cluster_id in related_cluster_ids:
        if cluster_id != cluster.id:
            old = session.get(NodeCluster, cluster_id)
            if old is not None:
                session.delete(old)

    emit_event(
        session,
        event_type="cluster_updated",
        aggregate_type="node_cluster",
        aggregate_id=cluster.id,
        actor_id=user_id,
        payload={
            "label": cluster.label,
            "node_count": cluster.node_count,
            "dominant_topics": cluster.dominant_topics,
        },
    )
    session.flush()


def _primary_cluster_id_for_merge(session: Session, cluster_ids: set[str]) -> str | None:
    if not cluster_ids:
        return None
    clusters = [cluster for cluster_id in cluster_ids if (cluster := session.get(NodeCluster, cluster_id)) is not None]
    if not clusters:
        return None
    clusters.sort(key=lambda item: (-item.node_count, item.created_at, item.id))
    return clusters[0].id


def _component_for_anchor(anchor_node_id: str, adjacency: dict[str, set[str]]) -> list[str]:
    seen: set[str] = set()
    queue: deque[str] = deque([anchor_node_id])
    result: list[str] = []
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        result.append(current)
        queue.extend(adjacency.get(current, set()) - seen)
    return result


def _cluster_label(dominant_topics: list[str]) -> str:
    return " / ".join(topic.replace("_", " ").title() for topic in dominant_topics[:2])


def _cluster_summary(dominant_topics: list[str], count: int) -> str:
    topic_phrase = ", ".join(topic.replace("_", " ") for topic in dominant_topics[:3])
    return f"{count} connected nodes centered on {topic_phrase}."


def build_graph_response(session: Session, user_id: str, social: bool = False) -> GraphResponse:
    own_nodes = visible_nodes_for_owner(session, user_id, user_id, include_muted=True)
    own_clusters = list(session.scalars(select(NodeCluster).where(NodeCluster.user_id == user_id)))
    all_nodes = list(own_nodes)
    all_clusters = list(own_clusters)
    users = {user.id: user for user in session.scalars(select(User))}
    node_positions: dict[str, tuple[float, float]] = {}
    cluster_positions: dict[str, tuple[float, float]] = {}

    own_layout = _build_layout(own_nodes, own_clusters)
    node_positions.update(own_layout["nodes"])
    cluster_positions.update(own_layout["clusters"])

    social_edges: list[GraphEdgeRead] = []
    social_cluster_ids: set[str] = set()
    if social:
        social_user_ids = get_visible_social_user_ids(session, user_id)
        for index, social_user_id in enumerate(social_user_ids):
            visible_nodes = visible_nodes_for_owner(session, user_id, social_user_id)
            if not visible_nodes:
                continue
            user_clusters = list(session.scalars(select(NodeCluster).where(NodeCluster.user_id == social_user_id)))
            local_layout = _build_layout(visible_nodes, user_clusters)
            angle = (-pi / 2) + (2 * pi * index / max(len(social_user_ids), 1))
            anchor_x = 760 * cos(angle)
            anchor_y = 760 * sin(angle)
            for node_id, (x, y) in local_layout["nodes"].items():
                node_positions[node_id] = (round(anchor_x + (x * 0.55), 3), round(anchor_y + (y * 0.55), 3))
            for cluster_id, (x, y) in local_layout["clusters"].items():
                cluster_positions[cluster_id] = (round(anchor_x + (x * 0.55), 3), round(anchor_y + (y * 0.55), 3))
                social_cluster_ids.add(cluster_id)
            all_nodes.extend(visible_nodes)
            all_clusters.extend(user_clusters)

            own_subset = own_nodes[-12:]
            for own in own_subset:
                scored = [
                    (candidate, cosine_similarity(own.embedding, candidate.embedding))
                    for candidate in visible_nodes
                ]
                scored = [item for item in scored if item[1] >= max(get_settings().semantic_link_threshold, 0.28)]
                scored.sort(key=lambda item: item[1], reverse=True)
                for candidate, score in scored[:2]:
                    social_edges.append(
                        GraphEdgeRead(
                            id=f"social-{own.id}-{candidate.id}",
                            source=own.id,
                            target=candidate.id,
                            edge_type="social_similarity",
                            weight=round(score, 4),
                            explanation={
                                "reason": "shared_topics",
                                "shared_topics": sorted(set(own.topics).intersection(candidate.topics)),
                            },
                        )
                    )

    media_asset_ids = {node.media_asset_id for node in all_nodes if node.media_asset_id}
    media_assets = {
        asset.id: asset
        for asset in session.scalars(select(MediaAsset).where(MediaAsset.id.in_(media_asset_ids)))
    }
    cluster_map = {cluster.id: cluster for cluster in all_clusters}
    included_node_ids = [node.id for node in all_nodes]
    stored_edges = list(
        session.scalars(
            select(NodeEdge).where(
                NodeEdge.source_id.in_(included_node_ids),
                NodeEdge.target_id.in_(included_node_ids),
            )
        )
    ) if included_node_ids else []
    graph_edges = [
        GraphEdgeRead(
            id=edge.id,
            source=edge.source_id,
            target=edge.target_id,
            edge_type=edge.edge_type,
            weight=edge.weight,
            explanation=edge.explanation or {},
        )
        for edge in stored_edges
    ]
    graph_edges.extend(social_edges)

    graph_nodes = []
    for node in all_nodes:
        author = users.get(node.user_id)
        relationship = "self" if node.user_id == user_id else _relationship_label(session, user_id, node.user_id)
        media_asset = media_assets.get(node.media_asset_id) if node.media_asset_id else None
        media_read = to_media_asset_read(media_asset) if media_asset else None
        graph_nodes.append(
            GraphNodeRead(
                id=node.id,
                kind=node.kind,
                title=node.title,
                content_text=node.content_text,
                preview_text=node.preview_text,
                visibility=node.visibility,
                created_at=_ensure_utc(node.created_at),
                updated_at=_ensure_utc(node.updated_at),
                topics=node.topics,
                cluster_id=node.cluster_id,
                cluster_label=cluster_map[node.cluster_id].label if node.cluster_id in cluster_map else None,
                cluster_color=cluster_map[node.cluster_id].color if node.cluster_id in cluster_map else None,
                connection_count=node.connection_count,
                x=node_positions.get(node.id, (0.0, 0.0))[0],
                y=node_positions.get(node.id, (0.0, 0.0))[1],
                author_id=node.user_id,
                author_display_name=author.display_name if author else None,
                relationship_to_viewer=relationship,
                is_social=node.user_id != user_id,
                media_asset_id=media_asset.id if media_asset else None,
                media_kind=media_asset.kind if media_asset else None,
                media_status=media_asset.status if media_asset else None,
                thumbnail_url=media_read.thumbnail_url if media_read else None,
                playback_url=media_read.playback_url if media_read else None,
                duration_seconds=media_asset.duration_seconds if media_asset else None,
                media_url=media_read.original_url if media_read else None,
                link_url=node.link_url,
                reply_to_node_id=node.reply_to_node_id,
                quote_of_node_id=node.quote_of_node_id,
            )
        )

    graph_clusters = []
    seen_cluster_ids: set[str] = set()
    for cluster in sorted(all_clusters, key=lambda item: item.node_count, reverse=True):
        if cluster.id in seen_cluster_ids:
            continue
        seen_cluster_ids.add(cluster.id)
        graph_clusters.append(
            GraphClusterRead(
                id=cluster.id,
                label=cluster.label,
                color=cluster.color,
                summary=cluster.summary,
                node_count=cluster.node_count,
                dominant_topics=cluster.dominant_topics,
                centroid_x=cluster_positions.get(cluster.id, (0.0, 0.0))[0],
                centroid_y=cluster_positions.get(cluster.id, (0.0, 0.0))[1],
                owner_user_id=cluster.user_id,
                is_social=cluster.id in social_cluster_ids,
            )
        )

    return GraphResponse(
        nodes=graph_nodes,
        edges=graph_edges,
        clusters=graph_clusters,
        viewport=GraphViewport(center_x=0.0, center_y=0.0, zoom_hint=_zoom_hint(len(graph_nodes))),
        explanation=GraphExplanation(
            reason="social graph projected from visible nodes, relationship state, and semantic bridges" if social else "personal graph projected from canonical content nodes and semantic similarity edges",
            generated_at=datetime.now(timezone.utc),
        ),
        social_mode=social,
    )


def search_graph(session: Session, user_id: str, query: str) -> GraphSearchResponse:
    terms = [term for term in query.lower().split() if term]
    if not terms:
        return GraphSearchResponse(items=[])

    clusters = {cluster.id: cluster for cluster in session.scalars(select(NodeCluster).where(NodeCluster.user_id == user_id))}
    nodes = list(
        session.scalars(
            select(ContentNode).where(ContentNode.user_id == user_id).order_by(ContentNode.updated_at.desc())
        )
    )
    scored: list[GraphSearchItem] = []
    for node in nodes:
        haystacks = [
            (node.title or "").lower(),
            node.content_text.lower(),
            " ".join(node.topics).lower(),
            node.preview_text.lower(),
        ]
        score = 0.0
        for term in terms:
            for haystack in haystacks:
                if term in haystack:
                    score += 1.0
        if score <= 0:
            continue
        cluster = clusters.get(node.cluster_id)
        scored.append(
            GraphSearchItem(
                node_id=node.id,
                title=node.title,
                preview_text=node.preview_text,
                cluster_label=cluster.label if cluster else None,
                cluster_color=cluster.color if cluster else None,
                score=score,
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    return GraphSearchResponse(items=scored[: get_settings().graph_search_limit])


def summarize_node_topics(text: str) -> tuple[str, list[str]]:
    preview = summarize_preview(text, limit=180)
    return preview, infer_topics(text)


def _build_layout(nodes: list[ContentNode], clusters: list[NodeCluster]) -> dict[str, dict[str, tuple[float, float]]]:
    cluster_nodes: dict[str, list[ContentNode]] = {cluster.id: [] for cluster in clusters}
    for node in nodes:
        if node.cluster_id and node.cluster_id in cluster_nodes:
            cluster_nodes[node.cluster_id].append(node)

    cluster_positions: dict[str, tuple[float, float]] = {}
    node_positions: dict[str, tuple[float, float]] = {}
    if not clusters:
        return {"clusters": cluster_positions, "nodes": node_positions}

    radius = 320.0 if len(clusters) > 1 else 0.0
    for index, cluster in enumerate(sorted(clusters, key=lambda item: item.label.lower())):
        angle = (-pi / 2) + (2 * pi * index / max(len(clusters), 1))
        cx = radius * cos(angle)
        cy = radius * sin(angle)
        cluster_positions[cluster.id] = (round(cx, 3), round(cy, 3))

        members = sorted(cluster_nodes.get(cluster.id, []), key=lambda item: item.created_at)
        for member_index, node in enumerate(members):
            local_angle = (2 * pi * member_index / max(len(members), 1)) if members else 0.0
            local_radius = 42 + 24 * (member_index // 6)
            x = cx + local_radius * cos(local_angle)
            y = cy + local_radius * sin(local_angle)
            node_positions[node.id] = (round(x, 3), round(y, 3))
    return {"clusters": cluster_positions, "nodes": node_positions}


def _relationship_label(session: Session, viewer_id: str, target_user_id: str) -> str:
    relationship = get_relationship(session, viewer_id, target_user_id)
    if relationship.friendship_state == "accepted":
        return "friend"
    if relationship.following:
        return "following"
    return "ambient"


def _zoom_hint(node_count: int) -> float:
    if node_count <= 8:
        return 1.0
    if node_count <= 24:
        return 0.88
    return 0.74


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
