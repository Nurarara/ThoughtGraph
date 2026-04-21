from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead


PUSH_PREF_KEYS = {
    "new_follower": "push_new_follower",
    "reply": "push_replies",
    "influence_milestone": "push_influence_updates",
    "weekly_report": "push_weekly_report",
}


def _can_deliver_notification(user: User | None, notification_type: str) -> bool:
    if not user:
        return False
    preference_key = PUSH_PREF_KEYS.get(notification_type)
    if not preference_key:
        return True
    return user.notification_prefs.get(preference_key, True)


def create_notification(
    session: Session,
    user_id: str,
    notification_type: str,
    *,
    actor_id: str | None = None,
    thought_id: str | None = None,
    content: str = "",
) -> Notification:
    user = session.get(User, user_id)
    if not _can_deliver_notification(user, notification_type):
        return Notification(
            id="suppressed",
            user_id=user_id,
            type=notification_type,
            actor_id=actor_id,
            thought_id=thought_id,
            content=content,
            read=True,
        )
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        actor_id=actor_id,
        thought_id=thought_id,
        content=content,
    )
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


def list_notifications(session: Session, user_id: str) -> list[NotificationRead]:
    actor_map = {user.id: user.display_name for user in session.scalars(select(User))}
    notifications = list(
        session.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
    )
    return [
        NotificationRead(
            id=notification.id,
            type=notification.type,
            actor_id=notification.actor_id,
            actor_display_name=actor_map.get(notification.actor_id) if notification.actor_id else None,
            thought_id=notification.thought_id,
            content=notification.content,
            read=notification.read,
            created_at=notification.created_at,
        )
        for notification in notifications
    ]


def mark_notification_read(session: Session, user_id: str, notification_id: str, read: bool) -> NotificationRead | None:
    notification = session.scalar(
        select(Notification).where(Notification.user_id == user_id, Notification.id == notification_id)
    )
    if not notification:
        return None
    notification.read = read
    session.add(notification)
    session.commit()
    session.refresh(notification)
    actor_name = session.get(User, notification.actor_id).display_name if notification.actor_id and session.get(User, notification.actor_id) else None
    return NotificationRead(
        id=notification.id,
        type=notification.type,
        actor_id=notification.actor_id,
        actor_display_name=actor_name,
        thought_id=notification.thought_id,
        content=notification.content,
        read=notification.read,
        created_at=notification.created_at,
    )
