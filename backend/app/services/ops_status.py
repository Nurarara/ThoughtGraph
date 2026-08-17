from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.domain_event import DomainEvent
from app.models.infra_read_models import (
    GraphProjectionRun,
    GraphReadModelNode,
    InfraDeadLetterRecord,
    InfraEventConsumerState,
    SearchIndexDocument,
)
from app.schemas.infra import OpsStatusResponse, PartitionStatus, ReplayReadiness, SLOStatus
from app.services.infra_event_bus import InProcessEventBus
from app.services.infra_schema import ensure_infra_schema


def build_ops_status(session: Session, *, event_bus: InProcessEventBus | None = None) -> OpsStatusResponse:
    ensure_infra_schema(session)
    replay = build_replay_readiness(session, event_bus=event_bus)
    return OpsStatusResponse(
        generated_at=datetime.now(timezone.utc),
        partitions=[
            _partition_status(session, "events", "aggregate_type", DomainEvent.aggregate_type),
            _partition_status(session, "search_index", "user_id", SearchIndexDocument.user_id),
            _partition_status(session, "graph_read_model", "user_id", GraphReadModelNode.user_id),
            _partition_status(session, "dead_letters", "consumer_name", InfraDeadLetterRecord.consumer_name),
        ],
        slos=[
            _slo_status("search_index_freshness", _latest_search_indexed_at(session), 300),
            _slo_status("graph_projection_freshness", _latest_graph_projection_completed_at(session), 600),
            _dead_letter_slo(session),
        ],
        replay_readiness=replay,
    )


def build_replay_readiness(session: Session, *, event_bus: InProcessEventBus | None = None) -> ReplayReadiness:
    ensure_infra_schema(session)
    pending = session.scalar(
        select(func.count(InfraDeadLetterRecord.id)).where(InfraDeadLetterRecord.replay_status == "pending")
    ) or 0
    registered = event_bus.consumer_names if event_bus else []
    blockers = []
    if pending and not registered:
        blockers.append("pending dead letters exist but no in-process consumers are registered")
    if _running_consumer_count(session):
        blockers.append("consumer checkpoints are currently running")
    return ReplayReadiness(
        ready=not blockers,
        pending_dead_letters=pending,
        registered_consumers=registered,
        blockers=blockers,
    )


def _partition_status(session: Session, name: str, key_name: str, key_column) -> PartitionStatus:
    rows = session.execute(select(key_column, func.count()).group_by(key_column))
    partitions = {str(key or "unknown"): count for key, count in rows}
    total = sum(partitions.values())
    return PartitionStatus(
        name=name,
        partition_key=key_name,
        partitions=partitions,
        total_records=total,
        status="ok" if total >= 0 else "unknown",
    )


def _slo_status(name: str, timestamp: datetime | None, target_seconds: int) -> SLOStatus:
    if timestamp is None:
        return SLOStatus(
            name=name,
            target_seconds=target_seconds,
            observed_seconds=None,
            status="unknown",
            detail="no successful materialization yet",
        )
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    observed = int((datetime.now(timezone.utc) - timestamp).total_seconds())
    return SLOStatus(
        name=name,
        target_seconds=target_seconds,
        observed_seconds=observed,
        status="ok" if observed <= target_seconds else "degraded",
        detail=f"latest successful update was {observed}s ago",
    )


def _dead_letter_slo(session: Session) -> SLOStatus:
    pending = session.scalar(
        select(func.count(InfraDeadLetterRecord.id)).where(InfraDeadLetterRecord.replay_status == "pending")
    ) or 0
    return SLOStatus(
        name="dead_letter_backlog",
        target_seconds=0,
        observed_seconds=pending,
        status="ok" if pending == 0 else "degraded",
        detail=f"{pending} pending dead-letter records",
    )


def _latest_search_indexed_at(session: Session) -> datetime | None:
    return session.scalar(select(func.max(SearchIndexDocument.indexed_at)))


def _latest_graph_projection_completed_at(session: Session) -> datetime | None:
    return session.scalar(select(func.max(GraphProjectionRun.completed_at)).where(GraphProjectionRun.status == "succeeded"))


def _running_consumer_count(session: Session) -> int:
    return session.scalar(
        select(func.count(InfraEventConsumerState.id)).where(InfraEventConsumerState.status == "running")
    ) or 0
