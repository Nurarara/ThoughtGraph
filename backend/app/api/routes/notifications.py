from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.notification import NotificationRead, NotificationUpdate
from app.services.notification_service import list_notifications, mark_notification_read

router = APIRouter(prefix="/notifications")


@router.get("", response_model=list[NotificationRead])
def get_notifications(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> list[NotificationRead]:
    return list_notifications(session, current_user_id)


@router.patch("/{notification_id}", response_model=NotificationRead)
def update_notification(
    notification_id: str,
    payload: NotificationUpdate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> NotificationRead:
    notification = mark_notification_read(session, current_user_id, notification_id, payload.read)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification

