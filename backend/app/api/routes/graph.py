from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.graph import GraphResponse
from app.services.graph_pipeline import get_graph_response_with_options

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
    return get_graph_response_with_options(session, current_user_id, social=social)
