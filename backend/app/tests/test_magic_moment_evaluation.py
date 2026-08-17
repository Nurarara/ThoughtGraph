from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, func, select

from app import db as db_package
from app.db.session import init_db, set_database_url
from app.models.insight import Insight
from app.models.node_edge import NodeEdge
from app.services.reflective_insight_service import generate_reflective_insight_loop
from app.tests.fixtures.magic_moment_histories import (
    REFERENCE_TIME,
    MagicMomentHistory,
    builder_pivot,
    connected_synthesis,
    source_monoculture,
)


EXPECTED_KINDS = {
    "weekly_report", "attention_drift", "influence_summary", "cluster_growth_decay",
    "diversity_warning", "source_shaping_summary",
}


def test_builder_pivot_detects_exact_shift_growth_evidence_and_windows(tmp_path: Path) -> None:
    with _scenario_session(tmp_path, "builder") as session:
        history = builder_pivot(session)
        result = generate_reflective_insight_loop(session, "local-user", reference_time=history.now)
        cards = _cards(result)

        assert set(cards) == EXPECTED_KINDS
        assert result.window_start == REFERENCE_TIME - timedelta(days=7)
        assert result.window_end == REFERENCE_TIME
        assert result.report.thought_count == 8
        assert cards["weekly_report"].metrics == {
            "current_nodes": 8, "previous_nodes": 6, "delta": 2, "domain_events": 0,
        }
        drift = cards["attention_drift"]
        assert drift.metrics["rising_theme"] == "Product"
        assert drift.metrics["rising_delta"] == 0.75
        assert drift.metrics["current_distribution"] == {"Product": 0.75, "Career": 0.25}
        assert drift.metrics["previous_distribution"] == {"Career": 1.0}
        assert history.clusters["Product"].id in _evidence_ids(drift)
        growth = cards["cluster_growth_decay"]
        assert growth.metrics["cluster_deltas"] == {"Product": 6, "Career": -4}
        assert {history.clusters["Product"].id, history.clusters["Career"].id} <= _evidence_ids(growth)
        _assert_evidence_integrity(history, result)


def test_source_monoculture_detects_domain_and_diversity_with_evidence(tmp_path: Path) -> None:
    with _scenario_session(tmp_path, "sources") as session:
        history = source_monoculture(session)
        result = generate_reflective_insight_loop(session, "local-user", reference_time=history.now)
        cards = _cards(result)

        source = cards["source_shaping_summary"]
        assert source.severity == "warning"
        assert source.metrics["dominant_kind"] == "link"
        assert source.metrics["dominant_share"] == 1.0
        assert source.metrics["domain_counts"] == {"research.example": 5, "alternate.example": 1}
        assert any(item.evidence_type == "source" and item.id == "research.example" for item in source.evidence)
        diversity = cards["diversity_warning"]
        assert diversity.severity == "warning"
        assert diversity.metrics["dominant_theme"] == "Research"
        assert diversity.metrics["dominant_share"] == 1.0
        assert diversity.metrics["theme_count"] == 1
        _assert_evidence_integrity(history, result)


def test_connected_synthesis_identifies_known_hub_and_explicit_references(tmp_path: Path) -> None:
    with _scenario_session(tmp_path, "connected") as session:
        history = connected_synthesis(session)
        result = generate_reflective_insight_loop(session, "local-user", reference_time=history.now)
        cards = _cards(result)

        influence = cards["influence_summary"]
        hub = history.nodes["current_decision_0"]
        assert influence.metrics["top_node_id"] == hub.id
        assert influence.metrics["semantic_edges"] == 4
        assert influence.metrics["reply_nodes"] == 1
        assert influence.metrics["quoted_nodes"] == 1
        assert hub.id in _evidence_ids(influence)
        assert set(edge.id for edge in history.edges.values()).intersection(_evidence_ids(influence))
        assert cards["attention_drift"].metrics["rising_theme"] == "Decision"
        assert cards["attention_drift"].metrics["rising_delta"] == 1.0
        _assert_evidence_integrity(history, result)


def test_reflective_evaluation_is_idempotent(tmp_path: Path) -> None:
    with _scenario_session(tmp_path, "idempotent") as session:
        history = builder_pivot(session)
        first = generate_reflective_insight_loop(session, "local-user", reference_time=history.now)
        first_metrics = {card.kind: card.metrics for card in first.insights}
        count_after_first = session.scalar(select(func.count()).select_from(Insight))

        second = generate_reflective_insight_loop(session, "local-user", reference_time=history.now)

        assert {card.kind: card.metrics for card in second.insights} == first_metrics
        assert second.persisted_insight_ids == first.persisted_insight_ids
        assert session.scalar(select(func.count()).select_from(Insight)) == count_after_first == 6


def test_counterfactual_timestamps_remove_product_as_rising_theme(tmp_path: Path) -> None:
    with _scenario_session(tmp_path, "time-counterfactual") as session:
        history = builder_pivot(session)
        for key, node in history.nodes.items():
            if key.startswith("current_product"):
                node.created_at = REFERENCE_TIME - timedelta(days=10)
                node.updated_at = node.created_at
        session.commit()

        drift = _cards(generate_reflective_insight_loop(session, "local-user", reference_time=history.now))["attention_drift"]
        assert drift.metrics["rising_theme"] != "Product"
        assert drift.metrics["rising_delta"] != 0.75


def test_counterfactual_domains_and_edges_remove_causal_signals(tmp_path: Path) -> None:
    with _scenario_session(tmp_path, "domain-counterfactual") as session:
        history = source_monoculture(session)
        for index in range(6):
            history.nodes[f"current_link_{index}"].link_url = f"https://distinct-{index}.example/item"
        session.commit()
        source = _cards(generate_reflective_insight_loop(session, "local-user", reference_time=history.now))["source_shaping_summary"]
        assert max(source.metrics["domain_counts"].values()) == 1
        assert not any(item.evidence_type == "source" and item.id == "research.example" for item in source.evidence)

    with _scenario_session(tmp_path, "edge-counterfactual") as session:
        history = connected_synthesis(session)
        session.execute(delete(NodeEdge).where(NodeEdge.user_id == "local-user"))
        session.commit()
        influence = _cards(generate_reflective_insight_loop(session, "local-user", reference_time=history.now))["influence_summary"]
        assert influence.metrics["semantic_edges"] == 0
        assert influence.metrics["top_node_id"] is None


def _scenario_session(tmp_path: Path, name: str):
    set_database_url(f"sqlite:///{tmp_path / f'{name}.db'}")
    init_db()
    return db_package.session.SessionLocal()


def _cards(result):
    return {card.kind: card for card in result.insights}


def _evidence_ids(card) -> set[str]:
    return {item.id for item in card.evidence}


def _assert_evidence_integrity(history: MagicMomentHistory, result) -> None:
    fixture_ids = (
        {node.id for node in history.nodes.values()}
        | {cluster.id for cluster in history.clusters.values()}
        | {edge.id for edge in history.edges.values()}
    )
    for card in result.insights:
        for evidence in card.evidence:
            if evidence.evidence_type != "source":
                assert evidence.id in fixture_ids, f"{card.kind} cited unknown {evidence.evidence_type} {evidence.id}"
