from __future__ import annotations

import base64
from html import escape

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.graph_snapshot import GraphSnapshot
from app.models.user import User
from app.schemas.snapshot import SnapshotRead
from app.services.graph_pipeline import get_graph_response
from app.services.user_service import ensure_user_exists


def _to_data_uri(svg: str) -> str:
    return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode('utf-8')).decode('ascii')}"


def _render_snapshot_svg(display_name: str, mood: str, caption: str, metadata: dict) -> str:
    top_clusters = metadata.get("top_clusters", [])[:3]
    cluster_lines = "".join(
        f"<text x='80' y='{350 + index * 48}' fill='#e8e6f0' font-size='30'>{escape(label)}</text>"
        for index, label in enumerate(top_clusters or ["General Reflection"])
    )
    return f"""
    <svg xmlns='http://www.w3.org/2000/svg' width='1200' height='1200' viewBox='0 0 1200 1200'>
      <defs>
        <linearGradient id='g' x1='0' x2='1'>
          <stop offset='0%' stop-color='#7c5bf5'/>
          <stop offset='50%' stop-color='#4a8eff'/>
          <stop offset='100%' stop-color='#22d3ee'/>
        </linearGradient>
      </defs>
      <rect width='1200' height='1200' fill='#08080f'/>
      <circle cx='980' cy='220' r='200' fill='rgba(74,142,255,0.15)'/>
      <circle cx='260' cy='920' r='240' fill='rgba(124,91,245,0.18)'/>
      <text x='80' y='110' fill='#22d3ee' font-family='monospace' font-size='22'>THOUGHTGRAPH SNAPSHOT</text>
      <text x='80' y='220' fill='#e8e6f0' font-family='serif' font-size='72'>{escape(display_name)}</text>
      <text x='80' y='290' fill='#8a88a0' font-family='sans-serif' font-size='28'>Mood: {escape(mood)}</text>
      <text x='80' y='450' fill='#8a88a0' font-family='monospace' font-size='20'>Top clusters</text>
      {cluster_lines}
      <text x='80' y='640' fill='#e8e6f0' font-family='sans-serif' font-size='36'>{escape(caption or 'A captured state of mind.')}</text>
      <text x='80' y='980' fill='#8a88a0' font-family='sans-serif' font-size='28'>Nodes: {metadata.get('node_count', 0)} • Clusters: {metadata.get('cluster_count', 0)}</text>
      <text x='80' y='1080' fill='url(#g)' font-family='serif' font-size='58'>ThoughtGraph</text>
    </svg>
    """.strip()


def _serialize_snapshot(session: Session, snapshot: GraphSnapshot) -> SnapshotRead:
    user = session.get(User, snapshot.user_id)
    return SnapshotRead(
        id=snapshot.id,
        user_id=snapshot.user_id,
        user_display_name=user.display_name if user else snapshot.user_id,
        image_url=snapshot.image_url,
        thumbnail_url=snapshot.thumbnail_url,
        metadata=snapshot.metadata_json,
        caption=snapshot.caption,
        is_public=snapshot.is_public,
        created_at=snapshot.created_at,
    )


def create_snapshot(session: Session, user_id: str, caption: str, is_public: bool) -> SnapshotRead:
    user = ensure_user_exists(session, user_id)
    graph = get_graph_response(session, user_id)
    metadata = {
        "node_count": len(graph.nodes),
        "cluster_count": len(graph.clusters),
        "top_clusters": [cluster.label for cluster in graph.clusters[:3]],
        "mood": graph.mood,
    }
    image_url = _to_data_uri(_render_snapshot_svg(user.display_name, graph.mood, caption, metadata))
    snapshot = GraphSnapshot(
        user_id=user_id,
        image_url=image_url,
        thumbnail_url=image_url,
        metadata_json=metadata,
        caption=caption,
        is_public=is_public,
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return _serialize_snapshot(session, snapshot)


def list_snapshots(session: Session, user_id: str) -> list[SnapshotRead]:
    snapshots = list(
        session.scalars(
            select(GraphSnapshot).where(GraphSnapshot.user_id == user_id).order_by(desc(GraphSnapshot.created_at))
        )
    )
    return [_serialize_snapshot(session, snapshot) for snapshot in snapshots]


def list_recent_public_snapshots(session: Session, limit: int = 12) -> list[SnapshotRead]:
    snapshots = list(
        session.scalars(
            select(GraphSnapshot)
            .where(GraphSnapshot.is_public.is_(True))
            .order_by(desc(GraphSnapshot.created_at))
            .limit(limit)
        )
    )
    return [_serialize_snapshot(session, snapshot) for snapshot in snapshots]


def get_snapshot(session: Session, snapshot_id: str, viewer_user_id: str | None = None) -> SnapshotRead | None:
    snapshot = session.get(GraphSnapshot, snapshot_id)
    if not snapshot:
        return None
    if not snapshot.is_public and viewer_user_id != snapshot.user_id:
        return None
    return _serialize_snapshot(session, snapshot)


def delete_snapshot(session: Session, user_id: str, snapshot_id: str) -> bool:
    snapshot = session.scalar(
        select(GraphSnapshot).where(GraphSnapshot.id == snapshot_id, GraphSnapshot.user_id == user_id)
    )
    if not snapshot:
        return False
    session.delete(snapshot)
    session.commit()
    return True
