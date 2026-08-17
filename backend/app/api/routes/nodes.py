from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.node import NodeCreate, NodeListResponse, NodeRead, NodeThreadResponse
from app.services.node_service import create_node, get_node, get_thread, list_nodes

router = APIRouter(prefix="/nodes")


@router.post("", response_model=NodeRead)
def create_node_route(
    payload: NodeCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> NodeRead:
    try:
        return create_node(session, current_user_id, payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("", response_model=NodeListResponse)
def list_nodes_route(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> NodeListResponse:
    return NodeListResponse(items=list_nodes(session, current_user_id))


@router.get("/{node_id}", response_model=NodeRead)
def get_node_route(
    node_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> NodeRead:
    try:
        return get_node(session, current_user_id, node_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.get("/{node_id}/thread", response_model=NodeThreadResponse)
def get_thread_route(
    node_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> NodeThreadResponse:
    try:
        return NodeThreadResponse(**get_thread(session, current_user_id, node_id))
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
