from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostCreate, PostListResponse, PostRead
from app.schemas.post_engagement import PostEngagementSummary
from app.services.friendship_service import accepted_friend_ids


def _to_read(
    session: Session,
    post: Post,
    engagement: PostEngagementSummary | None = None,
) -> PostRead:
    author = session.get(User, post.user_id)
    display_name = author.display_name if author else post.user_id
    return PostRead(
        id=post.id,
        user_id=post.user_id,
        display_name=display_name,
        cluster_key=post.cluster_key,
        caption=post.caption,
        media_url=post.media_url,
        location=post.location,
        visibility=post.visibility,
        created_at=post.created_at,
        reaction_count=engagement.reaction_count if engagement else 0,
        viewer_liked=engagement.viewer_liked if engagement else False,
        comment_count=engagement.comment_count if engagement else 0,
    )


def create_post(session: Session, user_id: str, payload: PostCreate) -> PostRead:
    post = Post(
        user_id=user_id,
        cluster_key=payload.cluster_key,
        caption=payload.caption,
        media_url=payload.media_url,
        location=payload.location,
        visibility=payload.visibility,
    )
    session.add(post)
    session.commit()
    session.refresh(post)
    return _to_read(session, post)


def can_view_post(session: Session, current_user_id: str, post: Post) -> bool:
    if post.visibility == "public":
        return True
    if post.user_id == current_user_id:
        return True
    if post.visibility == "friends":
        return post.user_id in set(accepted_friend_ids(session, current_user_id))
    return False


def list_cluster_posts(session: Session, current_user_id: str, cluster_key: str) -> PostListResponse:
    from app.services.post_engagement_service import engagement_for_posts

    stmt = select(Post).where(Post.cluster_key == cluster_key).order_by(Post.created_at.desc()).limit(60)
    rows = session.scalars(stmt).all()
    visible_posts = [post for post in rows if can_view_post(session, current_user_id, post)]
    engagement = engagement_for_posts(
        session, [p.id for p in visible_posts], current_user_id
    )
    return PostListResponse(
        cluster_key=cluster_key,
        posts=[_to_read(session, post, engagement.get(post.id)) for post in visible_posts],
    )


def delete_post(session: Session, current_user_id: str, post_id: str) -> bool:
    post = session.get(Post, post_id)
    if post is None or post.user_id != current_user_id:
        return False
    session.delete(post)
    session.commit()
    return True


def list_friend_post_clusters(session: Session, current_user_id: str) -> dict[str, set[str]]:
    friend_ids = accepted_friend_ids(session, current_user_id)
    if not friend_ids:
        return {}
    rows = session.execute(
        select(Post.user_id, Post.cluster_key).where(
            Post.user_id.in_(friend_ids),
            or_(Post.visibility == "public", Post.visibility == "friends"),
        )
    ).all()
    result: dict[str, set[str]] = {}
    for user_id, cluster_key in rows:
        result.setdefault(user_id, set()).add(cluster_key)
    return result
