from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from math import cos, pi, sin

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models.content_node import ContentNode
from app.models.infra_read_models import GraphProjectionRun, GraphReadModelEdge, GraphReadModelNode
from app.models.node_edge import NodeEdge
from app.schemas.infra import (
    GraphProjectionResponse,
    GraphReadModelEdgeRead,
    GraphReadModelNodeRead,
    GraphReadModelResponse,
)
from app.services.infra_schema import ensure_infra_schema


def rebuild_graph_read_model(
    session: Session,
    *,
    user_id: str | None = None,
    reason: str = "manual",
) -> GraphProjectionResponse:
    ensure_infra_schema(session)
    run = GraphProjectionRun(user_id=user_id, rebuild_reason=reason, status="running")
    session.add(run)
    session.flush()

    try:
        node_delete = delete(GraphReadModelNode)
        edge_delete = delete(GraphReadModelEdge)
        if user_id:
            node_delete = node_delete.where(GraphReadModelNode.user_id == user_id)
            edge_delete = edge_delete.where(GraphReadModelEdge.user_id == user_id)
        session.execute(node_delete)
        session.execute(edge_delete)

        nodes = _source_nodes(session, user_id)
        degree_counts = _degree_counts(session, [node.id for node in nodes])
        positions = _layout_positions(nodes)
        high_watermark = _high_watermark(nodes)
        for node in nodes:
            x, y = positions.get(node.id, (0.0, 0.0))
            session.add(
                GraphReadModelNode(
                    source_node_id=node.id,
                    user_id=node.user_id,
                    kind=node.kind,
                    title=node.title,
                    preview_text=node.preview_text,
                    topics=node.topics or [],
                    cluster_id=node.cluster_id,
                    degree=degree_counts.get(node.id, 0),
                    position_x=x,
                    position_y=y,
                    source_updated_at=node.updated_at,
                    projection_version=run.id,
                    derived_from={
                        "canonical": False,
                        "source_table": "content_nodes",
                        "source_id": node.id,
                        "rebuildable": True,
                    },
                )
            )

        edges = _source_edges(session, user_id, {node.id for node in nodes})
        for edge in edges:
            session.add(
                GraphReadModelEdge(
                    source_edge_id=edge.id,
                    user_id=edge.user_id,
                    source_node_id=edge.source_id,
                    target_node_id=edge.target_id,
                    edge_type=edge.edge_type,
                    weight=edge.weight,
                    explanation=edge.explanation or {},
                    projection_version=run.id,
                )
            )

        run.status = "succeeded"
        run.completed_at = datetime.now(timezone.utc)
        run.source_high_watermark = high_watermark
        run.projected_counts = {"nodes": len(nodes), "edges": len(edges)}
        session.add(run)
        session.flush()
        return GraphProjectionResponse(
            projection_id=run.id,
            status=run.status,
            nodes=len(nodes),
            edges=len(edges),
            user_id=user_id,
            source_high_watermark=high_watermark,
            explanation="graph read model rebuilt from canonical content_nodes and node_edges; it is derived storage only",
        )
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        session.add(run)
        session.flush()
        raise


def query_graph_read_model(
    session: Session,
    *,
    user_id: str,
    include_edges: bool = True,
    limit: int = 500,
) -> GraphReadModelResponse:
    ensure_infra_schema(session)
    projection_version = session.scalar(
        select(GraphProjectionRun.id)
        .where(
            GraphProjectionRun.status == "succeeded",
            or_(GraphProjectionRun.user_id == user_id, GraphProjectionRun.user_id.is_(None)),
        )
        .order_by(GraphProjectionRun.completed_at.desc())
        .limit(1)
    )
    nodes = list(
        session.scalars(
            select(GraphReadModelNode)
            .where(GraphReadModelNode.user_id == user_id)
            .order_by(GraphReadModelNode.degree.desc(), GraphReadModelNode.updated_at.desc())
            .limit(limit)
        )
    )
    edges: list[GraphReadModelEdge] = []
    if include_edges and nodes:
        node_ids = {node.source_node_id for node in nodes}
        edges = list(
            session.scalars(
                select(GraphReadModelEdge).where(
                    GraphReadModelEdge.user_id == user_id,
                    GraphReadModelEdge.source_node_id.in_(node_ids),
                    GraphReadModelEdge.target_node_id.in_(node_ids),
                )
            )
        )
    return GraphReadModelResponse(
        nodes=[GraphReadModelNodeRead.model_validate(node) for node in nodes],
        edges=[GraphReadModelEdgeRead.model_validate(edge) for edge in edges],
        projection_version=projection_version,
        explanation="query served from graph_read_model_* tables only; rebuild from canonical tables if stale",
    )


def latest_graph_projection_run(session: Session) -> GraphProjectionRun | None:
    ensure_infra_schema(session)
    return session.scalar(select(GraphProjectionRun).order_by(GraphProjectionRun.created_at.desc()).limit(1))


def _source_nodes(session: Session, user_id: str | None) -> list[ContentNode]:
    statement = select(ContentNode).order_by(ContentNode.created_at.asc())
    if user_id:
        statement = statement.where(ContentNode.user_id == user_id)
    return list(session.scalars(statement))


def _source_edges(session: Session, user_id: str | None, node_ids: set[str]) -> list[NodeEdge]:
    if not node_ids:
        return []
    statement = select(NodeEdge).where(NodeEdge.source_id.in_(node_ids), NodeEdge.target_id.in_(node_ids))
    if user_id:
        statement = statement.where(NodeEdge.user_id == user_id)
    return list(session.scalars(statement))


def _degree_counts(session: Session, node_ids: list[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    if not node_ids:
        return {}
    rows = session.execute(
        select(NodeEdge.source_id, NodeEdge.target_id, func.count(NodeEdge.id))
        .where(NodeEdge.source_id.in_(node_ids), NodeEdge.target_id.in_(node_ids))
        .group_by(NodeEdge.source_id, NodeEdge.target_id)
    )
    for source_id, target_id, count in rows:
        counts[source_id] += count
        counts[target_id] += count
    return dict(counts)


def _layout_positions(nodes: list[ContentNode]) -> dict[str, tuple[float, float]]:
    by_cluster: dict[str, list[ContentNode]] = {}
    for node in nodes:
        by_cluster.setdefault(node.cluster_id or "unclustered", []).append(node)

    positions: dict[str, tuple[float, float]] = {}
    cluster_keys = sorted(by_cluster)
    for cluster_index, cluster_id in enumerate(cluster_keys):
        cluster_angle = (-pi / 2) + (2 * pi * cluster_index / max(len(cluster_keys), 1))
        cluster_radius = 280.0 if len(cluster_keys) > 1 else 0.0
        center_x = cluster_radius * cos(cluster_angle)
        center_y = cluster_radius * sin(cluster_angle)
        members = sorted(by_cluster[cluster_id], key=lambda item: item.created_at)
        for node_index, node in enumerate(members):
            local_angle = 2 * pi * node_index / max(len(members), 1)
            local_radius = 52.0 + 18.0 * (node_index // 8)
            positions[node.id] = (
                round(center_x + local_radius * cos(local_angle), 3),
                round(center_y + local_radius * sin(local_angle), 3),
            )
    return positions


def _high_watermark(nodes: list[ContentNode]) -> str | None:
    values = [node.updated_at for node in nodes if node.updated_at]
    if not values:
        return None
    return max(values).isoformat()
