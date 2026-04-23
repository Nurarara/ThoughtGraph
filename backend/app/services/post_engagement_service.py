from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.post_comment import PostComment
from app.models.post_reaction import PostReaction
from app.models.user import User
from app.schemas.post_engagement import (
    CommentListResponse,
    CommentRead,
    PostEngagementSummary,
    ReactionToggleResponse,
)
from app.services.notification_service import create_notification
from app.services.post_service import can_view_post


def _count_reactions(session: Session, post_id: str) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(PostReaction).where(PostReaction.post_id == post_id)
        )
        or 0
    )


def _count_comments(session: Session, post_id: str) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(PostComment).where(PostComment.post_id == post_id)
        )
        or 0
    )


def viewer_liked(session: Session, post_id: str, user_id: str) -> bool:
    return session.scalar(
        select(PostReaction.id).where(
            PostReaction.post_id == post_id, PostReaction.user_id == user_id
        )
    ) is not None


def engagement_for_posts(
    session: Session, post_ids: list[str], viewer_id: str
) -> dict[str, PostEngagementSummary]:
    if not post_ids:
        return {}
    reaction_rows = session.execute(
        select(PostReaction.post_id, func.count())
        .where(PostReaction.post_id.in_(post_ids))
        .group_by(PostReaction.post_id)
    ).all()
    reaction_counts = {post_id: int(count) for post_id, count in reaction_rows}
    comment_rows = session.execute(
        select(PostComment.post_id, func.count())
        .where(PostComment.post_id.in_(post_ids))
        .group_by(PostComment.post_id)
    ).all()
    comment_counts = {post_id: int(count) for post_id, count in comment_rows}
    viewer_rows = set(
        session.scalars(
            select(PostReaction.post_id).where(
                PostReaction.post_id.in_(post_ids), PostReaction.user_id == viewer_id
            )
        )
    )
    return {
        post_id: PostEngagementSummary(
            post_id=post_id,
            reaction_count=reaction_counts.get(post_id, 0),
            viewer_liked=post_id in viewer_rows,
            comment_count=comment_counts.get(post_id, 0),
        )
        for post_id in post_ids
    }


def toggle_reaction(session: Session, user_id: str, post_id: str) -> ReactionToggleResponse:
    post = session.get(Post, post_id)
    if post is None or not can_view_post(session, user_id, post):
        raise ValueError("post not found")
    existing = session.scalar(
        select(PostReaction).where(PostReaction.post_id == post_id, PostReaction.user_id == user_id)
    )
    liked: bool
    if existing is not None:
        session.execute(
            delete(PostReaction).where(
                PostReaction.post_id == post_id, PostReaction.user_id == user_id
            )
        )
        liked = False
    else:
        session.add(PostReaction(post_id=post_id, user_id=user_id))
        liked = True
    session.commit()
    if liked and post.user_id != user_id:
        create_notification(
            session,
            user_id=post.user_id,
            notification_type="post_reaction",
            actor_id=user_id,
            content=post_id,
        )
    return ReactionToggleResponse(
        post_id=post_id,
        liked=liked,
        reaction_count=_count_reactions(session, post_id),
    )


def add_comment(session: Session, user_id: str, post_id: str, content: str) -> CommentRead:
    post = session.get(Post, post_id)
    if post is None or not can_view_post(session, user_id, post):
        raise ValueError("post not found")
    comment = PostComment(post_id=post_id, user_id=user_id, content=content.strip())
    session.add(comment)
    session.commit()
    session.refresh(comment)
    if post.user_id != user_id:
        create_notification(
            session,
            user_id=post.user_id,
            notification_type="post_comment",
            actor_id=user_id,
            content=post_id,
        )
    author = session.get(User, user_id)
    return CommentRead(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        display_name=author.display_name if author else user_id,
        content=comment.content,
        created_at=comment.created_at,
    )


def list_comments(session: Session, post_id: str, user_id: str) -> CommentListResponse:
    post = session.get(Post, post_id)
    if post is None or not can_view_post(session, user_id, post):
        raise ValueError("post not found")
    rows = list(
        session.scalars(
            select(PostComment)
            .where(PostComment.post_id == post_id)
            .order_by(PostComment.created_at.asc())
        )
    )
    user_ids = {row.user_id for row in rows}
    users = {u.id: u.display_name for u in session.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    return CommentListResponse(
        post_id=post_id,
        comments=[
            CommentRead(
                id=row.id,
                post_id=row.post_id,
                user_id=row.user_id,
                display_name=users.get(row.user_id, row.user_id),
                content=row.content,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


def delete_comment(session: Session, user_id: str, comment_id: str) -> bool:
    comment = session.get(PostComment, comment_id)
    if comment is None or comment.user_id != user_id:
        return False
    session.delete(comment)
    session.commit()
    return True
