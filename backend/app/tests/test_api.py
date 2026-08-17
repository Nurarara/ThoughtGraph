from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db import session as db_session
from app.db.session import set_database_url
from app.main import create_app
from app.models.content_node import ContentNode


@pytest.fixture(autouse=True)
def reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Multi-user API tests explicitly exercise the development impersonation
    # harness. Runtime defaults keep this disabled.
    monkeypatch.setenv("THOUGHTGRAPH_ALLOW_DEV_USER_HEADER_IMPERSONATION", "true")
    get_settings.cache_clear()
    database_path = tmp_path / "test.db"
    set_database_url(f"sqlite:///{database_path}")
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def make_client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "test.db"
    set_database_url(f"sqlite:///{database_path}")
    app = create_app()
    return TestClient(app)


def test_health_and_default_profile_bootstrap(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    me = client.get("/api/users/me")
    assert me.status_code == 200
    payload = me.json()
    assert payload["id"] == "local-user"
    assert payload["node_count"] == 0
    assert payload["cluster_count"] == 0


def test_default_dev_cors_allows_thoughtgraph_frontend(client: TestClient) -> None:
    response = client.options(
        "/api/auth/request-link",
        headers={
            "Origin": "http://127.0.0.1:5174",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"


def test_magic_link_auth_flow(client: TestClient) -> None:
    request_link = client.post("/api/auth/request-link", json={"email": "builder@example.com"})
    assert request_link.status_code == 200
    link = request_link.json()["magic_link"]
    token = link.split("token=", 1)[1]

    redirect = client.get(link, follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == f"http://127.0.0.1:5174/?token={token}"

    verified = client.post("/api/auth/verify", json={"token": token})
    assert verified.status_code == 200
    payload = verified.json()
    assert payload["email"] == "builder@example.com"
    assert payload["session_token"]

    me = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {payload['session_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["display_name"] == "Builder"


def test_magic_link_email_is_normalized_and_reuses_existing_user(client: TestClient) -> None:
    request_link = client.post("/api/auth/request-link", json={"email": "  Builder@Example.COM  "})
    assert request_link.status_code == 200
    assert request_link.json()["email"] == "builder@example.com"
    token = request_link.json()["magic_link"].split("token=", 1)[1]

    first_verified = client.post("/api/auth/verify", json={"token": token})
    assert first_verified.status_code == 200
    assert first_verified.json()["email"] == "builder@example.com"
    assert first_verified.json()["is_new_user"] is True

    second_link = client.post("/api/auth/request-link", json={"email": "builder@example.com"})
    assert second_link.status_code == 200
    second_token = second_link.json()["magic_link"].split("token=", 1)[1]
    second_verified = client.post("/api/auth/verify", json={"token": second_token})
    assert second_verified.status_code == 200
    assert second_verified.json()["user_id"] == first_verified.json()["user_id"]
    assert second_verified.json()["is_new_user"] is False


def test_production_request_link_requires_email_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THOUGHTGRAPH_AUTH_MODE", "production")
    with make_client(tmp_path) as prod_client:
        response = prod_client.post("/api/auth/request-link", json={"email": "builder@example.com"})
    assert response.status_code == 503
    assert response.json()["detail"] == "email delivery is not configured"


def test_production_request_link_hides_magic_link_when_email_is_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("THOUGHTGRAPH_AUTH_MODE", "production")
    monkeypatch.setenv("THOUGHTGRAPH_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("THOUGHTGRAPH_SMTP_FROM_EMAIL", "noreply@example.com")

    send_mock = Mock()
    monkeypatch.setattr("app.api.routes.auth.send_magic_link_email", send_mock)

    with make_client(tmp_path) as prod_client:
        response = prod_client.post("/api/auth/request-link", json={"email": "builder@example.com"})
    assert response.status_code == 200
    assert response.json()["magic_link"] is None
    send_mock.assert_called_once()


def test_production_routes_require_authentication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THOUGHTGRAPH_AUTH_MODE", "production")
    with make_client(tmp_path) as prod_client:
        response = prod_client.get("/api/users/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "authentication required"


def test_development_rejects_arbitrary_user_header_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("THOUGHTGRAPH_ALLOW_DEV_USER_HEADER_IMPERSONATION", raising=False)
    get_settings.cache_clear()
    with make_client(tmp_path) as dev_client:
        default_user = dev_client.get(
            "/api/users/me",
            headers={"X-ThoughtGraph-User": "local-user"},
        )
        impersonated = dev_client.get(
            "/api/users/me",
            headers={"X-ThoughtGraph-User": "maya-chen"},
        )

    assert default_user.status_code == 200
    assert default_user.json()["id"] == "local-user"
    assert impersonated.status_code == 403
    assert impersonated.json()["detail"] == "development user impersonation is disabled"


def test_development_user_header_impersonation_requires_explicit_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("THOUGHTGRAPH_ALLOW_DEV_USER_HEADER_IMPERSONATION", "true")
    get_settings.cache_clear()
    with make_client(tmp_path) as dev_client:
        response = dev_client.get(
            "/api/users/me",
            headers={"X-ThoughtGraph-User": "maya-chen"},
        )

    assert response.status_code == 200
    assert response.json()["id"] == "maya-chen"


def test_production_rejects_dev_impersonation_even_when_opted_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("THOUGHTGRAPH_AUTH_MODE", "production")
    monkeypatch.setenv("THOUGHTGRAPH_ALLOW_DEV_USER_HEADER_IMPERSONATION", "true")
    get_settings.cache_clear()
    with make_client(tmp_path) as prod_client:
        response = prod_client.get(
            "/api/users/me",
            headers={"X-ThoughtGraph-User": "maya-chen"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "authentication required"


def test_production_rejects_dev_impersonation_for_infra_and_moderation_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("THOUGHTGRAPH_AUTH_MODE", "production")
    with make_client(tmp_path) as prod_client:
        headers = {"X-ThoughtGraph-User": "local-user"}
        assert prod_client.get("/api/infra/search?q=graph", headers=headers).status_code == 401
        assert prod_client.get("/api/infra/ops/status", headers=headers).status_code == 401
        assert prod_client.get("/api/moderation/events", headers=headers).status_code == 401
        assert prod_client.get("/api/moderation/enforcement/node/missing", headers=headers).status_code == 401


def test_admin_routes_reject_development_impersonated_non_admin(client: TestClient) -> None:
    headers = {"X-ThoughtGraph-User": "maya-chen"}
    dispatch = client.post("/api/infra/events/dispatch?limit=1", headers=headers)
    assert dispatch.status_code == 403
    assert dispatch.json()["detail"] == "admin privileges required"

    moderation_events = client.get("/api/moderation/events", headers=headers)
    assert moderation_events.status_code == 403
    assert moderation_events.json()["detail"] == "admin privileges required"


def test_magic_link_get_route_redirects_to_frontend_callback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("THOUGHTGRAPH_APP_URL", "http://localhost:5173")
    with make_client(tmp_path) as test_client:
        response = test_client.get("/api/auth/verify?token=test-token", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:5173/?token=test-token"


def test_create_nodes_updates_graph_clusters_jobs_and_events(client: TestClient) -> None:
    first = client.post(
        "/api/nodes",
        json={
            "kind": "thought",
            "title": "Ambient systems",
            "content_text": "I want graph interfaces that make software architecture spatial and transparent.",
            "visibility": "private",
        },
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["cluster_id"] is not None
    assert first_payload["topics"]

    second = client.post(
        "/api/nodes",
        json={
            "kind": "thought",
            "title": "Spatial reasoning",
            "content_text": "Transparent graph systems help users reason across architecture, nodes, and context.",
            "visibility": "public",
        },
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["cluster_id"] is not None

    graph = client.get("/api/graph")
    assert graph.status_code == 200
    graph_payload = graph.json()
    assert len(graph_payload["nodes"]) == 2
    assert len(graph_payload["edges"]) >= 1
    assert len(graph_payload["clusters"]) >= 1
    assert graph_payload["viewport"]["zoom_hint"] <= 1.0
    assert graph_payload["explanation"]["reason"]

    listed = client.get("/api/nodes")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2

    detail = client.get(f"/api/nodes/{first_payload['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == first_payload["id"]


def test_graph_search_returns_focusable_matches(client: TestClient) -> None:
    client.post(
        "/api/nodes",
        json={
            "kind": "thought",
            "title": "Trust layer",
            "content_text": "Claims need provenance, evidence, and contradiction trails.",
            "visibility": "private",
        },
    )
    client.post(
        "/api/nodes",
        json={
            "kind": "thought",
            "title": "Canvas behavior",
            "content_text": "Pan and zoom should feel deterministic and calm.",
            "visibility": "private",
        },
    )

    search = client.get("/api/graph/search?q=provenance")
    assert search.status_code == 200
    items = search.json()["items"]
    assert items
    assert items[0]["preview_text"]


def test_profile_update_and_onboarding_state(client: TestClient) -> None:
    response = client.patch(
        "/api/users/me",
        json={
            "display_name": "Rounak",
            "bio": "Building ThoughtGraph as a graph-native social system.",
            "onboarding_v2_completed": True,
            "is_public": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["display_name"] == "Rounak"
    assert payload["bio"].startswith("Building ThoughtGraph")
    assert payload["onboarding_v2_completed"] is True
    assert payload["is_public"] is False


def test_image_and_link_nodes_are_supported(client: TestClient) -> None:
    image = client.post(
        "/api/nodes",
        json={
            "kind": "image",
            "title": "Graph concept art",
            "content_text": "A neural atlas style landing visual.",
            "visibility": "public",
            "media": {
                "url": "https://example.com/concept.png",
                "mime_type": "image/png",
                "width": 1280,
                "height": 720,
            },
        },
    )
    assert image.status_code == 200
    assert image.json()["media_url"] == "https://example.com/concept.png"

    link = client.post(
        "/api/nodes",
        json={
            "kind": "link",
            "title": "OpenSearch docs",
            "content_text": "Hybrid retrieval reference",
            "visibility": "private",
            "link_url": "https://opensearch.org/docs/latest/",
        },
    )
    assert link.status_code == 200
    assert link.json()["link_url"] == "https://opensearch.org/docs/latest/"


def test_follow_friendship_and_profile_search_flow(client: TestClient) -> None:
    client.get("/api/users/me", headers={"X-ThoughtGraph-User": "maya-chen"})
    client.patch(
        "/api/users/me",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={"display_name": "Maya Chen", "bio": "Builds graph-native systems.", "is_public": True},
    )

    follow = client.post("/api/social/follow/maya-chen")
    assert follow.status_code == 200
    assert follow.json()["following"] is True

    request_friend = client.post("/api/friends/request", json={"user_id": "maya-chen"})
    assert request_friend.status_code == 200
    assert request_friend.json()["friendship_state"] == "outgoing"

    accept = client.post("/api/friends/local-user/accept", headers={"X-ThoughtGraph-User": "maya-chen"})
    assert accept.status_code == 200
    assert accept.json()["friendship_state"] == "accepted"

    relationship = client.get("/api/social/relationship/maya-chen")
    assert relationship.status_code == 200
    payload = relationship.json()
    assert payload["following"] is True
    assert payload["friendship_state"] == "accepted"

    search = client.get("/api/users/search?q=maya")
    assert search.status_code == 200
    assert search.json()
    assert search.json()[0]["relationship"]["friendship_state"] == "accepted"

    profile = client.get("/api/users/maya-chen")
    assert profile.status_code == 200
    assert profile.json()["relationship"]["friendship_state"] == "accepted"


def test_friends_visibility_and_social_graph_projection(client: TestClient) -> None:
    client.get("/api/users/me", headers={"X-ThoughtGraph-User": "maya-chen"})
    client.patch(
        "/api/users/me",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={"display_name": "Maya Chen", "bio": "Social graph builder.", "is_public": True},
    )
    client.post("/api/friends/request", json={"user_id": "maya-chen"})
    client.post("/api/friends/local-user/accept", headers={"X-ThoughtGraph-User": "maya-chen"})
    client.post("/api/social/follow/maya-chen")

    friends_node = client.post(
        "/api/nodes",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={
            "kind": "thought",
            "title": "Friends-only update",
            "content_text": "This branch is only for trusted graph neighbors.",
            "visibility": "friends",
        },
    )
    assert friends_node.status_code == 200

    public_node = client.post(
        "/api/nodes",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={
            "kind": "thought",
            "title": "Public update",
            "content_text": "This node should appear in public social mode.",
            "visibility": "public",
        },
    )
    assert public_node.status_code == 200

    social_graph = client.get("/api/graph?social=true")
    assert social_graph.status_code == 200
    payload = social_graph.json()
    assert payload["social_mode"] is True
    social_nodes = [node for node in payload["nodes"] if node["is_social"]]
    assert social_nodes
    assert any(node["author_id"] == "maya-chen" for node in social_nodes)
    assert any(node["visibility"] == "friends" for node in social_nodes)

    stranger_fetch = client.get(
        f"/api/nodes/{friends_node.json()['id']}",
        headers={"X-ThoughtGraph-User": "leo-martin"},
    )
    assert stranger_fetch.status_code == 404

    neighborhood = client.get("/api/social/neighborhood")
    assert neighborhood.status_code == 200
    assert neighborhood.json()["items"]


def test_reply_quote_threads_and_restrictions(client: TestClient) -> None:
    client.get("/api/users/me", headers={"X-ThoughtGraph-User": "maya-chen"})
    client.patch(
        "/api/users/me",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={"display_name": "Maya Chen", "bio": "Trust and provenance.", "is_public": True},
    )
    client.post("/api/friends/request", json={"user_id": "maya-chen"})
    client.post("/api/friends/local-user/accept", headers={"X-ThoughtGraph-User": "maya-chen"})
    client.post("/api/social/follow/maya-chen")

    root = client.post(
        "/api/nodes",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={
            "kind": "thought",
            "title": "Origin node",
            "content_text": "Users should be able to inspect where a claim came from.",
            "visibility": "public",
        },
    )
    assert root.status_code == 200
    root_id = root.json()["id"]

    reply = client.post(
        "/api/nodes",
        json={
            "kind": "thought",
            "title": "Reply node",
            "content_text": "Replies should branch instead of collapsing into a flat thread.",
            "visibility": "friends",
            "reply_to_node_id": root_id,
            "quote_of_node_id": root_id,
        },
    )
    assert reply.status_code == 200

    thread = client.get(f"/api/nodes/{root_id}/thread")
    assert thread.status_code == 200
    thread_payload = thread.json()
    assert thread_payload["root"]["id"] == root_id
    assert any(item["reply_to_node_id"] == root_id for item in thread_payload["replies"])

    friends_only = client.post(
        "/api/nodes",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={
            "kind": "thought",
            "title": "Restricted branch",
            "content_text": "This should disappear once the owner restricts the viewer.",
            "visibility": "friends",
        },
    )
    assert friends_only.status_code == 200
    friends_only_id = friends_only.json()["id"]

    restricted = client.post(
        "/api/social/restrictions/local-user",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={"kind": "restricted", "active": True},
    )
    assert restricted.status_code == 200
    assert restricted.json()["restricted"] is True

    restricted_fetch = client.get(f"/api/nodes/{friends_only_id}")
    assert restricted_fetch.status_code == 404

    blocked = client.post("/api/social/restrictions/maya-chen", json={"kind": "blocked", "active": True})
    assert blocked.status_code == 200
    blocked_relationship = client.get("/api/social/relationship/maya-chen")
    assert blocked_relationship.status_code == 200
    assert blocked_relationship.json()["blocked"] is True


def test_discovery_explore_related_and_adjacent_people_are_explainable(client: TestClient) -> None:
    root = client.post(
        "/api/nodes",
        json={
            "kind": "thought",
            "title": "Graph-native discovery",
            "content_text": "Discovery should show why a node appears instead of hiding ranking logic.",
            "visibility": "private",
        },
    )
    assert root.status_code == 200
    root_id = root.json()["id"]

    sibling = client.post(
        "/api/nodes",
        json={
            "kind": "link",
            "title": "Explainable ranking",
            "content_text": "Ranking should combine relevance, novelty, social proximity, and evidence proxies.",
            "visibility": "public",
            "link_url": "https://example.com/explainable-ranking",
        },
    )
    assert sibling.status_code == 200
    trusted_claim = client.post(
        "/api/trust/claims",
        json={
            "node_id": sibling.json()["id"],
            "claim_text": "Explainable ranking has an inspectable trust claim.",
            "verification_status": "supported",
            "confidence_score": 0.8,
            "rationale_text": "Local test evidence marks this discovery item as trusted.",
        },
    )
    assert trusted_claim.status_code == 200

    client.get("/api/users/me", headers={"X-ThoughtGraph-User": "maya-chen"})
    client.patch(
        "/api/users/me",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={"display_name": "Maya Chen", "bio": "Maps discovery systems.", "is_public": True},
    )
    maya_node = client.post(
        "/api/nodes",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={
            "kind": "thought",
            "title": "Outside the bubble",
            "content_text": "Public topic bridges should let people move beyond their local graph.",
            "visibility": "public",
        },
    )
    assert maya_node.status_code == 200
    explore = client.get("/api/discovery/explore?high_evidence=true&trusted_only=true")
    assert explore.status_code == 200
    explore_payload = explore.json()
    assert explore_payload["materialization_id"]
    assert explore_payload["explanation_summary"]
    assert explore_payload["filter_availability"]["trusted_only"] is True
    assert explore_payload["items"]
    first_item = explore_payload["items"][0]
    assert first_item["explanation"]["summary"]
    assert first_item["explanation"]["score_breakdown"]["total"] >= 0
    assert first_item["explanation"]["unavailable_filters"] == []

    related = client.get(f"/api/discovery/related/{root_id}")
    assert related.status_code == 200
    related_payload = related.json()
    assert related_payload["subject"]["id"] == root_id
    assert related_payload["items"]
    assert related_payload["items"][0]["explanation"]["primary_reason"] == "semantic_overlap"

    client.post("/api/social/follow/maya-chen")
    adjacent = client.get("/api/discovery/people-adjacent")
    assert adjacent.status_code == 200
    adjacent_payload = adjacent.json()
    assert adjacent_payload["materialization_id"]
    assert adjacent_payload["items"]
    assert any(item["user_id"] == "maya-chen" for item in adjacent_payload["items"])
    assert adjacent_payload["items"][0]["explanation"]["score_breakdown"]["total"] >= 0


def test_discovery_normalizes_mixed_legacy_embeddings(client: TestClient) -> None:
    created_ids = []
    for title in ("Valid vector", "Empty vector", "Malformed vector"):
        response = client.post(
            "/api/nodes",
            json={
                "kind": "thought",
                "title": title,
                "content_text": f"{title} should remain discoverable after a legacy migration.",
                "visibility": "public",
            },
        )
        assert response.status_code == 200
        created_ids.append(response.json()["id"])

    with db_session.SessionLocal() as session:
        nodes = list(session.scalars(select(ContentNode).where(ContentNode.id.in_(created_ids))))
        by_title = {node.title: node for node in nodes}
        by_title["Empty vector"].embedding = []
        by_title["Malformed vector"].embedding = ["bad", None, {"not": "numeric"}]
        malformed_id = by_title["Malformed vector"].id
        session.commit()

    explore = client.get("/api/discovery/explore?q=legacy")
    assert explore.status_code == 200
    assert explore.json()["items"]

    related = client.get(f"/api/discovery/related/{malformed_id}")
    assert related.status_code == 200
    assert related.json()["subject"]["id"] == malformed_id


def test_phase_6_to_12_routes_are_mounted_and_explainable(client: TestClient) -> None:
    node = client.post(
        "/api/nodes",
        json={
            "kind": "link",
            "title": "Launch trust route",
            "content_text": "Prototype launch needs provenance, moderation, search, and operations checks.",
            "visibility": "public",
            "link_url": "https://example.com/launch-trust",
        },
    )
    assert node.status_code == 200
    node_id = node.json()["id"]

    claim = client.post(
        "/api/trust/claims",
        json={
            "node_id": node_id,
            "claim_text": "ThoughtGraph routes expose provenance and evidence.",
            "verification_status": "needs_review",
            "confidence_score": 0.25,
            "rationale_text": "Initial route-level provenance test.",
        },
    )
    assert claim.status_code == 200
    claim_id = claim.json()["id"]

    source = client.post(
        "/api/trust/sources",
        json={
            "url": "https://example.com/source",
            "title": "Launch Source",
            "credibility_score": 0.7,
        },
    )
    assert source.status_code == 200

    evidence = client.post(
        f"/api/trust/claims/{claim_id}/evidence",
        json={
            "source_id": source.json()["id"],
            "stance": "supporting",
            "summary": "The source supports the route-level provenance path.",
            "weight": 0.6,
        },
    )
    assert evidence.status_code == 200

    provenance = client.get(f"/api/trust/nodes/{node_id}/provenance")
    assert provenance.status_code == 200
    assert provenance.json()["claims"]
    assert provenance.json()["snapshot"]["id"]

    report = client.post(
        "/api/moderation/reports",
        json={"subject_type": "node", "subject_id": node_id, "reason": "misleading", "details": "CEO smoke test."},
    )
    assert report.status_code == 200

    enforcement = client.put(
        "/api/moderation/enforcement",
        json={
            "subject_type": "node",
            "subject_id": node_id,
            "state": "limited",
            "blocked_from_discovery": True,
            "reason": "Hold from discovery during review.",
            "report_id": report.json()["id"],
        },
    )
    assert enforcement.status_code == 200
    assert enforcement.json()["blocked_from_discovery"] is True

    discovery = client.get("/api/discovery/explore?q=launch")
    assert discovery.status_code == 200
    assert all(item["node"]["id"] != node_id for item in discovery.json()["items"])

    reflective = client.post("/api/reflective-insights/run", json={"run_inline": True})
    assert reflective.status_code == 200
    assert reflective.json()["event_id"]
    assert reflective.json()["insights"]

    search_rebuild = client.post("/api/infra/search/rebuild")
    assert search_rebuild.status_code == 200
    assert search_rebuild.json()["indexed"] >= 1

    search = client.get("/api/infra/search?q=provenance")
    assert search.status_code == 200
    assert search.json()["explanation_summary"]

    graph_rebuild = client.post("/api/infra/graph/rebuild")
    assert graph_rebuild.status_code == 200
    assert graph_rebuild.json()["explanation"].startswith("graph read model rebuilt")

    graph_projection = client.get("/api/infra/graph")
    assert graph_projection.status_code == 200
    assert graph_projection.json()["explanation"].startswith("query served from graph_read_model")

    ops = client.get("/api/infra/ops/status")
    assert ops.status_code == 200
    assert {partition["name"] for partition in ops.json()["partitions"]} >= {"events", "search_index", "graph_read_model"}

    dispatch = client.post("/api/infra/events/dispatch?limit=5")
    assert dispatch.status_code == 200
    assert dispatch.json()["outcomes"]


def test_media_upload_pipeline_supports_images_and_video_nodes(client: TestClient) -> None:
    image_bytes = _image_bytes("PNG", (640, 360), "#77a8ff")
    image_upload = client.post(
        "/api/media/uploads",
        json={
            "kind": "image",
            "filename": "cluster.png",
            "mime_type": "image/png",
            "size_bytes": len(image_bytes),
        },
    )
    assert image_upload.status_code == 200
    image_asset = image_upload.json()["asset"]
    image_put = client.put(
        image_upload.json()["upload"]["upload_url"],
        content=image_bytes,
        headers={"Content-Type": "image/png", "X-Upload-Filename": "cluster.png"},
    )
    assert image_put.status_code == 200
    image_payload = image_put.json()
    assert image_payload["status"] == "ready"
    assert image_payload["moderation_status"] == "unreviewed"
    assert image_payload["thumbnail_url"]
    assert image_payload["playback_url"]

    thumbnail = client.get(image_payload["thumbnail_url"])
    assert thumbnail.status_code == 200

    image_node = client.post(
        "/api/nodes",
        json={
            "kind": "image",
            "title": "Cluster artwork",
            "content_text": "Image nodes should survive a real upload flow.",
            "visibility": "public",
            "media": {"asset_id": image_asset["id"]},
        },
    )
    assert image_node.status_code == 200
    assert image_node.json()["media_asset_id"] == image_asset["id"]
    assert image_node.json()["thumbnail_url"]

    video_bytes = b"\x00\x00\x00\x18ftypmp42thoughtgraph-video"
    video_upload = client.post(
        "/api/media/uploads",
        json={
            "kind": "video",
            "filename": "signal.mp4",
            "mime_type": "video/mp4",
            "size_bytes": len(video_bytes),
        },
    )
    assert video_upload.status_code == 200
    video_put = client.put(
        video_upload.json()["upload"]["upload_url"],
        content=video_bytes,
        headers={"Content-Type": "video/mp4", "X-Upload-Filename": "signal.mp4"},
    )
    assert video_put.status_code == 200
    video_payload = video_put.json()
    assert video_payload["status"] == "ready"
    assert video_payload["moderation_status"] == "unreviewed"
    assert video_payload["playback_url"]
    assert video_payload["thumbnail_url"]
    assert video_payload["metadata_json"]["processing_mode"] == "passthrough"

    playback = client.get(video_payload["playback_url"])
    assert playback.status_code == 200
    poster = client.get(video_payload["thumbnail_url"])
    assert poster.status_code == 200
    assert poster.headers["content-type"].startswith("image/svg+xml")

    video_node = client.post(
        "/api/nodes",
        json={
            "kind": "video",
            "title": "Playback branch",
            "content_text": "Video nodes should attach to uploaded assets.",
            "visibility": "friends",
            "media": {"asset_id": video_upload.json()["asset"]["id"]},
        },
    )
    assert video_node.status_code == 200
    assert video_node.json()["playback_url"]
    graph = client.get("/api/graph")
    assert graph.status_code == 200
    assert any(node["kind"] == "video" for node in graph.json()["nodes"])


def test_unreviewed_media_remains_usable_but_is_excluded_from_discovery(client: TestClient) -> None:
    client.get("/api/users/me", headers={"X-ThoughtGraph-User": "maya-chen"})
    client.patch(
        "/api/users/me",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={"display_name": "Maya Chen", "is_public": True},
    )
    image_bytes = _image_bytes("PNG", (64, 64), "#385c8a")
    upload = client.post(
        "/api/media/uploads",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={
            "kind": "image",
            "filename": "unreviewed.png",
            "mime_type": "image/png",
            "size_bytes": len(image_bytes),
        },
    )
    uploaded = client.put(
        upload.json()["upload"]["upload_url"],
        headers={
            "X-ThoughtGraph-User": "maya-chen",
            "Content-Type": "image/png",
        },
        content=image_bytes,
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["moderation_status"] == "unreviewed"

    node = client.post(
        "/api/nodes",
        headers={"X-ThoughtGraph-User": "maya-chen"},
        json={
            "kind": "image",
            "title": "Unreviewed public media",
            "content_text": "This remains available to its owner without entering discovery.",
            "visibility": "public",
            "media": {"asset_id": uploaded.json()["id"]},
        },
    )
    assert node.status_code == 200
    node_id = node.json()["id"]

    owner_read = client.get(
        f"/api/nodes/{node_id}",
        headers={"X-ThoughtGraph-User": "maya-chen"},
    )
    assert owner_read.status_code == 200
    discovery = client.get("/api/discovery/explore?q=unreviewed")
    assert discovery.status_code == 200
    assert all(item["node"]["id"] != node_id for item in discovery.json()["items"])


def test_failed_media_processing_is_safe_and_retryable(client: TestClient) -> None:
    broken_upload = client.post(
        "/api/media/uploads",
        json={
            "kind": "image",
            "filename": "broken.png",
            "mime_type": "image/png",
            "size_bytes": 13,
        },
    )
    assert broken_upload.status_code == 200

    broken_put = client.put(
        broken_upload.json()["upload"]["upload_url"],
        content=b"not-an-image",
        headers={"Content-Type": "image/png", "X-Upload-Filename": "broken.png"},
    )
    assert broken_put.status_code == 200
    assert broken_put.json()["status"] == "failed"
    assert broken_put.json()["error_message"]

    retry = client.post(f"/api/media/assets/{broken_upload.json()['asset']['id']}/retry")
    assert retry.status_code == 200
    assert retry.json()["status"] == "failed"
    assert retry.json()["error_message"]


def test_media_upload_rejects_actual_content_larger_than_configured_limit(client: TestClient) -> None:
    get_settings().max_image_upload_bytes = 8
    upload = client.post(
        "/api/media/uploads",
        json={
            "kind": "image",
            "filename": "oversized.png",
            "mime_type": "image/png",
            "size_bytes": 8,
        },
    )
    assert upload.status_code == 200

    response = client.put(
        upload.json()["upload"]["upload_url"],
        content=b"123456789",
        headers={"Content-Type": "image/png"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "image uploads are limited to 8 bytes"
    asset = client.get(f"/api/media/assets/{upload.json()['asset']['id']}")
    assert asset.status_code == 200
    assert asset.json()["status"] == "awaiting_upload"
    assert asset.json()["size_bytes"] == 8


def test_media_upload_stops_chunked_body_when_actual_limit_is_crossed(client: TestClient) -> None:
    get_settings().max_image_upload_bytes = 8
    upload = client.post(
        "/api/media/uploads",
        json={
            "kind": "image",
            "filename": "chunked.png",
            "mime_type": "image/png",
            "size_bytes": 8,
        },
    )
    assert upload.status_code == 200

    response = client.put(
        upload.json()["upload"]["upload_url"],
        content=(chunk for chunk in (b"1234", b"5678", b"9")),
        headers={"Content-Type": "image/png"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "image uploads are limited to 8 bytes"


def _image_bytes(fmt: str, size: tuple[int, int], color: str) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()
