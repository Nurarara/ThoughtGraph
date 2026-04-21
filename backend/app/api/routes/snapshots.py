from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.snapshot import SnapshotCreate, SnapshotRead
from app.services.broadcast import manager
from app.services.snapshot_service import (
    create_snapshot,
    delete_snapshot,
    get_snapshot,
    list_recent_public_snapshots,
    list_snapshots,
)

router = APIRouter(prefix="/snapshots")


@router.post("", response_model=SnapshotRead)
async def create_snapshot_route(
    payload: SnapshotCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SnapshotRead:
    snapshot = create_snapshot(session, current_user_id, payload.caption, payload.is_public)
    await manager.send_to_user(
        current_user_id,
        {"type": "snapshot_ready", "snapshot_id": snapshot.id, "image_url": snapshot.image_url},
    )
    return snapshot


@router.get("", response_model=list[SnapshotRead])
def list_snapshots_route(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> list[SnapshotRead]:
    return list_snapshots(session, current_user_id)


@router.get("/recent/public", response_model=list[SnapshotRead])
def list_recent_public_snapshots_route(session: Session = Depends(get_db)) -> list[SnapshotRead]:
    return list_recent_public_snapshots(session)


@router.get("/{snapshot_id}", response_model=SnapshotRead)
def get_snapshot_route(
    snapshot_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> SnapshotRead:
    snapshot = get_snapshot(session, snapshot_id, current_user_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.get("/public/{snapshot_id}", response_model=SnapshotRead)
def get_public_snapshot_route(
    snapshot_id: str,
    session: Session = Depends(get_db),
) -> SnapshotRead:
    snapshot = get_snapshot(session, snapshot_id, None)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.delete("/{snapshot_id}")
def delete_snapshot_route(
    snapshot_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, bool]:
    deleted = delete_snapshot(session, current_user_id, snapshot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"deleted": True}
