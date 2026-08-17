from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.graph import GraphResponse, GraphSearchResponse
from app.services.graph_service import build_graph_response, search_graph

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/graph", response_model=GraphResponse)
def get_graph(
    social: bool = False,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> GraphResponse:
    return build_graph_response(session, current_user_id, social=social)


@router.get("/graph/search", response_model=GraphSearchResponse)
def search_graph_route(
    q: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> GraphSearchResponse:
    return search_graph(session, current_user_id, q)
