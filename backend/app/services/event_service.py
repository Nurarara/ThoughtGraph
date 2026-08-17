from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.domain_event import DomainEvent


def emit_event(
    session: Session,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    actor_id: str | None,
    payload: dict,
) -> DomainEvent:
    event = DomainEvent(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        actor_id=actor_id,
        payload=payload,
    )
    session.add(event)
    session.flush()
    return event
