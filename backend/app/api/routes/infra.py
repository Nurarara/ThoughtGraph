from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, require_admin_user_id
from app.db.session import get_db
from app.schemas.infra import (
    DeadLetterRead,
    EventFanoutResponse,
    GraphProjectionResponse,
    GraphReadModelResponse,
    OpsStatusResponse,
    ReplayReadiness,
    ReplayRequest,
    ReplayResponse,
    SearchRebuildResponse,
    SearchResponse,
)
from app.services.graph_read_model import query_graph_read_model, rebuild_graph_read_model
from app.services.infra_event_bus import GLOBAL_EVENT_BUS
from app.services.ops_status import build_ops_status, build_replay_readiness
from app.services.search_read_model import hybrid_search, rebuild_search_index

router = APIRouter()


@router.post("/infra/events/dispatch", response_model=EventFanoutResponse)
async def dispatch_events(
    event_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db),
    _: str = Depends(require_admin_user_id),
) -> EventFanoutResponse:
    result = await GLOBAL_EVENT_BUS.dispatch_unprocessed(session, event_type=event_type, limit=limit)
    session.commit()
    return result


@router.get("/infra/dead-letters", response_model=list[DeadLetterRead])
def list_dead_letters(
    replay_status: str | None = "pending",
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db),
    _: str = Depends(require_admin_user_id),
) -> list[DeadLetterRead]:
    return GLOBAL_EVENT_BUS.list_dead_letters(session, replay_status=replay_status, limit=limit)


@router.post("/infra/dead-letters/replay", response_model=ReplayResponse)
async def replay_dead_letters(
    payload: ReplayRequest,
    session: Session = Depends(get_db),
    _: str = Depends(require_admin_user_id),
) -> ReplayResponse:
    result = await GLOBAL_EVENT_BUS.replay_dead_letters(
        session,
        dead_letter_ids=payload.dead_letter_ids,
        consumer_names=payload.consumer_names,
        limit=payload.limit,
    )
    session.commit()
    return result


@router.post("/infra/search/rebuild", response_model=SearchRebuildResponse)
def rebuild_search(
    all_users: bool = False,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
    admin_user_id: str | None = Depends(require_admin_user_id),
) -> SearchRebuildResponse:
    if all_users and admin_user_id is None:
        raise RuntimeError("unreachable")
    result = rebuild_search_index(session, user_id=None if all_users else current_user_id)
    session.commit()
    return result


@router.get("/infra/search", response_model=SearchResponse)
def search_index(
    q: str,
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SearchResponse:
    return hybrid_search(session, user_id=current_user_id, query=q, limit=limit)


@router.post("/infra/graph/rebuild", response_model=GraphProjectionResponse)
def rebuild_graph_projection(
    all_users: bool = False,
    reason: str = "manual",
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
    admin_user_id: str | None = Depends(require_admin_user_id),
) -> GraphProjectionResponse:
    if all_users and admin_user_id is None:
        raise RuntimeError("unreachable")
    result = rebuild_graph_read_model(session, user_id=None if all_users else current_user_id, reason=reason)
    session.commit()
    return result


@router.get("/infra/graph", response_model=GraphReadModelResponse)
def read_graph_projection(
    include_edges: bool = True,
    limit: int = Query(default=500, ge=1, le=2000),
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> GraphReadModelResponse:
    return query_graph_read_model(session, user_id=current_user_id, include_edges=include_edges, limit=limit)


@router.get("/infra/ops/status", response_model=OpsStatusResponse)
def ops_status(
    session: Session = Depends(get_db),
    _: str = Depends(require_admin_user_id),
) -> OpsStatusResponse:
    return build_ops_status(session, event_bus=GLOBAL_EVENT_BUS)


@router.get("/infra/ops/replay-readiness", response_model=ReplayReadiness)
def replay_readiness(
    session: Session = Depends(get_db),
    _: str = Depends(require_admin_user_id),
) -> ReplayReadiness:
    return build_replay_readiness(session, event_bus=GLOBAL_EVENT_BUS)
