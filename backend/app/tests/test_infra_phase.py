from __future__ import annotations

import asyncio

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.cluster import Cluster
from app.models.content_node import ContentNode
from app.models.domain_event import DomainEvent
from app.models.infra_read_models import (
    GraphReadModelNode,
    InfraDeadLetterRecord,
    InfraEventConsumerState,
    SearchIndexDocument,
)
from app.models.media_asset import MediaAsset
from app.models.node_cluster import NodeCluster
from app.models.node_edge import NodeEdge
from app.models.thought import Thought
from app.models.user import User
from app.services.graph_service import _refresh_clusters_for_node
from app.services.graph_read_model import query_graph_read_model, rebuild_graph_read_model
from app.services.infra_event_bus import InProcessEventBus
from app.services.media_pipeline_service import _video_poster_svg
from app.services.ops_status import build_ops_status
from app.services.search_read_model import hybrid_search, rebuild_search_index
from app.services.social_service import request_friendship, respond_friendship
from app.services.storage_service import copy_storage_object, storage_path, write_bytes
from app.services.text_analysis import embed_text


def test_in_process_event_bus_idempotency_dead_letter_and_replay() -> None:
    session = _session()
    event = DomainEvent(
        event_type="node_created",
        aggregate_type="content_node",
        aggregate_id="node-1",
        actor_id="local-user",
        payload={"idempotency_key": "node-1-created"},
    )
    session.add(event)
    session.commit()
    calls = {"ok": 0, "retry": 0}
    bus = InProcessEventBus()

    async def ok_consumer(received: DomainEvent) -> dict:
        calls["ok"] += 1
        return {"event_id": received.id}

    async def failing_consumer(_: DomainEvent) -> None:
        calls["retry"] += 1
        raise RuntimeError("temporary projector failure")

    bus.register("search-index-projector", ["node_created"], ok_consumer)
    bus.register("graph-projector", ["node_created"], failing_consumer)

    first = asyncio.run(bus.dispatch_event(session, event))
    second = asyncio.run(bus.dispatch_event(session, event))
    session.commit()

    assert [outcome.status for outcome in first.outcomes] == ["succeeded", "failed"]
    assert any(outcome.idempotent_skip for outcome in second.outcomes)
    assert calls["ok"] == 1
    assert session.scalar(select(InfraDeadLetterRecord)).replay_status == "pending"

    async def recovered_consumer(_: DomainEvent) -> dict:
        calls["retry"] += 1
        return {"recovered": True}

    bus.register("graph-projector", ["node_created"], recovered_consumer)
    replay = asyncio.run(bus.replay_dead_letters(session))
    session.commit()

    assert replay.replayed == 1
    assert session.scalar(select(InfraDeadLetterRecord)).replay_status == "replayed"
    assert session.scalar(select(InfraEventConsumerState).where(InfraEventConsumerState.consumer_name == "graph-projector")).status == "succeeded"


def test_dispatch_unprocessed_skips_events_already_handled_by_all_consumers() -> None:
    session = _session()
    handled = DomainEvent(event_type="node_created", aggregate_type="content_node", aggregate_id="node-1")
    pending = DomainEvent(event_type="node_created", aggregate_type="content_node", aggregate_id="node-2")
    session.add_all([handled, pending])
    session.flush()
    session.add(
        InfraEventConsumerState(
            consumer_name="search-index-projector",
            event_id=handled.id,
            event_type=handled.event_type,
            idempotency_key=f"search-index-projector:{handled.id}",
            status="succeeded",
            attempts=1,
        )
    )
    session.commit()

    calls: list[str] = []
    bus = InProcessEventBus()

    def consumer(event: DomainEvent) -> dict:
        calls.append(event.aggregate_id)
        return {"event_id": event.id}

    bus.register("search-index-projector", ["node_created"], consumer)

    result = asyncio.run(bus.dispatch_unprocessed(session, limit=1))

    assert result.dispatched == 1
    assert calls == ["node-2"]


def test_storage_paths_are_contained_under_configured_root(tmp_path, monkeypatch) -> None:
    storage_root = tmp_path / "media"
    monkeypatch.setenv("THOUGHTGRAPH_MEDIA_STORAGE_DIR", str(storage_root))
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        valid = write_bytes("users/local-user/original.png", b"image")
        assert valid == (storage_root / "users" / "local-user" / "original.png").resolve()
        assert valid.read_bytes() == b"image"

        copied = copy_storage_object("users/local-user/original.png", "derived/thumbnail.png")
        assert copied == (storage_root / "derived" / "thumbnail.png").resolve()
        assert copied.read_bytes() == b"image"

        for malicious_key in (
            "../outside.txt",
            "users/../../outside.txt",
            str((tmp_path / "absolute.txt").resolve()),
            "",
            ".",
        ):
            try:
                storage_path(malicious_key)
            except ValueError:
                pass
            else:  # pragma: no cover - assertion guard
                raise AssertionError(f"unsafe storage key was accepted: {malicious_key!r}")

        assert not (tmp_path / "outside.txt").exists()
        assert not (tmp_path / "absolute.txt").exists()
    finally:
        get_settings.cache_clear()


def test_friendship_events_follow_actual_state_changes_only() -> None:
    session = _session()
    _seed_user(session, "local-user")
    _seed_user(session, "maya-chen")

    request_friendship(session, "local-user", "maya-chen")
    request_friendship(session, "maya-chen", "local-user")
    request_friendship(session, "local-user", "maya-chen")

    event_types = list(session.scalars(select(DomainEvent.event_type).order_by(DomainEvent.created_at.asc())))

    assert event_types == ["friendship_requested", "friendship_accepted"]


def test_respond_friendship_rejects_already_handled_requests_without_noop_event() -> None:
    session = _session()
    _seed_user(session, "local-user")
    _seed_user(session, "maya-chen")

    request_friendship(session, "local-user", "maya-chen")
    respond_friendship(session, "maya-chen", "local-user", accept=True)
    try:
        respond_friendship(session, "maya-chen", "local-user", accept=True)
    except ValueError as exc:
        assert str(exc) == "friend request not found"
    else:  # pragma: no cover - assertion guard
        raise AssertionError("already accepted friendship response should fail")

    event_types = list(session.scalars(select(DomainEvent.event_type).order_by(DomainEvent.created_at.asc())))

    assert event_types == ["friendship_requested", "friendship_accepted"]


def test_cluster_merge_keeps_existing_cluster_identifier() -> None:
    session = _session()
    _seed_user(session)
    first_cluster = NodeCluster(user_id="local-user", label="Alpha", color="#2f7be5", summary="", node_count=1)
    second_cluster = NodeCluster(user_id="local-user", label="Beta", color="#2aa876", summary="", node_count=1)
    session.add_all([first_cluster, second_cluster])
    session.flush()
    first = ContentNode(
        user_id="local-user",
        kind="thought",
        title="Alpha graph",
        content_text="Alpha graph",
        preview_text="Alpha graph",
        visibility="private",
        topics=["graph"],
        embedding=embed_text("alpha graph"),
        cluster_id=first_cluster.id,
    )
    second = ContentNode(
        user_id="local-user",
        kind="thought",
        title="Beta graph",
        content_text="Beta graph",
        preview_text="Beta graph",
        visibility="private",
        topics=["graph"],
        embedding=embed_text("beta graph"),
        cluster_id=second_cluster.id,
    )
    session.add_all([first, second])
    session.flush()
    session.add(
        NodeEdge(
            user_id="local-user",
            source_id=first.id,
            target_id=second.id,
            edge_type="semantic_similarity",
            weight=0.9,
            explanation={},
        )
    )
    session.flush()
    original_cluster_ids = {first_cluster.id, second_cluster.id}

    _refresh_clusters_for_node(session, "local-user", first.id)

    remaining_clusters = list(session.scalars(select(NodeCluster)))
    assert len(remaining_clusters) == 1
    assert remaining_clusters[0].id in original_cluster_ids
    assert {first.cluster_id, second.cluster_id} == {remaining_clusters[0].id}


def test_video_poster_generation_handles_missing_metadata_json() -> None:
    asset = MediaAsset(user_id="local-user", kind="video", source_kind="upload", filename="clip.mp4", metadata_json=None)

    poster = _video_poster_svg(asset)

    assert "Playback preview" in poster


def test_search_index_hybrid_results_are_explainable_and_postgres_derived() -> None:
    session = _session()
    _seed_user(session)
    node = ContentNode(
        user_id="local-user",
        kind="thought",
        title="Provenance trails",
        content_text="Claims need evidence, provenance, contradiction trails, and source context.",
        preview_text="Claims need evidence and provenance.",
        visibility="private",
        topics=["provenance", "evidence"],
        embedding=embed_text("provenance evidence contradiction trails"),
    )
    session.add(node)
    session.commit()

    rebuild = rebuild_search_index(session, user_id="local-user")
    results = hybrid_search(session, user_id="local-user", query="provenance evidence", limit=5)

    assert rebuild.indexed == 1
    assert session.scalar(select(SearchIndexDocument)).source_table == "content_nodes"
    assert results.items[0].source_id == node.id
    assert results.items[0].score.lexical > 0
    assert results.items[0].score.semantic > 0
    assert results.items[0].explanation["source"] == "postgres-derived-search-index"


def test_graph_read_model_is_rebuildable_query_boundary_and_ops_reports_readiness() -> None:
    session = _session()
    _seed_user(session)
    first = ContentNode(
        user_id="local-user",
        kind="thought",
        title="Graph query boundary",
        content_text="Read models should be rebuilt from canonical graph storage.",
        preview_text="Read models should be rebuilt.",
        visibility="private",
        topics=["graph"],
        embedding=embed_text("graph read model"),
    )
    second = ContentNode(
        user_id="local-user",
        kind="thought",
        title="Projection store",
        content_text="Projection stores are derived and safe to drop.",
        preview_text="Projection stores are derived.",
        visibility="private",
        topics=["graph"],
        embedding=embed_text("projection graph store"),
    )
    session.add_all([first, second])
    session.flush()
    session.add(
        NodeEdge(
            user_id="local-user",
            source_id=first.id,
            target_id=second.id,
            edge_type="semantic_similarity",
            weight=0.81,
            explanation={"reason": "semantic_overlap"},
        )
    )
    session.commit()

    projection = rebuild_graph_read_model(session, user_id="local-user", reason="test")
    graph = query_graph_read_model(session, user_id="local-user")
    ops = build_ops_status(session, event_bus=InProcessEventBus())

    assert projection.nodes == 2
    assert projection.edges == 1
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.nodes[0].derived_from["rebuildable"] is True
    assert graph.explanation.startswith("query served from graph_read_model")
    assert session.scalar(select(GraphReadModelNode)).derived_from["canonical"] is False
    assert ops.replay_readiness.ready is True
    assert {partition.name for partition in ops.partitions} >= {"search_index", "graph_read_model", "dead_letters"}


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _seed_user(session: Session, user_id: str = "local-user") -> None:
    session.add(User(id=user_id, display_name=user_id.replace("-", " ").title()))
    session.commit()
