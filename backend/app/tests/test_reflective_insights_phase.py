from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db as db_package
from app.core.config import get_settings
from app.db.session import init_db, set_database_url
from app.models.content_node import ContentNode
from app.models.domain_event import DomainEvent
from app.models.insight import Insight
from app.models.node_cluster import NodeCluster
from app.models.node_edge import NodeEdge
from app.models.user import User
from app.models.workflow_job import WorkflowJob
from app.main import create_app
from app.services.event_service import emit_event
from app.services.reflective_insight_service import (
    NON_CLINICAL_LIMITATION,
    enqueue_reflective_insight_loop,
    generate_reflective_insight_loop,
    list_persisted_attention_drift_insights,
)


def test_reflective_insight_loop_persists_report_insights_and_evidence(tmp_path: Path) -> None:
    set_database_url(f"sqlite:///{tmp_path / 'reflective.db'}")
    init_db()
    now = datetime(2026, 4, 24, 12, tzinfo=timezone.utc)

    with db_package.session.SessionLocal() as session:
        architecture = NodeCluster(
            user_id="local-user",
            label="Architecture",
            color="#2f7be5",
            summary="System design nodes.",
            node_count=4,
            density_score=1.5,
            dominant_topics=["architecture"],
        )
        reading = NodeCluster(
            user_id="local-user",
            label="Research",
            color="#2aa876",
            summary="Research links.",
            node_count=1,
            density_score=0.5,
            dominant_topics=["research"],
        )
        session.add_all([architecture, reading])
        session.flush()

        old_node = _node(
            session,
            "local-user",
            "Prior research",
            "Research notes from last week.",
            reading.id,
            ["research"],
            now - timedelta(days=10),
            kind="link",
            link_url="https://example.com/prior",
        )
        first = _node(
            session,
            "local-user",
            "Durable jobs",
            "Workflow jobs should carry expensive graph work.",
            architecture.id,
            ["architecture", "workflow"],
            now - timedelta(days=2),
        )
        second = _node(
            session,
            "local-user",
            "Evidence graph",
            "Insights need evidence trails back to visible graph nodes.",
            architecture.id,
            ["architecture", "evidence"],
            now - timedelta(days=1),
            kind="link",
            link_url="https://docs.example.com/graph",
        )
        session.add(
            NodeEdge(
                user_id="local-user",
                source_id=first.id,
                target_id=second.id,
                edge_type="semantic_similarity",
                weight=0.84,
                explanation={"shared_topics": ["architecture"]},
            )
        )
        emit_event(
            session,
            event_type="node_created",
            aggregate_type="content_node",
            aggregate_id=first.id,
            actor_id="local-user",
            payload={"kind": first.kind},
        )
        session.commit()

        result = generate_reflective_insight_loop(session, "local-user", reference_time=now)

        assert result.report.id
        assert result.report.thought_count == 2
        assert {insight.kind for insight in result.insights} == {
            "weekly_report",
            "attention_drift",
            "influence_summary",
            "cluster_growth_decay",
            "diversity_warning",
            "source_shaping_summary",
        }
        assert result.persisted_insight_ids
        assert any(insight.evidence for insight in result.insights)
        assert old_node.id not in [item.id for insight in result.insights for item in insight.evidence]


def test_reflective_insight_loop_can_run_through_workflow_job(tmp_path: Path) -> None:
    set_database_url(f"sqlite:///{tmp_path / 'reflective-job.db'}")
    init_db()
    now = datetime(2026, 4, 24, 12, tzinfo=timezone.utc)

    with db_package.session.SessionLocal() as session:
        cluster = NodeCluster(
            user_id="local-user",
            label="Sources",
            color="#2f7be5",
            summary="Source shaping nodes.",
            node_count=1,
            density_score=0.0,
            dominant_topics=["sources"],
        )
        session.add(cluster)
        session.flush()
        _node(
            session,
            "local-user",
            "Source mix",
            "Track how links shape the graph.",
            cluster.id,
            ["sources"],
            now - timedelta(days=1),
            kind="link",
            link_url="https://example.com/source",
        )
        session.commit()

        result = enqueue_reflective_insight_loop(session, "local-user", reference_time=now, run_inline=True)

        assert not isinstance(result, WorkflowJob)
        assert result.workflow_job_id
        job = session.get(WorkflowJob, result.workflow_job_id)
        assert job is not None
        assert job.status == "completed"
        assert job.result["insight_count"] == 6


def test_attention_drift_contract_is_lossless_stable_and_explainable(tmp_path: Path) -> None:
    set_database_url(f"sqlite:///{tmp_path / 'attention-contract.db'}")
    init_db()
    now = datetime(2026, 4, 24, 12, tzinfo=timezone.utc)
    with db_package.session.SessionLocal() as session:
        first_cluster = NodeCluster(user_id="local-user", label="Research", color="#123456")
        second_cluster = NodeCluster(user_id="local-user", label="Building", color="#654321")
        session.add_all([first_cluster, second_cluster])
        session.flush()
        for offset in (10, 9):
            _node(session, "local-user", f"Earlier {offset}", "Earlier research.", first_cluster.id, ["research"], now - timedelta(days=offset))
        for offset in (3, 2, 1):
            _node(session, "local-user", f"Current {offset}", "Current building.", second_cluster.id, ["building"], now - timedelta(days=offset))
        session.commit()

        first_run = generate_reflective_insight_loop(session, "local-user", reference_time=now)
        second_run = generate_reflective_insight_loop(session, "local-user", reference_time=now)
        first_id = first_run.persisted_insight_ids[1]
        assert second_run.persisted_insight_ids[1] == first_id
        assert len(session.scalars(select(Insight).where(
            Insight.kind == "reflective_attention_drift", Insight.stable_key.is_not(None)
        )).all()) == 1

        persisted = list_persisted_attention_drift_insights(session, "local-user", kind="attention_drift")[0]
        assert persisted.id == first_id
        assert persisted.status == "ready"
        assert persisted.window.current_start == now - timedelta(days=7)
        assert persisted.window.comparison_start == now - timedelta(days=14)
        assert persisted.metrics[0].unit == "proportion"
        assert "Count nodes per cluster" in persisted.metrics[0].method
        assert persisted.metrics[0].current == 1.0
        assert persisted.metrics[0].previous == 0.0
        assert persisted.confidence.sample_size == 5
        assert persisted.confidence.score > 0
        assert "not certainty about the user" in persisted.confidence.basis
        assert NON_CLINICAL_LIMITATION in persisted.limitations
        assert persisted.evidence
        assert all(session.get(ContentNode, item.id) is not None for item in persisted.evidence if item.evidence_type == "node")
        forbidden = ("diagnosis", "disorder", "mental illness")
        rendered = f"{persisted.title} {persisted.summary} {' '.join(persisted.limitations)}".lower()
        assert not any(term in rendered for term in forbidden)


def test_attention_drift_sparse_data_is_explicitly_insufficient(tmp_path: Path) -> None:
    set_database_url(f"sqlite:///{tmp_path / 'attention-sparse.db'}")
    init_db()
    now = datetime(2026, 4, 24, 12, tzinfo=timezone.utc)
    with db_package.session.SessionLocal() as session:
        cluster = NodeCluster(user_id="local-user", label="Sparse", color="#123456")
        session.add(cluster)
        session.flush()
        _node(session, "local-user", "Only node", "Not enough evidence.", cluster.id, ["sparse"], now - timedelta(days=1))
        for offset in (9, 10, 11):
            _node(
                session, "local-user", f"Earlier {offset}", "Earlier evidence.", cluster.id,
                ["sparse"], now - timedelta(days=offset),
            )
        session.commit()
        generate_reflective_insight_loop(session, "local-user", reference_time=now)
        persisted = list_persisted_attention_drift_insights(session, "local-user", kind="attention_drift")[0]
        assert persisted.status == "insufficient_data"
        assert persisted.confidence.score == 0
        assert persisted.confidence.label == "low"
        assert persisted.evidence == []
        assert persisted.summary.startswith("There is not enough saved activity")


def test_attention_feedback_is_owner_scoped_reversible_and_audited(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("THOUGHTGRAPH_ALLOW_DEV_USER_HEADER_IMPERSONATION", "true")
    get_settings.cache_clear()
    set_database_url(f"sqlite:///{tmp_path / 'attention-feedback.db'}")
    app = create_app()
    with TestClient(app) as client:
        run = client.post("/api/reflective-insights/run", json={"run_inline": True})
        assert run.status_code == 200
        insight_id = run.json()["persisted_insight_ids"][1]

        owner_list = client.get("/api/reflective-insights?kind=attention_drift")
        assert owner_list.status_code == 200
        assert owner_list.json()[0]["id"] == insight_id
        feedback = client.patch(
            f"/api/reflective-insights/{insight_id}/feedback",
            json={"dismissed": True, "correction": "wrong_evidence", "annotation": "This theme label is misleading."},
        )
        assert feedback.status_code == 200
        assert feedback.json()["feedback"]["dismissed"] is True
        assert feedback.json()["feedback"]["correction"] == "wrong_evidence"
        assert feedback.json()["feedback"]["updated_at"]
        assert client.get("/api/reflective-insights?kind=attention_drift").json() == []
        assert client.get("/api/reflective-insights?kind=attention_drift&include_dismissed=true").json()[0]["feedback"]["annotation"] == "This theme label is misleading."

        restored = client.patch(
            f"/api/reflective-insights/{insight_id}/feedback",
            json={"dismissed": False, "correction": None, "annotation": None},
        )
        assert restored.status_code == 200
        assert restored.json()["feedback"]["dismissed"] is False
        assert restored.json()["feedback"]["correction"] is None
        assert restored.json()["feedback"]["annotation"] is None

        other_headers = {"X-ThoughtGraph-User": "maya-chen"}
        assert client.get("/api/reflective-insights", headers=other_headers).json() == []
        denied = client.patch(
            f"/api/reflective-insights/{insight_id}/feedback",
            headers=other_headers,
            json={"dismissed": True},
        )
        assert denied.status_code == 404
        invalid = client.patch(
            f"/api/reflective-insights/{insight_id}/feedback",
            json={"correction": "diagnosis", "annotation": "x" * 1001},
        )
        assert invalid.status_code == 422
        assert client.patch(f"/api/reflective-insights/{insight_id}/feedback", json={}).status_code == 422

    with db_package.session.SessionLocal() as session:
        events = session.scalars(
            select(DomainEvent).where(DomainEvent.event_type == "reflective_insight_feedback_updated")
        ).all()
        assert len(events) == 2
        assert all(event.actor_id == "local-user" for event in events)


def test_source_shaping_contract_tracks_monoculture_stably_and_losslessly(tmp_path: Path) -> None:
    set_database_url(f"sqlite:///{tmp_path / 'source-contract.db'}")
    init_db()
    now = datetime(2026, 4, 24, 12, tzinfo=timezone.utc)
    with db_package.session.SessionLocal() as session:
        cluster = NodeCluster(user_id="local-user", label="Sources", color="#123456")
        session.add(cluster)
        session.flush()
        _node(session, "local-user", "Earlier note", "A prior note.", cluster.id, ["sources"], now - timedelta(days=10))
        _node(session, "local-user", "Earlier link", "A prior link.", cluster.id, ["sources"], now - timedelta(days=9), kind="link", link_url="https://other.example/prior")
        for offset in (3, 2, 1):
            _node(session, "local-user", f"Repeated source {offset}", "A repeated saved source.", cluster.id, ["sources"], now - timedelta(days=offset), kind="link", link_url=f"https://news.example/item-{offset}?private=query")
        session.commit()

        first = generate_reflective_insight_loop(session, "local-user", reference_time=now)
        source_model = session.get(Insight, first.persisted_insight_ids[5])
        assert source_model is not None
        source_model.feedback_json = {"correction": "inaccurate", "annotation": "Keep this context."}
        source_model.dismissed = True
        session.commit()
        second = generate_reflective_insight_loop(session, "local-user", reference_time=now + timedelta(hours=1))
        source_id = first.persisted_insight_ids[5]
        assert second.persisted_insight_ids[5] == source_id
        source_rows = list_persisted_attention_drift_insights(
            session, "local-user", kind="source_shaping_summary", include_dismissed=True
        )
        assert len(source_rows) == 1
        persisted = source_rows[0]
        assert persisted.kind == "source_shaping_summary"
        assert persisted.feedback.dismissed is True
        assert persisted.feedback.annotation == "Keep this context."
        assert persisted.status == "ready"
        metrics = {metric.key: metric for metric in persisted.metrics}
        assert metrics["dominant_input_kind_share"].current == 1.0
        assert metrics["dominant_input_kind_share"].previous == 0.5
        assert metrics["top_source_domain_share"].current == 1.0
        assert metrics["top_source_domain_count"].current == 3
        assert metrics["top_source_domain_count"].unit == "nodes"
        assert "news.example" in metrics["top_source_domain_share"].label
        assert all("?" not in evidence.label for evidence in persisted.evidence if evidence.evidence_type == "source")
        assert persisted.confidence.score > 0
        assert "not completeness or proof of influence" in persisted.confidence.basis
        assert "does not establish influence" in persisted.limitations[0]
        assert "Among your saved inputs" in persisted.summary


def test_source_shaping_sparse_and_feedback_isolation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("THOUGHTGRAPH_ALLOW_DEV_USER_HEADER_IMPERSONATION", "true")
    get_settings.cache_clear()
    set_database_url(f"sqlite:///{tmp_path / 'source-sparse.db'}")
    app = create_app()
    with TestClient(app) as client:
        run = client.post("/api/reflective-insights/run", json={"run_inline": True})
        assert run.status_code == 200
        source_id = run.json()["persisted_insight_ids"][5]
        listed = client.get("/api/reflective-insights?kind=source_shaping_summary")
        assert listed.status_code == 200
        payload = listed.json()[0]
        assert payload["kind"] == "source_shaping_summary"
        assert payload["status"] == "insufficient_data"
        assert payload["confidence"]["score"] == 0
        assert payload["evidence"] == []

        feedback = client.patch(
            f"/api/reflective-insights/{source_id}/feedback",
            json={"correction": "not_useful", "annotation": "I do not consider file type a source."},
        )
        assert feedback.status_code == 200
        assert feedback.json()["kind"] == "source_shaping_summary"
        assert feedback.json()["feedback"]["correction"] == "not_useful"
        denied = client.patch(
            f"/api/reflective-insights/{source_id}/feedback",
            headers={"X-ThoughtGraph-User": "maya-chen"},
            json={"dismissed": True},
        )
        assert denied.status_code == 404


def _node(
    session: Session,
    user_id: str,
    title: str,
    content: str,
    cluster_id: str,
    topics: list[str],
    created_at: datetime,
    *,
    kind: str = "thought",
    link_url: str | None = None,
) -> ContentNode:
    node = ContentNode(
        user_id=user_id,
        kind=kind,
        title=title,
        content_text=content,
        preview_text=content[:120],
        visibility="private",
        status="ready",
        topics=topics,
        cluster_id=cluster_id,
        link_url=link_url,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(node)
    session.flush()
    return node
