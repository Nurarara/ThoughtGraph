from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.post import PostCreate, PostListResponse, PostRead
from app.schemas.post_engagement import (
    CommentCreate,
    CommentListResponse,
    CommentRead,
    ReactionToggleResponse,
)
from app.services.post_engagement_service import (
    add_comment,
    delete_comment,
    list_comments,
    toggle_reaction,
)
from app.services.post_service import create_post, delete_post, list_cluster_posts

router = APIRouter(prefix="/posts")


@router.post("/", response_model=PostRead)
def create(
    payload: PostCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> PostRead:
    return create_post(session, current_user_id, payload)


@router.get("/cluster/{cluster_key}", response_model=PostListResponse)
def cluster_feed(
    cluster_key: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> PostListResponse:
    if cluster_key not in {"technology", "growth", "purpose"}:
        raise HTTPException(status_code=404, detail="unknown cluster")
    return list_cluster_posts(session, current_user_id, cluster_key)


@router.delete("/{post_id}")
def remove(
    post_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, bool]:
    ok = delete_post(session, current_user_id, post_id)
    if not ok:
        raise HTTPException(status_code=404, detail="post not found")
    return {"deleted": True}


@router.post("/{post_id}/react", response_model=ReactionToggleResponse)
def react(
    post_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> ReactionToggleResponse:
    try:
        return toggle_reaction(session, current_user_id, post_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.get("/{post_id}/comments", response_model=CommentListResponse)
def comments(
    post_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> CommentListResponse:
    try:
        return list_comments(session, post_id, current_user_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.post("/{post_id}/comments", response_model=CommentRead)
def add_comment_route(
    post_id: str,
    payload: CommentCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> CommentRead:
    try:
        return add_comment(session, current_user_id, post_id, payload.content)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.delete("/comments/{comment_id}")
def remove_comment(
    comment_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, bool]:
    ok = delete_comment(session, current_user_id, comment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="comment not found")
    return {"deleted": True}
