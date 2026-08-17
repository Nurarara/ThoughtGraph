from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content_node import ContentNode
from app.models.media_asset import MediaAsset
from app.models.node_cluster import NodeCluster
from app.models.node_edge import NodeEdge
from app.models.user import User
from app.schemas.node import NodeCreate, NodeRead
from app.services.event_service import emit_event
from app.services.graph_service import recompute_local_graph_projection, summarize_node_topics
from app.services.media_service import register_external_media, to_media_asset_read
from app.services.social_service import can_view_node
from app.services.text_analysis import embed_text
from app.services.user_service import ensure_user_exists
from app.services.workflow_service import enqueue_job, should_run_inline


def create_node(session: Session, user_id: str, payload: NodeCreate) -> NodeRead:
    ensure_user_exists(session, user_id)
    if payload.kind in {"image", "video"} and payload.media is None:
        raise ValueError(f"{payload.kind} nodes require media")
    if payload.kind == "link" and payload.link_url is None:
        raise ValueError("link nodes require link_url")
    if payload.kind == "thought" and not (payload.content_text or payload.title):
        raise ValueError("thought nodes require content_text or title")

    reply_to: ContentNode | None = None
    quote_of: ContentNode | None = None
    if payload.reply_to_node_id:
        reply_to = session.get(ContentNode, payload.reply_to_node_id)
        if reply_to is None or not can_view_node(session, user_id, reply_to):
            raise ValueError("reply target not found")
    if payload.quote_of_node_id:
        quote_of = session.get(ContentNode, payload.quote_of_node_id)
        if quote_of is None or not can_view_node(session, user_id, quote_of):
            raise ValueError("quote target not found")

    media_asset: MediaAsset | None = None
    if payload.kind in {"image", "video"} and payload.media is not None:
        media_asset = _resolve_media_asset(session, user_id, payload.kind, payload.media)

    embedding_source = " ".join(
        part
        for part in (
            payload.title or "",
            payload.content_text or "",
            str(payload.link_url) if payload.link_url else "",
            str(payload.media.url) if payload.media and payload.media.url else "",
            media_asset.filename if media_asset and media_asset.filename else "",
        )
        if part
    ).strip()
    if not embedding_source:
        raise ValueError("node content cannot be empty")

    preview_text, topics = summarize_node_topics(embedding_source)
    node = ContentNode(
        user_id=user_id,
        kind=payload.kind,
        title=payload.title,
        content_text=payload.content_text or "",
        preview_text=preview_text,
        visibility=payload.visibility,
        link_url=str(payload.link_url) if payload.link_url else None,
        media_asset_id=media_asset.id if media_asset else None,
        topics=topics,
        metadata_json={"source": "phase_1", "phase": 4},
        embedding=embed_text(embedding_source),
        reply_to_node_id=reply_to.id if reply_to else None,
        quote_of_node_id=quote_of.id if quote_of else None,
    )
    session.add(node)
    session.flush()

    for related, edge_type in ((reply_to, "reply"), (quote_of, "quote")):
        if related is None:
            continue
        edge = NodeEdge(
            user_id=user_id,
            source_id=node.id,
            target_id=related.id,
            edge_type=edge_type,
            weight=1.0,
            explanation={"reason": edge_type, "target_user_id": related.user_id},
        )
        session.add(edge)
        session.flush()
        emit_event(
            session,
            event_type="edge_created",
            aggregate_type="node_edge",
            aggregate_id=edge.id,
            actor_id=user_id,
            payload=edge.explanation,
        )

    emit_event(
        session,
        event_type="node_created",
        aggregate_type="content_node",
        aggregate_id=node.id,
        actor_id=user_id,
        payload={"kind": node.kind, "visibility": node.visibility},
    )
    emit_event(
        session,
        event_type="node_embedded",
        aggregate_type="content_node",
        aggregate_id=node.id,
        actor_id=user_id,
        payload={"embedding_dimensions": len(node.embedding), "topics": node.topics},
    )
    job = enqueue_job(
        session,
        job_type="graph_projection",
        aggregate_type="content_node",
        aggregate_id=node.id,
        payload={"user_id": user_id},
        actor_id=user_id,
    )
    session.commit()

    if should_run_inline():
        recompute_local_graph_projection(session, job)

    return get_node(session, user_id, node.id)


def list_nodes(session: Session, user_id: str) -> list[NodeRead]:
    nodes = list(
        session.scalars(
            select(ContentNode).where(ContentNode.user_id == user_id).order_by(ContentNode.created_at.desc())
        )
    )
    return [_to_node_read(session, node) for node in nodes]


def get_node(session: Session, user_id: str, node_id: str) -> NodeRead:
    node = session.get(ContentNode, node_id)
    if node is None or not can_view_node(session, user_id, node):
        raise ValueError("node not found")
    return _to_node_read(session, node)


def get_thread(session: Session, user_id: str, node_id: str):
    root = session.get(ContentNode, node_id)
    if root is None or not can_view_node(session, user_id, root):
        raise ValueError("node not found")
    replies = list(
        session.scalars(
            select(ContentNode).where(ContentNode.reply_to_node_id == node_id).order_by(ContentNode.created_at.asc())
        )
    )
    visible_replies = [_to_node_read(session, reply) for reply in replies if can_view_node(session, user_id, reply)]
    quoted = session.get(ContentNode, root.quote_of_node_id) if root.quote_of_node_id else None
    return {
        "root": _to_node_read(session, root),
        "replies": visible_replies,
        "quoted_node": _to_node_read(session, quoted) if quoted and can_view_node(session, user_id, quoted) else None,
    }


def _to_node_read(session: Session, node: ContentNode) -> NodeRead:
    cluster = session.get(NodeCluster, node.cluster_id) if node.cluster_id else None
    media = session.get(MediaAsset, node.media_asset_id) if node.media_asset_id else None
    author = session.get(User, node.user_id)
    media_read = to_media_asset_read(media) if media else None
    return NodeRead(
        id=node.id,
        kind=node.kind,
        title=node.title,
        content_text=node.content_text,
        preview_text=node.preview_text,
        visibility=node.visibility,
        created_at=node.created_at,
        updated_at=node.updated_at,
        topics=node.topics,
        cluster_id=node.cluster_id,
        cluster_label=cluster.label if cluster else None,
        cluster_color=cluster.color if cluster else None,
        connection_count=node.connection_count,
        author_id=node.user_id,
        author_display_name=author.display_name if author else None,
        media_asset_id=media.id if media else None,
        media_kind=media.kind if media else None,
        media_status=media.status if media else None,
        thumbnail_url=media_read.thumbnail_url if media_read else None,
        playback_url=media_read.playback_url if media_read else None,
        duration_seconds=media.duration_seconds if media else None,
        media_url=media_read.original_url if media_read else None,
        link_url=node.link_url,
        reply_to_node_id=node.reply_to_node_id,
        quote_of_node_id=node.quote_of_node_id,
        metadata_json=node.metadata_json or {},
    )


def _resolve_media_asset(session: Session, user_id: str, node_kind: str, media_payload) -> MediaAsset:
    if media_payload.asset_id:
        asset = session.get(MediaAsset, media_payload.asset_id)
        if asset is None or asset.user_id != user_id:
            raise ValueError("media asset not found")
        if asset.kind != node_kind:
            raise ValueError("media kind does not match node kind")
        return asset
    if media_payload.url:
        external_asset = register_external_media(session, user_id, media_payload)
        external_asset.kind = node_kind
        session.add(external_asset)
        session.flush()
        return external_asset
    raise ValueError("media nodes require asset_id or url")
