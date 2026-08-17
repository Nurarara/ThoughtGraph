from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from math import isfinite
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.content_node import ContentNode
from app.models.node_edge import NodeEdge
from app.models.thought import Thought
from app.models.user import User
from app.services.text_analysis import embed_text, summarize_preview
from app.services.graph_service import reconcile_user_graph_projection


MIGRATION_VERSION = 1
EMBEDDING_DIMENSIONS = 256
VisibilityPolicy = Literal["preserve", "private"]


class LegacyThoughtMigrationConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class LegacyThoughtMigrationReport:
    legacy_thoughts: int = 0
    would_migrate: int = 0
    already_migrated: int = 0
    reply_edges: int = 0
    embeddings_recomputed: int = 0
    conflicts: int = 0
    applied: bool = False
    visibility_policy: str = "preserve"
    projection_users: int = 0
    projected_nodes: int = 0
    semantic_edges: int = 0
    clusters: int = 0

    def to_dict(self) -> dict[str, int | bool | str]:
        return asdict(self)


def migrate_legacy_thoughts(
    session: Session,
    *,
    apply: bool = False,
    visibility_policy: VisibilityPolicy = "preserve",
    reconcile_projection: bool = False,
) -> LegacyThoughtMigrationReport:
    """Plan or atomically apply the V1 Thought -> ContentNode migration.

    The caller owns the database connection. On apply, this function commits the
    complete import or rolls it back on any conflict/error.
    """
    if visibility_policy not in {"preserve", "private"}:
        raise ValueError(f"unsupported visibility policy: {visibility_policy}")
    thoughts = list(session.scalars(select(Thought).order_by(Thought.created_at.asc(), Thought.id.asc())))
    legacy_ids = {thought.id for thought in thoughts}
    referenced_ids = {thought.reply_to_id for thought in thoughts if thought.reply_to_id}
    relevant_node_ids = legacy_ids | referenced_ids
    users = {user.id for user in session.scalars(select(User).where(User.id.in_({t.user_id for t in thoughts})))} if thoughts else {}
    existing_nodes = {
        node.id: node
        for node in session.scalars(select(ContentNode).where(ContentNode.id.in_(relevant_node_ids)))
    } if relevant_node_ids else {}

    conflicts: list[str] = []
    pending: list[tuple[Thought, list[float], bool, str | None]] = []
    already_migrated = 0
    embeddings_recomputed = 0

    for thought in thoughts:
        if thought.user_id not in users:
            conflicts.append(f"thought {thought.id} references missing user {thought.user_id}")
            continue
        if thought.reply_to_id and thought.reply_to_id not in legacy_ids and thought.reply_to_id not in existing_nodes:
            conflicts.append(f"thought {thought.id} references missing reply target {thought.reply_to_id}")
            continue
        reply_target_id = thought.reply_to_id
        embedding, recomputed = _validated_embedding(thought.vector, thought.content)
        existing = existing_nodes.get(thought.id)
        if existing is not None:
            if _is_same_migrated_thought(existing, thought, reply_target_id, visibility_policy):
                already_migrated += 1
                continue
            conflicts.append(f"content_nodes.id {thought.id} already exists with different canonical data")
            continue
        pending.append((thought, embedding, recomputed, reply_target_id))
        embeddings_recomputed += int(recomputed)

    if conflicts:
        if apply:
            session.rollback()
        raise LegacyThoughtMigrationConflict("; ".join(conflicts))

    reply_specs = [
        (thought, reply_target_id)
        for thought, _, _, reply_target_id in pending
        if reply_target_id is not None
    ]
    affected_user_ids = {thought.user_id for thought in thoughts}
    existing_affected_nodes = (
        session.scalar(
            select(func.count()).select_from(ContentNode).where(ContentNode.user_id.in_(affected_user_ids))
        )
        if affected_user_ids
        else 0
    ) or 0
    report = LegacyThoughtMigrationReport(
        legacy_thoughts=len(thoughts),
        would_migrate=len(pending),
        already_migrated=already_migrated,
        reply_edges=len(reply_specs),
        embeddings_recomputed=embeddings_recomputed,
        conflicts=0,
        applied=apply,
        visibility_policy=visibility_policy,
        projection_users=len(affected_user_ids) if reconcile_projection else 0,
        projected_nodes=(existing_affected_nodes + len(pending)) if reconcile_projection else 0,
    )
    if not apply:
        session.rollback()
        return report

    try:
        for thought, embedding, _, reply_target_id in pending:
            session.add(
                ContentNode(
                    id=thought.id,
                    user_id=thought.user_id,
                    kind="thought",
                    title=None,
                    content_text=thought.content,
                    preview_text=summarize_preview(thought.content, limit=280),
                    visibility=_mapped_visibility(thought, visibility_policy),
                    status="ready",
                    topics=list(thought.topics or []),
                    metadata_json={
                        "source": "legacy_thought",
                        "legacy_thought_id": thought.id,
                        "migration_version": MIGRATION_VERSION,
                        "legacy_emotion": thought.emotion,
                        "visibility_policy": visibility_policy,
                    },
                    embedding=embedding,
                    cluster_id=None,
                    connection_count=thought.connection_count or 0,
                    reply_to_node_id=reply_target_id,
                    created_at=thought.created_at,
                    updated_at=thought.updated_at,
                )
            )
        session.flush()
        for thought, reply_target_id in reply_specs:
            edge_id = _reply_edge_id(thought.id, reply_target_id)
            existing_edge = session.get(NodeEdge, edge_id)
            if existing_edge is not None:
                if existing_edge.source_id != thought.id or existing_edge.target_id != reply_target_id:
                    raise LegacyThoughtMigrationConflict(f"node_edges.id {edge_id} conflicts with migrated reply")
                continue
            session.add(
                NodeEdge(
                    id=edge_id,
                    user_id=thought.user_id,
                    source_id=thought.id,
                    target_id=reply_target_id,
                    edge_type="reply",
                    weight=1.0,
                    explanation={"reason": "legacy_reply", "migration_version": MIGRATION_VERSION},
                    created_at=thought.created_at,
                    updated_at=thought.updated_at,
                )
            )
        if reconcile_projection:
            totals = {"nodes": 0, "semantic_edges": 0, "clusters": 0}
            for user_id in sorted(affected_user_ids):
                counts = reconcile_user_graph_projection(session, user_id)
                for key in totals:
                    totals[key] += counts[key]
            report = replace(
                report,
                projected_nodes=totals["nodes"],
                semantic_edges=totals["semantic_edges"],
                clusters=totals["clusters"],
            )
        session.commit()
        return report
    except Exception:
        session.rollback()
        raise


def _validated_embedding(value: object, content: str) -> tuple[list[float], bool]:
    if isinstance(value, list) and len(value) == EMBEDDING_DIMENSIONS:
        try:
            embedding = [float(item) for item in value]
        except (TypeError, ValueError):
            embedding = []
        if embedding and all(isfinite(item) for item in embedding):
            return embedding, False
    return embed_text(content), True


def _is_same_migrated_thought(
    node: ContentNode,
    thought: Thought,
    reply_target_id: str | None,
    visibility_policy: VisibilityPolicy,
) -> bool:
    metadata = node.metadata_json or {}
    return (
        metadata.get("source") == "legacy_thought"
        and metadata.get("legacy_thought_id") == thought.id
        and metadata.get("migration_version") == MIGRATION_VERSION
        and node.user_id == thought.user_id
        and node.kind == "thought"
        and node.content_text == thought.content
        and metadata.get("visibility_policy") == visibility_policy
        and node.visibility == _mapped_visibility(thought, visibility_policy)
        and list(node.topics or []) == list(thought.topics or [])
        and node.reply_to_node_id == reply_target_id
        and node.created_at == thought.created_at
    )


def _reply_edge_id(source_id: str, target_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"thoughtgraph:legacy-reply:{source_id}:{target_id}"))


def _mapped_visibility(thought: Thought, visibility_policy: VisibilityPolicy) -> str:
    if visibility_policy == "private":
        return "private"
    return thought.visibility or "public"
