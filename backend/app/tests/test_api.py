from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.db.session import set_database_url
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "test.db"
    set_database_url(f"sqlite:///{database_path}")
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_graph_and_insight_flow(client: TestClient) -> None:
    seed_response = client.post("/api/demo/seed")
    assert seed_response.status_code == 200
    assert seed_response.json()["created"] == 10

    graph_response = client.get("/api/graph")
    assert graph_response.status_code == 200
    graph = graph_response.json()
    assert len(graph["nodes"]) == 10
    assert len(graph["clusters"]) >= 1

    insights_response = client.get("/api/insights")
    assert insights_response.status_code == 200
    insights = insights_response.json()
    assert isinstance(insights, list)

    create_response = client.post(
        "/api/thoughts",
        json={"content": "I am deeply focused on building AI systems that make people feel more honest about themselves."},
    )
    assert create_response.status_code == 200

    graph_after_create = client.get("/api/graph").json()
    assert len(graph_after_create["nodes"]) == 11


def test_insight_update_flow(client: TestClient) -> None:
    client.post("/api/demo/seed")
    insights = client.get("/api/insights")
    assert insights.status_code == 200
    payload = insights.json()
    assert payload

    insight_id = payload[0]["id"]

    seen_response = client.patch(f"/api/insights/{insight_id}", json={"seen": True})
    assert seen_response.status_code == 200
    assert seen_response.json()["seen"] is True

    dismissed_response = client.patch(f"/api/insights/{insight_id}", json={"dismissed": True})
    assert dismissed_response.status_code == 200
    assert dismissed_response.json()["dismissed"] is True

    remaining = client.get("/api/insights")
    assert remaining.status_code == 200
    assert all(item["id"] != insight_id for item in remaining.json())


def test_websocket_receives_graph_update_event(client: TestClient) -> None:
    with client.websocket_connect("/api/ws") as websocket:
        response = client.post(
            "/api/thoughts",
            json={"content": "Websocket validation thought about systems, delivery, and graph updates."},
        )
        assert response.status_code == 200

        event = websocket.receive_json()
        assert event["type"] == "graph_updated"
        assert event["nodeCount"] == 1
        assert "edgeCount" in event


def test_create_app_initializes_database_without_manual_init(tmp_path: Path) -> None:
    database_path = tmp_path / "startup.db"
    set_database_url(f"sqlite:///{database_path}")
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/graph")

    assert response.status_code == 200
    assert response.json()["nodes"] == []


def test_v2_follow_flow_and_notification_event(client: TestClient) -> None:
    seed_social = client.post("/api/social/demo/seed")
    assert seed_social.status_code == 200

    users = client.get("/api/users/search?q=")
    assert users.status_code == 200
    candidates = users.json()
    assert candidates
    target_id = candidates[0]["id"]

    with client.websocket_connect(f"/api/ws?user_id={target_id}") as websocket:
        follow = client.post(f"/api/social/follow/{target_id}")
        assert follow.status_code == 200
        assert follow.json()["following"] is True

        event = websocket.receive_json()
        assert event["type"] == "new_follower"
        assert event["user_id"] == "local-user"

    me = client.get("/api/users/me")
    assert me.status_code == 200
    assert me.json()["following_count"] == 1

    relationship = client.get(f"/api/social/relationship/{target_id}")
    assert relationship.status_code == 200
    assert relationship.json() == {"following": True, "followed_by": False}

    followers = client.get(f"/api/social/followers/{target_id}")
    assert followers.status_code == 200
    assert any(item["user_id"] == "local-user" for item in followers.json())

    notifications = client.get("/api/notifications", headers={"X-ThoughtGraph-User": target_id})
    assert notifications.status_code == 200
    assert notifications.json()
    assert notifications.json()[0]["type"] == "new_follower"

    unfollow = client.delete(f"/api/social/follow/{target_id}")
    assert unfollow.status_code == 200
    assert unfollow.json()["following"] is False


def test_v2_social_graph_overlay_and_profile_privacy(client: TestClient) -> None:
    client.post("/api/demo/seed")
    client.post("/api/social/demo/seed")
    client.post("/api/thoughts", json={"content": "AI products should reveal uncertainty instead of pretending to be certain."})
    client.post("/api/social/follow/maya-chen")

    graph = client.get("/api/graph?social=true")
    assert graph.status_code == 200
    payload = graph.json()
    assert payload["social_enabled"] is True
    assert payload["social_profiles"]
    assert any(node["is_social"] for node in payload["social_nodes"])
    assert all(edge["kind"] == "cross_semantic_link" for edge in payload["social_edges"])

    update_me = client.patch("/api/users/me", json={"is_public": False, "bio": "private bio"})
    assert update_me.status_code == 200
    assert update_me.json()["is_public"] is False

    profile = client.get("/api/users/local-user", headers={"X-ThoughtGraph-User": "maya-chen"})
    assert profile.status_code == 200
    assert profile.json()["bio"] == ""
    assert profile.json()["top_clusters"] == []


def test_v2_reply_thread_influence_and_feed(client: TestClient) -> None:
    client.post("/api/demo/seed")
    client.post("/api/social/demo/seed")
    client.post("/api/social/follow/maya-chen")

    graph = client.get("/api/graph?social=true")
    assert graph.status_code == 200
    social_nodes = graph.json()["social_nodes"]
    assert social_nodes
    target_thought_id = social_nodes[0]["id"]

    with client.websocket_connect("/api/ws?user_id=maya-chen") as websocket:
        reply = client.post(
            "/api/thoughts",
            json={
                "content": "That point about uncertainty is exactly why trust rises when systems show their seams.",
                "reply_to_id": target_thought_id,
                "visibility": "public",
            },
        )
        assert reply.status_code == 200
        event = websocket.receive_json()
        assert event["type"] == "new_reply"
        assert event["thought_id"] == target_thought_id

    thread = client.get(f"/api/social/replies/{target_thought_id}")
    assert thread.status_code == 200
    payload = thread.json()
    assert payload["root"]["id"] == target_thought_id
    assert any(item["reply_to_id"] == target_thought_id for item in payload["replies"])

    influence = client.get("/api/social/influence/maya-chen")
    assert influence.status_code == 200
    assert influence.json()["target_user_id"] == "maya-chen"
    assert influence.json()["score"] >= 0

    feed = client.get("/api/social/feed")
    assert feed.status_code == 200
    assert feed.json()

    notifications = client.get("/api/notifications", headers={"X-ThoughtGraph-User": "maya-chen"})
    assert notifications.status_code == 200
    assert any(item["type"] == "reply" for item in notifications.json())


def test_v2_snapshots_reports_discovery_and_settings(client: TestClient) -> None:
    client.post("/api/demo/seed")
    client.post("/api/social/demo/seed")

    snapshot = client.post("/api/snapshots", json={"caption": "My graph this week", "is_public": True})
    assert snapshot.status_code == 200
    snapshot_payload = snapshot.json()
    assert snapshot_payload["image_url"].startswith("data:image/svg+xml;base64,")

    snapshot_list = client.get("/api/snapshots")
    assert snapshot_list.status_code == 200
    assert len(snapshot_list.json()) == 1

    public_snapshot = client.get(f"/api/snapshots/public/{snapshot_payload['id']}")
    assert public_snapshot.status_code == 200
    assert public_snapshot.json()["id"] == snapshot_payload["id"]

    report = client.post("/api/reports/generate")
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["image_url"].startswith("data:image/svg+xml;base64,")

    latest_report = client.get("/api/reports/latest")
    assert latest_report.status_code == 200
    assert latest_report.json()["id"] == report_payload["id"]

    reports = client.get("/api/reports")
    assert reports.status_code == 200
    assert reports.json()

    trending = client.get("/api/social/trending-clusters")
    assert trending.status_code == 200
    assert trending.json()

    suggested = client.get("/api/social/suggested-users")
    assert suggested.status_code == 200
    assert suggested.json()

    notification_prefs = client.patch(
        "/api/users/me/notification-preferences",
        json={"push_new_follower": False},
        headers={"X-ThoughtGraph-User": "maya-chen"},
    )
    assert notification_prefs.status_code == 200
    assert notification_prefs.json()["notification_prefs"]["push_new_follower"] is False

    follow = client.post("/api/social/follow/maya-chen")
    assert follow.status_code == 200

    notifications = client.get("/api/notifications", headers={"X-ThoughtGraph-User": "maya-chen"})
    assert notifications.status_code == 200
    assert all(item["type"] != "new_follower" for item in notifications.json())

    onboarding = client.patch("/api/users/me/onboarding", json={"completed": True})
    assert onboarding.status_code == 200
    assert onboarding.json()["completed"] is True

    bulk_visibility = client.patch("/api/users/me/thought-visibility", json={"visibility": "private"})
    assert bulk_visibility.status_code == 200
    assert bulk_visibility.json()["visibility"] == "private"

    exported = client.get("/api/users/me/export")
    assert exported.status_code == 200
    assert exported.json()["profile"]["onboarding_v2_completed"] is True


def test_v2_delete_account(client: TestClient) -> None:
    client.post("/api/demo/seed")
    exported = client.get("/api/users/me/export")
    assert exported.status_code == 200
    assert exported.json()["thoughts"]

    deleted = client.delete("/api/users/me")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    graph = client.get("/api/graph")
    assert graph.status_code == 200
    assert graph.json()["nodes"] == []
