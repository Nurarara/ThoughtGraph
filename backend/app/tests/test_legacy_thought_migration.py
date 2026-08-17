from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.cli.migrate_legacy_thoughts import main as migration_cli
from app.db.session import set_database_url
from app.main import create_app
from app.models import ContentNode, DomainEvent, NodeCluster, NodeEdge, Thought, User, WorkflowJob
from app.models.base import Base
from app.services.legacy_thought_migration import (
    LegacyThoughtMigrationConflict,
    migrate_legacy_thoughts,
)
from app.services.graph_service import build_graph_response
from app.services.text_analysis import embed_text


def _database(tmp_path: Path):
    path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}", future=True)
    Base.metadata.create_all(engine)
    return path, engine


def _seed_user(session: Session, user_id: str) -> None:
    session.add(User(id=user_id, display_name=user_id, is_public=True))


def test_migration_preserves_fields_maps_replies_and_is_idempotent(tmp_path: Path) -> None:
    _, engine = _database(tmp_path)
    created = datetime(2025, 3, 4, 12, 30, tzinfo=timezone.utc)
    with Session(engine) as session:
        _seed_user(session, "legacy-user")
        root = Thought(
            id="00000000-0000-0000-0000-000000000001",
            user_id="legacy-user",
            content="A private legacy idea about durable knowledge.",
            emotion="growth",
            topics=["knowledge", "systems"],
            vector=embed_text("A private legacy idea about durable knowledge."),
            visibility="private",
            created_at=created,
            updated_at=created,
        )
        reply = Thought(
            id="00000000-0000-0000-0000-000000000002",
            user_id="legacy-user",
            content="A reply with a malformed vector.",
            emotion="neutral",
            topics=["reply"],
            vector=[1.0],
            visibility="friends",
            reply_to_id=root.id,
            created_at=created,
            updated_at=created,
        )
        session.add_all([root, reply])
        session.commit()

        dry_run = migrate_legacy_thoughts(session, apply=False)
        assert dry_run.would_migrate == 2
        assert dry_run.reply_edges == 1
        assert dry_run.embeddings_recomputed == 1
        assert session.scalar(select(func.count()).select_from(ContentNode)) == 0

        applied = migrate_legacy_thoughts(session, apply=True)
        assert applied.applied is True
        assert applied.would_migrate == 2
        migrated_root = session.get(ContentNode, root.id)
        migrated_reply = session.get(ContentNode, reply.id)
        assert migrated_root is not None
        assert migrated_root.user_id == root.user_id
        assert migrated_root.content_text == root.content
        assert migrated_root.visibility == "private"
        assert migrated_root.topics == root.topics
        assert migrated_root.created_at == created.replace(tzinfo=None)
        assert migrated_root.metadata_json == {
            "source": "legacy_thought",
            "legacy_thought_id": root.id,
            "migration_version": 1,
            "legacy_emotion": "growth",
            "visibility_policy": "preserve",
        }
        assert migrated_reply is not None
        assert migrated_reply.reply_to_node_id == root.id
        assert len(migrated_reply.embedding) == 256
        assert session.scalar(select(func.count()).select_from(NodeEdge)) == 1

        repeated = migrate_legacy_thoughts(session, apply=True)
        assert repeated.would_migrate == 0
        assert repeated.already_migrated == 2
        assert session.scalar(select(func.count()).select_from(ContentNode)) == 2
        assert session.scalar(select(func.count()).select_from(NodeEdge)) == 1
    engine.dispose()


def test_conflict_rolls_back_without_partial_import(tmp_path: Path) -> None:
    _, engine = _database(tmp_path)
    with Session(engine) as session:
        _seed_user(session, "legacy-user")
        session.add_all(
            [
                Thought(id="conflict", user_id="legacy-user", content="legacy", vector=embed_text("legacy")),
                Thought(id="safe", user_id="legacy-user", content="safe", vector=embed_text("safe")),
                ContentNode(
                    id="conflict",
                    user_id="legacy-user",
                    kind="thought",
                    content_text="different canonical content",
                    preview_text="different",
                    visibility="private",
                    status="ready",
                    topics=[],
                    metadata_json={},
                    embedding=embed_text("different"),
                ),
            ]
        )
        session.commit()

        with pytest.raises(LegacyThoughtMigrationConflict):
            migrate_legacy_thoughts(session, apply=True)
        assert session.get(ContentNode, "safe") is None
    engine.dispose()


def test_apply_cli_creates_verified_backup_before_migration(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path, engine = _database(tmp_path)
    with Session(engine) as session:
        _seed_user(session, "legacy-user")
        session.add(Thought(id="cli-legacy", user_id="legacy-user", content="CLI migration", vector=[]))
        session.commit()
    engine.dispose()

    assert migration_cli(["--database", str(path), "--apply"]) == 0
    output = capsys.readouterr().out
    assert '"status": "applied"' in output
    backups = list(tmp_path.glob("legacy.db.backup-*"))
    assert len(backups) == 1
    assert backups[0].stat().st_size > 0

    migrated_engine = create_engine(f"sqlite:///{path.as_posix()}", future=True)
    with Session(migrated_engine) as session:
        assert session.get(ContentNode, "cli-legacy") is not None
    migrated_engine.dispose()


def test_private_visibility_override_is_idempotent_and_owner_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, engine = _database(tmp_path)
    with Session(engine) as session:
        _seed_user(session, "local-user")
        _seed_user(session, "private-owner")
        session.add(
            Thought(
                id="formerly-public",
                user_id="private-owner",
                content="This legacy thought used to be public.",
                topics=["privacy"],
                vector=embed_text("This legacy thought used to be public."),
                visibility="public",
            )
        )
        session.commit()

        applied = migrate_legacy_thoughts(session, apply=True, visibility_policy="private")
        assert applied.would_migrate == 1
        assert applied.visibility_policy == "private"
        node = session.get(ContentNode, "formerly-public")
        assert node is not None
        assert node.visibility == "private"
        assert node.metadata_json["visibility_policy"] == "private"

        repeated = migrate_legacy_thoughts(session, apply=True, visibility_policy="private")
        assert repeated.would_migrate == 0
        assert repeated.already_migrated == 1
        assert session.scalar(select(func.count()).select_from(ContentNode)) == 1
    engine.dispose()

    monkeypatch.setenv("THOUGHTGRAPH_ALLOW_DEV_USER_HEADER_IMPERSONATION", "true")
    get_settings.cache_clear()
    set_database_url(f"sqlite:///{path.as_posix()}")
    with TestClient(create_app()) as client:
        hidden = client.get("/api/nodes/formerly-public")
        assert hidden.status_code == 404
        owner_detail = client.get(
            "/api/nodes/formerly-public",
            headers={"X-ThoughtGraph-User": "private-owner"},
        )
        assert owner_detail.status_code == 200
        assert owner_detail.json()["visibility"] == "private"
    get_settings.cache_clear()


def test_projection_reconciliation_handles_already_migrated_nodes_and_is_stable(tmp_path: Path) -> None:
    _, engine = _database(tmp_path)
    shared_text = "Graph provenance connects evidence and trustworthy knowledge."
    with Session(engine) as session:
        _seed_user(session, "legacy-user")
        session.add_all(
            [
                Thought(
                    id="projection-a",
                    user_id="legacy-user",
                    content=shared_text,
                    topics=["graph", "provenance"],
                    vector=embed_text(shared_text),
                    visibility="private",
                ),
                Thought(
                    id="projection-b",
                    user_id="legacy-user",
                    content=f"{shared_text} Again.",
                    topics=["graph", "provenance"],
                    vector=embed_text(f"{shared_text} Again."),
                    visibility="private",
                ),
            ]
        )
        session.commit()

        migrate_legacy_thoughts(session, apply=True)
        assert all(node.cluster_id is None for node in session.scalars(select(ContentNode)))

        reconciled = migrate_legacy_thoughts(session, apply=True, reconcile_projection=True)
        assert reconciled.already_migrated == 2
        assert reconciled.projection_users == 1
        assert reconciled.projected_nodes == 2
        assert reconciled.semantic_edges == 1
        assert reconciled.clusters == 1
        nodes = list(session.scalars(select(ContentNode).order_by(ContentNode.id)))
        assert all(node.cluster_id is not None for node in nodes)
        cluster_ids = {node.cluster_id for node in nodes}
        edge_ids = set(session.scalars(select(NodeEdge.id)))
        assert len(cluster_ids) == 1
        assert len(edge_ids) == 1
        assert session.scalar(select(func.count()).select_from(DomainEvent)) == 0
        assert session.scalar(select(func.count()).select_from(WorkflowJob)) == 0

        graph = build_graph_response(session, "legacy-user")
        assert all((node.x, node.y) != (0.0, 0.0) for node in graph.nodes)

        repeated = migrate_legacy_thoughts(session, apply=True, reconcile_projection=True)
        assert repeated.already_migrated == 2
        assert {node.cluster_id for node in session.scalars(select(ContentNode))} == cluster_ids
        assert set(session.scalars(select(NodeEdge.id))) == edge_ids
        assert session.scalar(select(func.count()).select_from(NodeCluster)) == 1
        assert session.scalar(select(func.count()).select_from(DomainEvent)) == 0
        assert session.scalar(select(func.count()).select_from(WorkflowJob)) == 0
    engine.dispose()


def test_migrated_thoughts_work_in_active_api_and_keep_privacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, engine = _database(tmp_path)
    with Session(engine) as session:
        _seed_user(session, "local-user")
        _seed_user(session, "other-user")
        session.add_all(
            [
                Thought(
                    id="own-legacy",
                    user_id="local-user",
                    content="Provenance makes a knowledge graph trustworthy.",
                    topics=["provenance"],
                    vector=embed_text("Provenance makes a knowledge graph trustworthy."),
                    visibility="private",
                ),
                Thought(
                    id="other-private",
                    user_id="other-user",
                    content="Private thought belonging to someone else.",
                    topics=["private"],
                    vector=embed_text("Private thought belonging to someone else."),
                    visibility="private",
                ),
            ]
        )
        session.commit()
        migrate_legacy_thoughts(session, apply=True)
    engine.dispose()

    monkeypatch.setenv("THOUGHTGRAPH_ALLOW_DEV_USER_HEADER_IMPERSONATION", "true")
    get_settings.cache_clear()
    set_database_url(f"sqlite:///{path.as_posix()}")
    with TestClient(create_app()) as client:
        me = client.get("/api/users/me")
        assert me.status_code == 200
        assert me.json()["node_count"] == 1

        graph = client.get("/api/graph")
        assert graph.status_code == 200
        assert [node["id"] for node in graph.json()["nodes"]] == ["own-legacy"]

        detail = client.get("/api/nodes/own-legacy")
        assert detail.status_code == 200
        assert detail.json()["content_text"].startswith("Provenance")

        search = client.get("/api/graph/search?q=provenance")
        assert search.status_code == 200
        assert search.json()["items"][0]["node_id"] == "own-legacy"

        forbidden = client.get("/api/nodes/other-private")
        assert forbidden.status_code == 404
    get_settings.cache_clear()
