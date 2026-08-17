from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.content_node import ContentNode
from app.models.node_cluster import NodeCluster
from app.models.node_edge import NodeEdge


REFERENCE_TIME = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)


@dataclass
class MagicMomentHistory:
    name: str
    now: datetime
    clusters: dict[str, NodeCluster]
    nodes: dict[str, ContentNode]
    edges: dict[str, NodeEdge] = field(default_factory=dict)


def builder_pivot(session: Session) -> MagicMomentHistory:
    clusters = _clusters(session, ["Career", "Product"])
    nodes: dict[str, ContentNode] = {}
    for index in range(6):
        nodes[f"prior_career_{index}"] = _node(
            session, f"Career plan {index}", "Planning the next role and interview path.", clusters["Career"], -10
        )
    for index in range(6):
        nodes[f"current_product_{index}"] = _node(
            session, f"Product experiment {index}", "Building and testing a focused product hypothesis.", clusters["Product"], -2
        )
    for index in range(2):
        nodes[f"current_career_{index}"] = _node(
            session, f"Career checkpoint {index}", "Keeping a small thread of career planning active.", clusters["Career"], -1
        )
    edges = _hub_edges(session, nodes["current_product_0"], [nodes[f"current_product_{i}"] for i in range(1, 4)])
    session.commit()
    return MagicMomentHistory("builder_pivot", REFERENCE_TIME, clusters, nodes, edges)


def source_monoculture(session: Session) -> MagicMomentHistory:
    clusters = _clusters(session, ["Research", "Practice"])
    nodes: dict[str, ContentNode] = {}
    for index in range(4):
        nodes[f"prior_mixed_{index}"] = _node(
            session, f"Mixed source {index}", "A deliberately varied earlier input.", clusters["Research"], -10,
            kind="link" if index % 2 else "thought", link_url=f"https://prior-{index}.example/item" if index % 2 else None,
        )
    for index in range(6):
        domain = "research.example" if index < 5 else "alternate.example"
        nodes[f"current_link_{index}"] = _node(
            session, f"Research link {index}", "Evidence collected from a synthetic research source.", clusters["Research"], -2,
            kind="link", link_url=f"https://{domain}/paper-{index}",
        )
    session.commit()
    return MagicMomentHistory("source_monoculture", REFERENCE_TIME, clusters, nodes)


def connected_synthesis(session: Session) -> MagicMomentHistory:
    clusters = _clusters(session, ["Learning", "Decision"])
    nodes: dict[str, ContentNode] = {}
    for index in range(4):
        nodes[f"prior_learning_{index}"] = _node(
            session, f"Learning note {index}", "Collecting background before making a decision.", clusters["Learning"], -10
        )
    for index in range(5):
        nodes[f"current_decision_{index}"] = _node(
            session, f"Decision synthesis {index}", "Connecting evidence into a concrete decision.", clusters["Decision"], -2
        )
    hub = nodes["current_decision_0"]
    nodes["current_decision_3"].quote_of_node_id = hub.id
    nodes["current_decision_4"].reply_to_node_id = hub.id
    edges = _hub_edges(session, hub, [nodes[f"current_decision_{i}"] for i in range(1, 5)])
    session.commit()
    return MagicMomentHistory("connected_synthesis", REFERENCE_TIME, clusters, nodes, edges)


def _clusters(session: Session, labels: list[str]) -> dict[str, NodeCluster]:
    result = {}
    for index, label in enumerate(labels):
        cluster = NodeCluster(
            user_id="local-user", label=label, color=f"#3366{index + 3}f", summary=f"Synthetic {label} history.",
            node_count=0, density_score=0.0, dominant_topics=[label.lower()],
        )
        session.add(cluster)
        session.flush()
        result[label] = cluster
    return result


def _node(
    session: Session,
    title: str,
    content: str,
    cluster: NodeCluster,
    days_from_now: int,
    *,
    kind: str = "thought",
    link_url: str | None = None,
) -> ContentNode:
    created_at = REFERENCE_TIME + timedelta(days=days_from_now)
    node = ContentNode(
        user_id="local-user", kind=kind, title=title, content_text=content, preview_text=content,
        visibility="private", status="ready", topics=[cluster.label.lower()], cluster_id=cluster.id,
        link_url=link_url, connection_count=0, created_at=created_at, updated_at=created_at,
    )
    session.add(node)
    session.flush()
    cluster.node_count += 1
    return node


def _hub_edges(session: Session, hub: ContentNode, targets: list[ContentNode]) -> dict[str, NodeEdge]:
    edges = {}
    for index, target in enumerate(targets):
        edge = NodeEdge(
            user_id="local-user", source_id=hub.id, target_id=target.id, edge_type="semantic_similarity",
            weight=round(0.9 - index * 0.05, 2), explanation={"fixture": "known semantic link"},
        )
        session.add(edge)
        session.flush()
        edges[f"hub_edge_{index}"] = edge
    hub.connection_count = len(targets)
    return edges
