from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from math import log2
from urllib.parse import urlparse

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.content_node import ContentNode
from app.models.domain_event import DomainEvent
from app.models.insight import Insight
from app.models.node_cluster import NodeCluster
from app.models.node_edge import NodeEdge
from app.models.weekly_report import WeeklyReport
from app.models.workflow_job import WorkflowJob
from app.schemas.reflective_insight import (
    PersistedReflectiveInsightRead,
    ReflectiveFeedbackUpdate,
    ReflectiveEvidenceRead,
    ReflectiveInsightRead,
    ReflectiveLoopRunRead,
    ReflectiveWeeklyReportRead,
)
from app.services.event_service import emit_event
from app.services.user_service import ensure_user_exists
from app.services.workflow_service import complete_job, enqueue_job, fail_job, should_run_inline, start_job


REFLECTIVE_JOB_TYPE = "reflective_insight_loop"
REFLECTIVE_INSIGHT_PREFIX = "reflective_"
ATTENTION_DRIFT_CONTRACT_VERSION = 1
ATTENTION_DRIFT_MINIMUM_SAMPLE = 4
SOURCE_SHAPING_CONTRACT_VERSION = 1
SOURCE_SHAPING_MINIMUM_SAMPLE = 4
NON_CLINICAL_LIMITATION = (
    "Based only on nodes saved in these time windows; this is not a clinical or psychological assessment."
)
SOURCE_SHAPING_LIMITATION = (
    "Based only on input types and links saved in these windows; it is incomplete, does not establish influence, "
    "and is not a clinical or psychological assessment."
)


def enqueue_reflective_insight_loop(
    session: Session,
    user_id: str,
    *,
    reference_time: datetime | None = None,
    run_inline: bool | None = None,
) -> WorkflowJob | ReflectiveLoopRunRead:
    ensure_user_exists(session, user_id)
    payload = {"reference_time": _ensure_utc(reference_time).isoformat() if reference_time else None}
    job = enqueue_job(
        session,
        job_type=REFLECTIVE_JOB_TYPE,
        aggregate_type="user",
        aggregate_id=user_id,
        payload=payload,
        actor_id=user_id,
    )
    session.commit()
    session.refresh(job)

    if run_inline if run_inline is not None else should_run_inline():
        return run_reflective_insight_job(session, job)
    return job


def run_reflective_insight_job(session: Session, job: WorkflowJob) -> ReflectiveLoopRunRead:
    if job.job_type != REFLECTIVE_JOB_TYPE:
        raise ValueError(f"unsupported job type: {job.job_type}")

    reference_time = None
    if job.payload.get("reference_time"):
        reference_time = datetime.fromisoformat(job.payload["reference_time"])

    start_job(session, job)
    session.commit()
    try:
        result = generate_reflective_insight_loop(
            session,
            job.aggregate_id,
            reference_time=reference_time,
            workflow_job_id=job.id,
            commit_changes=False,
        )
        complete_job(
            session,
            job,
            {
                "report_id": result.report.id,
                "insight_count": len(result.insights),
                "persisted_insight_ids": result.persisted_insight_ids,
                "event_id": result.event_id,
            },
        )
        session.commit()
        session.refresh(job)
        return result.model_copy(update={"workflow_status": job.status})
    except Exception as exc:
        fail_job(session, job, str(exc))
        session.commit()
        raise


def generate_reflective_insight_loop(
    session: Session,
    user_id: str,
    *,
    reference_time: datetime | None = None,
    workflow_job_id: str | None = None,
    commit_changes: bool = True,
) -> ReflectiveLoopRunRead:
    ensure_user_exists(session, user_id)
    now = _ensure_utc(reference_time or datetime.now(timezone.utc))
    window_start = now - timedelta(days=7)
    previous_start = now - timedelta(days=14)
    thirty_day_start = now - timedelta(days=30)

    nodes = _load_nodes(session, user_id, thirty_day_start, now)
    all_nodes = _load_nodes(session, user_id, None, now)
    clusters = {cluster.id: cluster for cluster in session.scalars(select(NodeCluster).where(NodeCluster.user_id == user_id))}
    edges = list(session.scalars(select(NodeEdge).where(NodeEdge.user_id == user_id)))
    events = _load_events(session, user_id, thirty_day_start, now)

    current_nodes = [node for node in nodes if _between(node.created_at, window_start, now)]
    previous_nodes = [node for node in nodes if _between(node.created_at, previous_start, window_start)]
    thirty_day_nodes = [node for node in nodes if _between(node.created_at, thirty_day_start, now)]

    insight_cards = [
        _weekly_report_card(current_nodes, previous_nodes, clusters, events, window_start, now),
        _attention_drift_card(current_nodes, previous_nodes, clusters),
        _influence_summary_card(current_nodes, all_nodes, clusters, edges),
        _cluster_growth_decay_card(current_nodes, previous_nodes, clusters),
        _diversity_warning_card(thirty_day_nodes, clusters),
        _source_shaping_card(current_nodes, previous_nodes),
    ]

    report_model = _upsert_weekly_report(session, user_id, now.date(), current_nodes, previous_nodes, insight_cards)
    persisted_ids = _persist_insights(
        session, user_id, report_model.id, insight_cards, previous_start, window_start, now
    )

    event = emit_event(
        session,
        event_type="reflective_insights_generated",
        aggregate_type="user",
        aggregate_id=user_id,
        actor_id=user_id,
        payload={
            "workflow_job_id": workflow_job_id,
            "report_id": report_model.id,
            "insight_count": len(insight_cards),
            "node_count": len(current_nodes),
            "event_count": len(events),
        },
    )
    if commit_changes:
        session.commit()
        session.refresh(report_model)
        session.refresh(event)
    else:
        session.flush()

    report_read = ReflectiveWeeklyReportRead(
        id=report_model.id,
        week_start=report_model.week_start,
        week_end=report_model.week_end,
        summary=report_model.content.get("summary", ""),
        thought_count=len(current_nodes),
        insight_count=len(insight_cards),
        content=report_model.content,
    )
    return ReflectiveLoopRunRead(
        user_id=user_id,
        generated_at=now,
        window_start=window_start,
        window_end=now,
        workflow_job_id=workflow_job_id,
        workflow_status="completed" if workflow_job_id else None,
        report=report_read,
        insights=insight_cards,
        persisted_insight_ids=persisted_ids,
        event_id=event.id,
    )


def _weekly_report_card(
    current_nodes: list[ContentNode],
    previous_nodes: list[ContentNode],
    clusters: dict[str, NodeCluster],
    events: list[DomainEvent],
    window_start: datetime,
    now: datetime,
) -> ReflectiveInsightRead:
    cluster_counts = _cluster_counts(current_nodes)
    previous_counts = _cluster_counts(previous_nodes)
    top_cluster_id = cluster_counts.most_common(1)[0][0] if cluster_counts else None
    top_cluster = clusters.get(top_cluster_id) if top_cluster_id else None
    delta = len(current_nodes) - len(previous_nodes)
    event_count = len([event for event in events if _between(event.created_at, window_start, now)])
    cluster_label = top_cluster.label if top_cluster else "unclustered reflection"
    summary = (
        f"This week added {len(current_nodes)} nodes ({delta:+d} vs the previous week), "
        f"with {cluster_label} carrying the most visible graph evidence."
    )
    evidence = []
    if top_cluster:
        evidence.append(_cluster_evidence(top_cluster, "largest current-week cluster", {"current_nodes": cluster_counts[top_cluster.id]}))
    evidence.extend(_node_evidence(node, "recent weekly report sample") for node in _top_nodes(current_nodes, limit=3))
    return ReflectiveInsightRead(
        kind="weekly_report",
        title="Weekly Thought Report",
        summary=summary,
        confidence=_confidence(len(current_nodes), target=6),
        metrics={
            "current_nodes": len(current_nodes),
            "previous_nodes": len(previous_nodes),
            "delta": delta,
            "domain_events": event_count,
        },
        evidence=evidence,
        action_hint="Review the largest cluster first; it is the clearest visible thread from this week.",
    )


def _attention_drift_card(
    current_nodes: list[ContentNode],
    previous_nodes: list[ContentNode],
    clusters: dict[str, NodeCluster],
) -> ReflectiveInsightRead:
    current = _theme_distribution(current_nodes, clusters)
    previous = _theme_distribution(previous_nodes, clusters)
    labels = set(current) | set(previous)
    drift_score = round(sum(abs(current.get(label, 0.0) - previous.get(label, 0.0)) for label in labels) / 2, 3)
    rising_label = next(
        iter(sorted(labels, key=lambda label: (-(current.get(label, 0.0) - previous.get(label, 0.0)), label))),
        "general reflection",
    )
    rising_delta = round(current.get(rising_label, 0.0) - previous.get(rising_label, 0.0), 3)
    if current_nodes and rising_delta > 0.1:
        summary = f"Your saved nodes show more attention toward {rising_label}, up {int(rising_delta * 100)} percentage points from the comparison window."
    else:
        summary = "Your saved nodes show no large change in theme share between these two windows."
    evidence = _theme_evidence(current_nodes, clusters, rising_label, "attention drift evidence")
    return ReflectiveInsightRead(
        kind="attention_drift",
        title="Attention Drift",
        summary=summary,
        confidence=_confidence(len(current_nodes) + len(previous_nodes), target=10),
        metrics={
            "drift_score": drift_score,
            "rising_theme": rising_label,
            "rising_delta": rising_delta,
            "current_rising_share": current.get(rising_label, 0.0),
            "previous_rising_share": previous.get(rising_label, 0.0),
            "current_node_count": len(current_nodes),
            "previous_node_count": len(previous_nodes),
            "current_distribution": current,
            "previous_distribution": previous,
        },
        evidence=evidence,
        action_hint="If the drift is intentional, add follow-up nodes; if not, revisit an older cluster.",
    )


def _influence_summary_card(
    current_nodes: list[ContentNode],
    all_nodes: list[ContentNode],
    clusters: dict[str, NodeCluster],
    edges: list[NodeEdge],
) -> ReflectiveInsightRead:
    node_by_id = {node.id: node for node in all_nodes}
    current_ids = {node.id for node in current_nodes}
    related_edges = [edge for edge in edges if edge.source_id in current_ids or edge.target_id in current_ids]
    edge_counts: Counter[str] = Counter()
    for edge in related_edges:
        edge_counts[edge.source_id] += 1
        edge_counts[edge.target_id] += 1
    top_node_id = next((node_id for node_id, _ in edge_counts.most_common() if node_id in node_by_id), None)
    top_node = node_by_id.get(top_node_id) if top_node_id else None
    quote_count = sum(1 for node in current_nodes if node.quote_of_node_id)
    reply_count = sum(1 for node in current_nodes if node.reply_to_node_id)
    if top_node:
        summary = f"{_node_label(top_node)} is the strongest local influence, appearing in {edge_counts[top_node.id]} semantic links."
    elif quote_count or reply_count:
        summary = f"Influence is coming through explicit graph references: {reply_count} replies and {quote_count} quotes this week."
    else:
        summary = "No dominant influence source is visible yet; this week's nodes are mostly self-contained."
    evidence = []
    if top_node:
        evidence.append(_node_evidence(top_node, "most semantically connected node"))
    for edge in related_edges[:3]:
        evidence.append(_edge_evidence(edge, "semantic influence link"))
    for node in current_nodes:
        if node.reply_to_node_id or node.quote_of_node_id:
            evidence.append(_node_evidence(node, "explicit reply or quote reference"))
        if len(evidence) >= 5:
            break
    cluster_id = top_node.cluster_id if top_node else None
    if cluster_id and cluster_id in clusters:
        evidence.append(_cluster_evidence(clusters[cluster_id], "cluster containing strongest influence node"))
    return ReflectiveInsightRead(
        kind="influence_summary",
        title="Influence Summary",
        summary=summary,
        confidence=_confidence(len(related_edges) + quote_count + reply_count, target=5),
        metrics={
            "semantic_edges": len(related_edges),
            "reply_nodes": reply_count,
            "quoted_nodes": quote_count,
            "top_node_id": top_node.id if top_node else None,
        },
        evidence=evidence[:6],
        action_hint="Open the strongest linked node before adding new notes; it explains the local pull.",
    )


def _cluster_growth_decay_card(
    current_nodes: list[ContentNode],
    previous_nodes: list[ContentNode],
    clusters: dict[str, NodeCluster],
) -> ReflectiveInsightRead:
    current = _cluster_counts(current_nodes)
    previous = _cluster_counts(previous_nodes)
    cluster_ids = set(current) | set(previous)
    deltas = {cluster_id: current.get(cluster_id, 0) - previous.get(cluster_id, 0) for cluster_id in cluster_ids}
    growing_id = max(deltas, key=deltas.get, default=None)
    decaying_id = min(deltas, key=deltas.get, default=None)
    growing = clusters.get(growing_id) if growing_id else None
    decaying = clusters.get(decaying_id) if decaying_id else None
    if growing and deltas[growing.id] > 0:
        summary = f"{growing.label} grew by {deltas[growing.id]:+d} nodes this week."
        if decaying and deltas[decaying.id] < 0:
            summary += f" {decaying.label} cooled by {deltas[decaying.id]:d}."
    else:
        summary = "Cluster movement is flat; growth and decay are not yet separated by visible node counts."
    evidence = []
    if growing:
        evidence.append(_cluster_evidence(growing, "largest growth delta", {"delta": deltas[growing.id]}))
    if decaying and decaying.id != (growing.id if growing else None):
        evidence.append(_cluster_evidence(decaying, "largest decay delta", {"delta": deltas[decaying.id]}))
    return ReflectiveInsightRead(
        kind="cluster_growth_decay",
        title="Cluster Growth And Decay",
        summary=summary,
        confidence=_confidence(len(current_nodes) + len(previous_nodes), target=8),
        metrics={
            "cluster_deltas": {
                clusters[cluster_id].label if cluster_id in clusters else "unclustered": delta
                for cluster_id, delta in deltas.items()
            },
        },
        evidence=evidence,
        action_hint="Use the decaying cluster as a prompt if you want to rebalance attention.",
    )


def _diversity_warning_card(
    nodes: list[ContentNode],
    clusters: dict[str, NodeCluster],
) -> ReflectiveInsightRead:
    distribution = _theme_distribution(nodes, clusters)
    diversity_score = _normalized_entropy(distribution)
    dominant_label = max(distribution, key=distribution.get, default="general reflection")
    dominant_share = round(distribution.get(dominant_label, 0.0), 3)
    severity = "warning" if len(nodes) >= 4 and diversity_score < 0.45 else "info"
    if severity == "warning":
        summary = f"{int(dominant_share * 100)}% of the last 30 days sits in {dominant_label}; perspective may be narrowing."
    else:
        summary = f"Recent thinking is spread across {len(distribution)} visible themes with a diversity score of {diversity_score:.2f}."
    evidence = _theme_evidence(nodes, clusters, dominant_label, "dominant diversity theme")
    return ReflectiveInsightRead(
        kind="diversity_warning",
        title="Diversity Warning",
        summary=summary,
        severity=severity,
        confidence=_confidence(len(nodes), target=12),
        metrics={
            "diversity_score": diversity_score,
            "dominant_theme": dominant_label,
            "dominant_share": dominant_share,
            "theme_count": len(distribution),
        },
        evidence=evidence,
        action_hint="Add one node from a neglected theme or search for an adjacent public perspective.",
    )


def _source_shaping_card(
    current_nodes: list[ContentNode],
    previous_nodes: list[ContentNode],
) -> ReflectiveInsightRead:
    kind_counts = Counter(node.kind for node in current_nodes)
    previous_kind_counts = Counter(node.kind for node in previous_nodes)
    domain_counts = Counter(_host(node.link_url) for node in current_nodes if node.link_url)
    previous_domain_counts = Counter(_host(node.link_url) for node in previous_nodes if node.link_url)
    total = max(len(current_nodes), 1)
    dominant_kind, dominant_count = kind_counts.most_common(1)[0] if kind_counts else ("none", 0)
    dominant_share = dominant_count / total
    top_domain = domain_counts.most_common(1)[0][0] if domain_counts else None
    severity = "warning" if len(current_nodes) >= 4 and dominant_share >= 0.75 else "info"
    if top_domain:
        summary = f"Among your saved inputs this week, {dominant_kind} nodes are most common and {top_domain} is the most repeated linked domain."
    elif current_nodes:
        summary = f"Among your saved inputs this week, {dominant_kind} nodes are most common ({int(dominant_share * 100)}%)."
    else:
        summary = "No new source mix is visible this week."
    evidence = []
    for node in current_nodes[:5]:
        reason = "source mix sample"
        if node.link_url:
            reason = f"linked source: {_host(node.link_url)}"
        evidence.append(_node_evidence(node, reason))
    if top_domain:
        evidence.append(
            ReflectiveEvidenceRead(
                evidence_type="source",
                id=top_domain,
                label=top_domain,
                reason="most repeated linked source domain",
                metadata={"count": domain_counts[top_domain]},
            )
        )
    return ReflectiveInsightRead(
        kind="source_shaping_summary",
        title="Source-Shaping Summary",
        summary=summary,
        severity=severity,
        confidence=_confidence(len(current_nodes), target=8),
        metrics={
            "kind_counts": dict(kind_counts),
            "previous_kind_counts": dict(previous_kind_counts),
            "domain_counts": dict(domain_counts),
            "previous_domain_counts": dict(previous_domain_counts),
            "current_node_count": len(current_nodes),
            "previous_node_count": len(previous_nodes),
            "dominant_kind": dominant_kind,
            "dominant_share": round(dominant_share, 3),
        },
        evidence=evidence,
        action_hint="If one source type dominates, add a contrasting note, image, link, or reply.",
    )


def _upsert_weekly_report(
    session: Session,
    user_id: str,
    week_end: date,
    current_nodes: list[ContentNode],
    previous_nodes: list[ContentNode],
    insights: list[ReflectiveInsightRead],
) -> WeeklyReport:
    week_start = week_end - timedelta(days=6)
    report = session.scalar(
        select(WeeklyReport).where(WeeklyReport.user_id == user_id, WeeklyReport.week_start == week_start)
    )
    summary = insights[0].summary if insights else "No reflective insights generated yet."
    content = {
        "summary": summary,
        "thought_count": len(current_nodes),
        "previous_thought_count": len(previous_nodes),
        "insights": [insight.summary for insight in insights],
        "reflective_insights": [insight.model_dump(mode="json") for insight in insights],
        "evidence_counts": {
            "nodes": len(current_nodes),
            "insights": len(insights),
        },
        "source": "reflective_insight_loop",
    }
    if report is None:
        report = WeeklyReport(user_id=user_id, week_start=week_start, week_end=week_end)
    report.week_end = week_end
    report.content = content
    report.sent_at = week_end
    session.add(report)
    session.flush()
    return report


def _persist_insights(
    session: Session,
    user_id: str,
    report_id: str,
    insights: list[ReflectiveInsightRead],
    comparison_start: datetime,
    window_start: datetime,
    window_end: datetime,
) -> list[str]:
    persisted_ids: list[str] = []
    for card in insights:
        kind = f"{REFLECTIVE_INSIGHT_PREFIX}{card.kind}"
        stable_key = None
        if card.kind in {"attention_drift", "source_shaping_summary"}:
            contract_version = (
                ATTENTION_DRIFT_CONTRACT_VERSION
                if card.kind == "attention_drift"
                else SOURCE_SHAPING_CONTRACT_VERSION
            )
            stable_key = (
                f"{user_id}:{card.kind}:{window_end.date().isoformat()}:v{contract_version}"
            )
        existing = session.scalar(
            select(Insight).where(
                Insight.user_id == user_id,
                Insight.stable_key == stable_key,
            )
        ) if stable_key else session.scalar(
            select(Insight).where(
                Insight.user_id == user_id,
                Insight.kind == kind,
                Insight.content == card.summary,
                Insight.dismissed.is_(False),
            )
        )
        if existing:
            if stable_key:
                existing.content = card.summary
                existing.raw_content = f"{card.title}: {card.summary}"
                existing.supporting_data = _stable_reflective_contract(card, comparison_start, window_start, window_end)
                session.add(existing)
            persisted_ids.append(existing.id)
            continue
        model = Insight(
            user_id=user_id,
            kind=kind,
            content=card.summary,
            raw_content=f"{card.title}: {card.summary}",
            stable_key=stable_key,
            supporting_data=_stable_reflective_contract(card, comparison_start, window_start, window_end)
            if stable_key else {
                "report_id": report_id,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "metrics": card.metrics,
                "evidence": [item.model_dump(mode="json") for item in card.evidence],
                "action_hint": card.action_hint,
            },
        )
        session.add(model)
        session.flush()
        persisted_ids.append(model.id)
    return persisted_ids


def _stable_reflective_contract(
    card: ReflectiveInsightRead,
    comparison_start: datetime,
    window_start: datetime,
    window_end: datetime,
) -> dict:
    if card.kind == "attention_drift":
        return _attention_drift_contract(card, comparison_start, window_start, window_end)
    if card.kind == "source_shaping_summary":
        return _source_shaping_contract(card, comparison_start, window_start, window_end)
    raise ValueError(f"unsupported stable reflective contract: {card.kind}")


def _attention_drift_contract(
    card: ReflectiveInsightRead,
    comparison_start: datetime,
    window_start: datetime,
    window_end: datetime,
) -> dict:
    current_nodes = int(card.metrics.get("current_node_count", 0))
    previous_nodes = int(card.metrics.get("previous_node_count", 0))
    sample_size = current_nodes + previous_nodes
    ready = current_nodes >= 2 and previous_nodes >= 2 and sample_size >= ATTENTION_DRIFT_MINIMUM_SAMPLE
    confidence_score = _confidence(sample_size, target=10) if ready else 0.0
    confidence_label = "high" if confidence_score >= 0.8 else "medium" if confidence_score >= 0.5 else "low"
    current_share = float(card.metrics.get("current_rising_share", 0.0))
    previous_share = float(card.metrics.get("previous_rising_share", 0.0))
    return {
        "contract_version": ATTENTION_DRIFT_CONTRACT_VERSION,
        "title": card.title,
        "summary": card.summary if ready else "There is not enough saved activity in both windows to describe a change yet.",
        "generated_at": window_end.isoformat(),
        "status": "ready" if ready else "insufficient_data",
        "window": {
            "current_start": window_start.isoformat(), "current_end": window_end.isoformat(),
            "comparison_start": comparison_start.isoformat(), "comparison_end": window_start.isoformat(),
        },
        "metrics": [{
            "key": "rising_theme_share", "label": f"Share of {card.metrics.get('rising_theme', 'theme')} nodes",
            "current": current_share, "previous": previous_share,
            "delta": round(current_share - previous_share, 3), "unit": "proportion",
            "method": "Count nodes per cluster label in each 7-day window, then divide by all nodes in that window.",
        }],
        "evidence": [item.model_dump(mode="json") for item in card.evidence] if ready else [],
        "confidence": {
            "score": confidence_score, "label": confidence_label,
            "basis": "Evidence sufficiency from saved-node counts in both windows; not certainty about the user.",
            "sample_size": sample_size, "minimum_sample_size": ATTENTION_DRIFT_MINIMUM_SAMPLE,
        },
        "limitations": [NON_CLINICAL_LIMITATION],
        "action_hint": card.action_hint if ready else "Add nodes over time before comparing attention patterns.",
    }


def _source_shaping_contract(
    card: ReflectiveInsightRead,
    comparison_start: datetime,
    window_start: datetime,
    window_end: datetime,
) -> dict:
    current_count = int(card.metrics.get("current_node_count", 0))
    previous_count = int(card.metrics.get("previous_node_count", 0))
    sample_size = current_count + previous_count
    ready = current_count >= 2 and previous_count >= 2 and sample_size >= SOURCE_SHAPING_MINIMUM_SAMPLE
    confidence_score = _confidence(sample_size, target=10) if ready else 0.0
    confidence_label = "high" if confidence_score >= 0.8 else "medium" if confidence_score >= 0.5 else "low"
    kind_counts = card.metrics.get("kind_counts", {})
    previous_kind_counts = card.metrics.get("previous_kind_counts", {})
    dominant_kind = str(card.metrics.get("dominant_kind", "thought"))
    current_kind_share = float(kind_counts.get(dominant_kind, 0)) / current_count if current_count else 0.0
    previous_kind_share = float(previous_kind_counts.get(dominant_kind, 0)) / previous_count if previous_count else 0.0
    domains = card.metrics.get("domain_counts", {})
    previous_domains = card.metrics.get("previous_domain_counts", {})
    top_domain = max(domains, key=domains.get, default=None)
    current_link_count = sum(int(value) for value in domains.values())
    previous_link_count = sum(int(value) for value in previous_domains.values())
    current_domain_count = int(domains.get(top_domain, 0)) if top_domain else 0
    previous_domain_count = int(previous_domains.get(top_domain, 0)) if top_domain else 0
    metrics = [{
        "key": "dominant_input_kind_share", "label": f"Share of {dominant_kind} inputs",
        "current": round(current_kind_share, 3), "previous": round(previous_kind_share, 3),
        "delta": round(current_kind_share - previous_kind_share, 3), "unit": "proportion",
        "method": "Count saved nodes by input kind in each 7-day window, then divide by all saved nodes in that window.",
    }]
    if top_domain:
        current_domain_share = current_domain_count / current_link_count if current_link_count else 0.0
        previous_domain_share = previous_domain_count / previous_link_count if previous_link_count else 0.0
        metrics.extend([
            {
                "key": "top_source_domain_share", "label": f"Share of linked inputs from {top_domain}",
                "current": round(current_domain_share, 3), "previous": round(previous_domain_share, 3),
                "delta": round(current_domain_share - previous_domain_share, 3), "unit": "proportion",
                "method": "Count saved link nodes by hostname in each window, divided by all link nodes in that window.",
            },
            {
                "key": "top_source_domain_count", "label": f"Saved links from {top_domain}",
                "current": float(current_domain_count), "previous": float(previous_domain_count),
                "delta": float(current_domain_count - previous_domain_count), "unit": "nodes",
                "method": "Count saved link nodes whose normalized hostname matches the current window's top domain.",
            },
        ])
    return {
        "contract_version": SOURCE_SHAPING_CONTRACT_VERSION,
        "title": card.title,
        "summary": card.summary if ready else "There is not enough saved activity in both windows to compare input patterns yet.",
        "generated_at": window_end.isoformat(),
        "status": "ready" if ready else "insufficient_data",
        "window": {
            "current_start": window_start.isoformat(), "current_end": window_end.isoformat(),
            "comparison_start": comparison_start.isoformat(), "comparison_end": window_start.isoformat(),
        },
        "metrics": metrics,
        "evidence": [item.model_dump(mode="json") for item in card.evidence] if ready else [],
        "confidence": {
            "score": confidence_score, "label": confidence_label,
            "basis": "Evidence sufficiency from saved-node counts in both windows; not completeness or proof of influence.",
            "sample_size": sample_size, "minimum_sample_size": SOURCE_SHAPING_MINIMUM_SAMPLE,
        },
        "limitations": [SOURCE_SHAPING_LIMITATION],
        "action_hint": card.action_hint if ready else "Save inputs over time before comparing source patterns.",
    }


def list_persisted_reflective_insights(
    session: Session,
    user_id: str,
    *,
    include_dismissed: bool = False,
    kind: str | None = None,
    limit: int = 50,
) -> list[PersistedReflectiveInsightRead]:
    statement = select(Insight).where(
        Insight.user_id == user_id,
        Insight.kind.in_((
            f"{REFLECTIVE_INSIGHT_PREFIX}attention_drift",
            f"{REFLECTIVE_INSIGHT_PREFIX}source_shaping_summary",
        )),
        Insight.stable_key.is_not(None),
        _current_stable_contract_predicate(),
    )
    if not include_dismissed:
        statement = statement.where(Insight.dismissed.is_(False))
    if kind:
        statement = statement.where(Insight.kind == f"{REFLECTIVE_INSIGHT_PREFIX}{kind}")
    generated_at = Insight.supporting_data["generated_at"].as_string()
    models = session.scalars(statement.order_by(generated_at.desc(), Insight.id.desc()).limit(limit)).all()
    return [_persisted_reflective_insight_read(model) for model in models]


def update_reflective_insight_feedback(
    session: Session,
    user_id: str,
    insight_id: str,
    payload: ReflectiveFeedbackUpdate,
) -> PersistedReflectiveInsightRead | None:
    model = session.scalar(
        select(Insight).where(
            Insight.id == insight_id,
            Insight.user_id == user_id,
            Insight.kind.in_((
                f"{REFLECTIVE_INSIGHT_PREFIX}attention_drift",
                f"{REFLECTIVE_INSIGHT_PREFIX}source_shaping_summary",
            )),
            Insight.stable_key.is_not(None),
            _current_stable_contract_predicate(),
        )
    )
    if model is None:
        return None
    feedback = dict(model.feedback_json or {})
    if payload.dismissed is not None:
        model.dismissed = payload.dismissed
        feedback["dismissed"] = payload.dismissed
    if "correction" in payload.model_fields_set:
        feedback["correction"] = payload.correction
    if "annotation" in payload.model_fields_set:
        feedback["annotation"] = payload.annotation.strip() if payload.annotation else None
    now = datetime.now(timezone.utc)
    model.feedback_json = feedback
    model.feedback_updated_at = now
    session.add(model)
    emit_event(
        session,
        event_type="reflective_insight_feedback_updated",
        aggregate_type="insight",
        aggregate_id=model.id,
        actor_id=user_id,
        payload={
            "dismissed": model.dismissed,
            "correction": feedback.get("correction"),
            "has_annotation": bool(feedback.get("annotation")),
        },
    )
    session.commit()
    session.refresh(model)
    return _persisted_reflective_insight_read(model)


def _current_stable_contract_predicate():
    return or_(
        and_(
            Insight.kind == f"{REFLECTIVE_INSIGHT_PREFIX}attention_drift",
            Insight.supporting_data["contract_version"].as_integer() == ATTENTION_DRIFT_CONTRACT_VERSION,
        ),
        and_(
            Insight.kind == f"{REFLECTIVE_INSIGHT_PREFIX}source_shaping_summary",
            Insight.supporting_data["contract_version"].as_integer() == SOURCE_SHAPING_CONTRACT_VERSION,
        ),
    )


def _persisted_reflective_insight_read(model: Insight) -> PersistedReflectiveInsightRead:
    contract = dict(model.supporting_data or {})
    return PersistedReflectiveInsightRead(
        id=model.id,
        kind=model.kind.removeprefix(REFLECTIVE_INSIGHT_PREFIX),
        **contract,
        feedback={
            "dismissed": model.dismissed,
            "correction": (model.feedback_json or {}).get("correction"),
            "annotation": (model.feedback_json or {}).get("annotation"),
            "updated_at": model.feedback_updated_at,
        },
    )


# Compatibility alias for early backend callers of the first vertical slice.
list_persisted_attention_drift_insights = list_persisted_reflective_insights


def _load_nodes(
    session: Session,
    user_id: str,
    start: datetime | None,
    end: datetime,
) -> list[ContentNode]:
    query = select(ContentNode).where(ContentNode.user_id == user_id, ContentNode.created_at <= end)
    if start is not None:
        query = query.where(ContentNode.created_at >= start)
    return list(session.scalars(query.order_by(ContentNode.created_at.desc())))


def _load_events(session: Session, user_id: str, start: datetime, end: datetime) -> list[DomainEvent]:
    return list(
        session.scalars(
            select(DomainEvent)
            .where(
                DomainEvent.actor_id == user_id,
                DomainEvent.created_at >= start,
                DomainEvent.created_at <= end,
            )
            .order_by(DomainEvent.created_at.desc())
        )
    )


def _between(value: datetime, start: datetime, end: datetime) -> bool:
    checked = _ensure_utc(value)
    return start <= checked < end


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _cluster_counts(nodes: list[ContentNode]) -> Counter[str]:
    return Counter(node.cluster_id for node in nodes if node.cluster_id)


def _theme_distribution(nodes: list[ContentNode], clusters: dict[str, NodeCluster]) -> dict[str, float]:
    labels: Counter[str] = Counter()
    for node in nodes:
        if node.cluster_id and node.cluster_id in clusters:
            labels[clusters[node.cluster_id].label] += 1
        elif node.topics:
            labels[node.topics[0].replace("_", " ").title()] += 1
        else:
            labels["Unclustered"] += 1
    total = sum(labels.values())
    if total == 0:
        return {}
    return {label: round(count / total, 3) for label, count in labels.items()}


def _normalized_entropy(distribution: dict[str, float]) -> float:
    if len(distribution) <= 1:
        return 0.0 if distribution else 1.0
    entropy = -sum(value * log2(value) for value in distribution.values() if value > 0)
    return round(entropy / log2(len(distribution)), 3)


def _theme_evidence(
    nodes: list[ContentNode],
    clusters: dict[str, NodeCluster],
    label: str,
    reason: str,
) -> list[ReflectiveEvidenceRead]:
    evidence: list[ReflectiveEvidenceRead] = []
    cluster = next((item for item in clusters.values() if item.label == label), None)
    if cluster:
        evidence.append(_cluster_evidence(cluster, reason))
    for node in nodes:
        node_label = clusters[node.cluster_id].label if node.cluster_id in clusters else None
        topic_label = node.topics[0].replace("_", " ").title() if node.topics else None
        if node_label == label or topic_label == label:
            evidence.append(_node_evidence(node, reason))
        if len(evidence) >= 4:
            break
    return evidence


def _top_nodes(nodes: list[ContentNode], *, limit: int) -> list[ContentNode]:
    return sorted(nodes, key=lambda node: (node.connection_count, node.created_at), reverse=True)[:limit]


def _node_evidence(node: ContentNode, reason: str) -> ReflectiveEvidenceRead:
    return ReflectiveEvidenceRead(
        evidence_type="node",
        id=node.id,
        label=_node_label(node),
        reason=reason,
        created_at=_ensure_utc(node.created_at),
        metadata={
            "kind": node.kind,
            "topics": node.topics,
            "cluster_id": node.cluster_id,
            "connection_count": node.connection_count,
            "visibility": node.visibility,
        },
    )


def _cluster_evidence(cluster: NodeCluster, reason: str, metrics: dict | None = None) -> ReflectiveEvidenceRead:
    return ReflectiveEvidenceRead(
        evidence_type="cluster",
        id=cluster.id,
        label=cluster.label,
        reason=reason,
        created_at=_ensure_utc(cluster.created_at),
        metadata={
            "node_count": cluster.node_count,
            "density_score": cluster.density_score,
            "dominant_topics": cluster.dominant_topics,
            **(metrics or {}),
        },
    )


def _edge_evidence(edge: NodeEdge, reason: str) -> ReflectiveEvidenceRead:
    return ReflectiveEvidenceRead(
        evidence_type="edge",
        id=edge.id,
        label=f"{edge.edge_type} {edge.source_id[:8]}->{edge.target_id[:8]}",
        reason=reason,
        created_at=_ensure_utc(edge.created_at),
        metadata={
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "weight": edge.weight,
            "explanation": edge.explanation,
        },
    )


def _node_label(node: ContentNode) -> str:
    if node.title:
        return node.title
    if node.preview_text:
        return node.preview_text[:80]
    if node.content_text:
        return node.content_text[:80]
    return f"{node.kind} node"


def _host(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www.") or None


def _confidence(count: int, *, target: int) -> float:
    if target <= 0:
        return 1.0
    return round(min(1.0, max(0.2, count / target)), 2)
