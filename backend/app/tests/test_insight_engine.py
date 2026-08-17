from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import db as db_package
from app.db.session import set_database_url
from app.main import create_app
from app.models.domain_event import DomainEvent
from app.models.workflow_job import WorkflowJob


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "events.db"
    set_database_url(f"sqlite:///{database_path}")
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_node_creation_emits_events_and_completes_graph_job(client: TestClient) -> None:
    response = client.post(
        "/api/nodes",
        json={
            "kind": "thought",
            "title": "Event-first architecture",
            "content_text": "Every expensive action should cross a durable workflow boundary.",
            "visibility": "private",
        },
    )
    assert response.status_code == 200

    with db_package.session.SessionLocal() as session:
        event_types = {
            event.event_type
            for event in session.query(DomainEvent).all()
        }
        assert "node_created" in event_types
        assert "node_embedded" in event_types
        assert "graph_job_enqueued" in event_types
        assert "graph_projection_refreshed" in event_types

        jobs = session.query(WorkflowJob).all()
        assert jobs
        assert jobs[0].status == "completed"
