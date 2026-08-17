from __future__ import annotations

from mimetypes import guess_type

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models.content_node import ContentNode
from app.models.media_asset import MediaAsset
from app.schemas.media import MediaAssetRead, MediaUploadCreate, MediaUploadCreateResponse
from app.services.media_service import (
    accept_upload_content,
    create_upload,
    file_storage_key_for,
    get_media_asset,
    max_upload_bytes,
    retry_processing,
)
from app.services.social_service import can_view_node
from app.services.storage_service import storage_path

router = APIRouter(prefix="/media")


@router.post("/uploads", response_model=MediaUploadCreateResponse)
def create_upload_route(
    payload: MediaUploadCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> MediaUploadCreateResponse:
    try:
        return create_upload(session, current_user_id, payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.put("/uploads/{asset_id}/content", response_model=MediaAssetRead)
async def upload_content_route(
    asset_id: str,
    request: Request,
    token: str,
    x_upload_filename: str | None = Header(default=None, alias="X-Upload-Filename"),
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> MediaAssetRead:
    try:
        asset = session.get(MediaAsset, asset_id)
        if asset is None or asset.user_id != current_user_id:
            raise ValueError("media asset not found")
        max_size = max_upload_bytes(asset.kind)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError as err:
                raise ValueError("invalid Content-Length header") from err
            if declared_length > max_size:
                raise ValueError(f"{asset.kind} uploads are limited to {max_size} bytes")

        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > max_size:
                raise ValueError(f"{asset.kind} uploads are limited to {max_size} bytes")
            body.extend(chunk)
        return accept_upload_content(
            session,
            current_user_id,
            asset_id,
            token,
            content=bytes(body),
            content_type=request.headers.get("content-type"),
            filename=x_upload_filename,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/assets/{asset_id}", response_model=MediaAssetRead)
def get_media_asset_route(
    asset_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> MediaAssetRead:
    try:
        asset = session.get(MediaAsset, asset_id)
        if asset is None or not _can_view_asset(session, current_user_id, asset):
            raise ValueError("media asset not found")
        return get_media_asset(session, asset.id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.post("/assets/{asset_id}/retry", response_model=MediaAssetRead)
def retry_media_route(
    asset_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> MediaAssetRead:
    try:
        return retry_processing(session, current_user_id, asset_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/assets/{asset_id}/thumbnail")
def get_media_thumbnail(
    asset_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    return _serve_media_variant(session, current_user_id, asset_id, "thumbnail")


@router.get("/assets/{asset_id}/playback")
def get_media_playback(
    asset_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    return _serve_media_variant(session, current_user_id, asset_id, "playback")


@router.get("/assets/{asset_id}/files/{variant}")
def get_media_variant(
    asset_id: str,
    variant: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    return _serve_media_variant(session, current_user_id, asset_id, variant)


def _serve_media_variant(session: Session, viewer_id: str, asset_id: str, variant: str):
    asset = session.get(MediaAsset, asset_id)
    if asset is None or not _can_view_asset(session, viewer_id, asset):
        raise HTTPException(status_code=404, detail="media asset not found")
    storage_key = file_storage_key_for(asset, variant)
    if not storage_key:
        raise HTTPException(status_code=404, detail="media variant not found")
    path = storage_path(storage_key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="media file missing")
    media_type = _infer_media_type(asset, variant)
    return FileResponse(path, media_type=media_type, filename=asset.filename)


def _can_view_asset(session: Session, viewer_id: str, asset: MediaAsset) -> bool:
    if asset.user_id == viewer_id:
        return True
    nodes = session.scalars(select(ContentNode).where(ContentNode.media_asset_id == asset.id))
    return any(can_view_node(session, viewer_id, node) for node in nodes)


def _infer_media_type(asset: MediaAsset, variant: str) -> str | None:
    storage_key = file_storage_key_for(asset, variant)
    guessed, _ = guess_type(storage_key or "")
    return guessed or asset.mime_type
