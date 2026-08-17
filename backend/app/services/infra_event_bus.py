from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain_event import DomainEvent
from app.models.infra_read_models import InfraDeadLetterRecord, InfraEventConsumerState
from app.schemas.infra import DeadLetterRead, EventDispatchOutcome, EventFanoutResponse, ReplayResponse
from app.services.infra_schema import ensure_infra_schema


ConsumerHandler = Callable[[DomainEvent], dict[str, Any] | None | Awaitable[dict[str, Any] | None]]
ReplayHook = Callable[[InfraDeadLetterRecord, DomainEvent | None, bool], None]


@dataclass(frozen=True)
class ConsumerRegistration:
    name: str
    event_types: frozenset[str]
    handler: ConsumerHandler

    def accepts(self, event_type: str) -> bool:
        return "*" in self.event_types or event_type in self.event_types


class InProcessEventBus:
    def __init__(self) -> None:
        self._consumers: dict[str, ConsumerRegistration] = {}
        self._replay_hooks: list[ReplayHook] = []

    @property
    def consumer_names(self) -> list[str]:
        return sorted(self._consumers)

    def register(self, name: str, event_types: list[str] | set[str] | tuple[str, ...], handler: ConsumerHandler) -> None:
        self._consumers[name] = ConsumerRegistration(name=name, event_types=frozenset(event_types), handler=handler)

    def add_replay_hook(self, hook: ReplayHook) -> None:
        self._replay_hooks.append(hook)

    def consumers_for(self, event_type: str) -> list[ConsumerRegistration]:
        return [consumer for consumer in self._consumers.values() if consumer.accepts(event_type)]

    async def dispatch_unprocessed(
        self,
        session: Session,
        *,
        event_type: str | None = None,
        limit: int = 100,
    ) -> EventFanoutResponse:
        ensure_infra_schema(session)
        statement = select(DomainEvent).order_by(DomainEvent.created_at.asc())
        if event_type:
            statement = statement.where(DomainEvent.event_type == event_type)
        events = list(session.scalars(statement))
        outcomes: list[EventDispatchOutcome] = []
        dispatched = 0
        for event in events:
            if dispatched >= limit:
                break
            if not _has_pending_consumer_work(session, event, self.consumers_for(event.event_type)):
                continue
            outcomes.extend((await self.dispatch_event(session, event)).outcomes)
            dispatched += 1
        return EventFanoutResponse(dispatched=dispatched, outcomes=outcomes)

    async def dispatch_event(self, session: Session, event: DomainEvent) -> EventFanoutResponse:
        ensure_infra_schema(session)
        consumers = self.consumers_for(event.event_type)
        pending: list[tuple[ConsumerRegistration, InfraEventConsumerState]] = []
        outcomes: list[EventDispatchOutcome] = []

        for consumer in consumers:
            state = _consumer_state(session, event, consumer.name)
            if state and state.status == "succeeded":
                outcomes.append(
                    EventDispatchOutcome(
                        event_id=event.id,
                        consumer_name=consumer.name,
                        status="succeeded",
                        attempts=state.attempts,
                        idempotent_skip=True,
                    )
                )
                continue
            if state and state.status == "failed":
                outcomes.append(
                    EventDispatchOutcome(
                        event_id=event.id,
                        consumer_name=consumer.name,
                        status="failed",
                        attempts=state.attempts,
                        idempotent_skip=True,
                        error=state.last_error,
                    )
                )
                continue
            if state is None:
                state = InfraEventConsumerState(
                    consumer_name=consumer.name,
                    event_id=event.id,
                    event_type=event.event_type,
                    idempotency_key=_idempotency_key(event, consumer.name),
                )
            state.status = "running"
            state.attempts = (state.attempts or 0) + 1
            state.last_error = None
            session.add(state)
            pending.append((consumer, state))
        session.flush()

        results = await asyncio.gather(
            *(_invoke_consumer(consumer.handler, event) for consumer, _ in pending),
            return_exceptions=True,
        )
        now = datetime.now(timezone.utc)
        for (consumer, state), result in zip(pending, results, strict=True):
            if isinstance(result, Exception):
                state.status = "failed"
                state.last_error = str(result)
                session.add(
                    InfraDeadLetterRecord(
                        event_id=event.id,
                        consumer_name=consumer.name,
                        event_type=event.event_type,
                        aggregate_type=event.aggregate_type,
                        aggregate_id=event.aggregate_id,
                        payload=event.payload or {},
                        error=str(result),
                        attempts=state.attempts,
                        last_failed_at=now,
                        metadata_json={"idempotency_key": state.idempotency_key},
                    )
                )
                outcomes.append(
                    EventDispatchOutcome(
                        event_id=event.id,
                        consumer_name=consumer.name,
                        status="failed",
                        attempts=state.attempts,
                        error=str(result),
                    )
                )
            else:
                state.status = "succeeded"
                state.processed_at = now
                state.result_json = result or {}
                outcomes.append(
                    EventDispatchOutcome(
                        event_id=event.id,
                        consumer_name=consumer.name,
                        status="succeeded",
                        attempts=state.attempts,
                    )
                )
            session.add(state)
        session.flush()
        return EventFanoutResponse(dispatched=1, outcomes=outcomes)

    async def replay_dead_letters(
        self,
        session: Session,
        *,
        dead_letter_ids: list[str] | None = None,
        consumer_names: list[str] | None = None,
        limit: int = 50,
    ) -> ReplayResponse:
        ensure_infra_schema(session)
        statement = (
            select(InfraDeadLetterRecord)
            .where(InfraDeadLetterRecord.replay_status == "pending")
            .order_by(InfraDeadLetterRecord.created_at.asc())
            .limit(limit)
        )
        if dead_letter_ids:
            statement = statement.where(InfraDeadLetterRecord.id.in_(dead_letter_ids))
        if consumer_names:
            statement = statement.where(InfraDeadLetterRecord.consumer_name.in_(consumer_names))

        records = list(session.scalars(statement))
        outcomes: list[EventDispatchOutcome] = []
        replayed = 0
        failed = 0
        for record in records:
            event = session.get(DomainEvent, record.event_id)
            consumer = self._consumers.get(record.consumer_name)
            if event is None or consumer is None:
                record.error = "event or consumer is unavailable for replay"
                record.attempts += 1
                failed += 1
                for hook in self._replay_hooks:
                    hook(record, event, False)
                outcomes.append(
                    EventDispatchOutcome(
                        event_id=record.event_id,
                        consumer_name=record.consumer_name,
                        status="failed",
                        attempts=record.attempts,
                        error=record.error,
                    )
                )
                continue

            state = _consumer_state(session, event, consumer.name)
            if state is None:
                state = InfraEventConsumerState(
                    consumer_name=consumer.name,
                    event_id=event.id,
                    event_type=event.event_type,
                    idempotency_key=_idempotency_key(event, consumer.name),
                )
            state.status = "running"
            state.attempts = (state.attempts or 0) + 1
            session.add(state)
            session.flush()

            try:
                result = await _invoke_consumer(consumer.handler, event)
            except Exception as exc:  # pragma: no cover - covered by dispatch failure path
                record.attempts += 1
                record.error = str(exc)
                record.last_failed_at = datetime.now(timezone.utc)
                state.status = "failed"
                state.last_error = str(exc)
                failed += 1
                success = False
                outcomes.append(
                    EventDispatchOutcome(
                        event_id=event.id,
                        consumer_name=consumer.name,
                        status="failed",
                        attempts=state.attempts,
                        error=str(exc),
                    )
                )
            else:
                state.status = "succeeded"
                state.processed_at = datetime.now(timezone.utc)
                state.result_json = result or {}
                record.replay_status = "replayed"
                record.replayed_at = state.processed_at
                replayed += 1
                success = True
                outcomes.append(
                    EventDispatchOutcome(
                        event_id=event.id,
                        consumer_name=consumer.name,
                        status="succeeded",
                        attempts=state.attempts,
                    )
                )
            session.add_all([record, state])
            for hook in self._replay_hooks:
                hook(record, event, success)
        session.flush()
        return ReplayResponse(attempted=len(records), replayed=replayed, failed=failed, outcomes=outcomes)

    def list_dead_letters(
        self,
        session: Session,
        *,
        replay_status: str | None = "pending",
        limit: int = 100,
    ) -> list[DeadLetterRead]:
        ensure_infra_schema(session)
        statement = select(InfraDeadLetterRecord).order_by(InfraDeadLetterRecord.created_at.desc()).limit(limit)
        if replay_status:
            statement = statement.where(InfraDeadLetterRecord.replay_status == replay_status)
        return [DeadLetterRead.model_validate(item) for item in session.scalars(statement)]


async def _invoke_consumer(handler: ConsumerHandler, event: DomainEvent) -> dict[str, Any] | None:
    result = handler(event)
    if inspect.isawaitable(result):
        return await result
    return result


def _consumer_state(session: Session, event: DomainEvent, consumer_name: str) -> InfraEventConsumerState | None:
    return session.scalar(
        select(InfraEventConsumerState).where(
            InfraEventConsumerState.consumer_name == consumer_name,
            InfraEventConsumerState.idempotency_key == _idempotency_key(event, consumer_name),
        )
    )


def _has_pending_consumer_work(
    session: Session,
    event: DomainEvent,
    consumers: list[ConsumerRegistration],
) -> bool:
    if not consumers:
        return False
    for consumer in consumers:
        state = _consumer_state(session, event, consumer.name)
        if state is None or state.status not in {"succeeded", "failed"}:
            return True
    return False


def _idempotency_key(event: DomainEvent, consumer_name: str) -> str:
    payload_key = (event.payload or {}).get("idempotency_key")
    return f"{consumer_name}:{payload_key or event.id}"


GLOBAL_EVENT_BUS = InProcessEventBus()


def register_default_consumers() -> None:
    """Register prototype consumers once; real Kafka consumers can keep these names/contracts."""

    def search_index_projector(event: DomainEvent) -> dict[str, Any]:
        return {
            "derived_store": "search_index_documents",
            "source_event_type": event.event_type,
            "rebuildable": True,
        }

    def graph_read_model_projector(event: DomainEvent) -> dict[str, Any]:
        return {
            "derived_store": "graph_read_model",
            "source_event_type": event.event_type,
            "rebuildable": True,
        }

    def ops_audit_projector(event: DomainEvent) -> dict[str, Any]:
        return {
            "observed_aggregate": event.aggregate_type,
            "observed_event_type": event.event_type,
        }

    GLOBAL_EVENT_BUS.register(
        "search-index-projector",
        {"node_created", "node_embedded", "media_uploaded", "provenance_snapshot_assembled"},
        search_index_projector,
    )
    GLOBAL_EVENT_BUS.register(
        "graph-read-model-projector",
        {"node_created", "edge_created", "follow_created", "friendship_accepted", "moderation_enforcement_updated"},
        graph_read_model_projector,
    )
    GLOBAL_EVENT_BUS.register("ops-audit-projector", {"*"}, ops_audit_projector)
