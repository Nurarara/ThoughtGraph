from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.infra_read_models import (
    GraphProjectionRun,
    GraphReadModelEdge,
    GraphReadModelNode,
    InfraDeadLetterRecord,
    InfraEventConsumerState,
    SearchIndexDocument,
)


INFRA_TABLES = (
    InfraEventConsumerState.__table__,
    InfraDeadLetterRecord.__table__,
    SearchIndexDocument.__table__,
    GraphReadModelNode.__table__,
    GraphReadModelEdge.__table__,
    GraphProjectionRun.__table__,
)


def ensure_infra_schema(session: Session) -> None:
    """Create prototype-owned infra tables when the app router has not imported them yet."""
    bind = session.get_bind()
    for table in INFRA_TABLES:
        table.create(bind=bind, checkfirst=True)
