from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from mimetypes import guess_type

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.media_asset import MediaAsset
from app.models.workflow_job import WorkflowJob
from app.schemas.media import MediaAssetRead, MediaRenditionRead, MediaUploadCreate, MediaUploadCreateResponse, MediaUploadTarget
from app.schemas.node import MediaInput
from app.services.media_pipeline_service import moderate_media_asset, process_media_asset
from app.services.event_service import emit_event
from app.services.storage_service import storage_path, write_bytes
from app.services.workflow_service import enqueue_job, should_run_inline


def register_external_media(session: Session, user_id: str, media: MediaInput) -> MediaAsset:
    asset = MediaAsset(
        user_id=user_id,
        kind="image",
        source_kind="external",
        filename=getattr(media, "filename", None),
        original_url=str(media.url),
        mime_type=media.mime_type,
        size_bytes=media.size_bytes,
        width=media.width,
        height=media.height,
        moderation_status="unreviewed",
        status="ready",
        metadata_json={"renditions": []},
    )
    session.add(asset)
    session.flush()
    emit_event(
        session,
        event_type="media_registered",
        aggregate_type="media_asset",
        aggregate_id=asset.id,
        actor_id=user_id,
        payload={
            "kind": asset.kind,
            "url": asset.original_url,
            "mime_type": asset.mime_type,
        },
    )
    return asset


def create_upload(session: Session, user_id: str, payload: MediaUploadCreate) -> MediaUploadCreateResponse:
    settings = get_settings()
    max_size = max_upload_bytes(payload.kind)
    if payload.size_bytes > max_size:
        raise ValueError(f"{payload.kind} uploads are limited to {max_size} bytes")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.media_upload_url_ttl_seconds)
    token = secrets.token_urlsafe(24)
    suffix = _suffix_for_filename(payload.filename, payload.mime_type)
    storage_key = f"media/{user_id}/{secrets.token_hex(8)}-source{suffix}"
    asset = MediaAsset(
        user_id=user_id,
        kind=payload.kind,
        source_kind="upload",
        filename=payload.filename,
        storage_key=storage_key,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        status="awaiting_upload",
        moderation_status="pending",
        upload_token=token,
        upload_expires_at=expires_at,
        metadata_json={"renditions": []},
    )
    session.add(asset)
    session.flush()
    emit_event(
        session,
        event_type="media_upload_initiated",
        aggregate_type="media_asset",
        aggregate_id=asset.id,
        actor_id=user_id,
        payload={"kind": asset.kind, "filename": asset.filename, "mime_type": asset.mime_type},
    )
    session.commit()
    return MediaUploadCreateResponse(
        asset=to_media_asset_read(asset),
        upload=MediaUploadTarget(
            upload_url=f"/api/media/uploads/{asset.id}/content?token={token}",
            expires_at=expires_at,
        ),
    )


def accept_upload_content(
    session: Session,
    user_id: str,
    asset_id: str,
    token: str,
    *,
    content: bytes,
    content_type: str | None = None,
    filename: str | None = None,
) -> MediaAssetRead:
    asset = session.get(MediaAsset, asset_id)
    if asset is None or asset.user_id != user_id:
        raise ValueError("media asset not found")
    if asset.upload_token != token:
        raise ValueError("invalid upload token")
    if asset.upload_expires_at and asset.upload_expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise ValueError("upload token expired")
    if asset.status not in {"awaiting_upload", "failed"}:
        raise ValueError("media asset is not accepting uploads")

    if not content:
        raise ValueError("uploaded file is empty")
    max_size = max_upload_bytes(asset.kind)
    if len(content) > max_size:
        raise ValueError(f"{asset.kind} uploads are limited to {max_size} bytes")

    write_bytes(asset.storage_key or f"media/{user_id}/{asset.id}", content)
    asset.size_bytes = len(content)
    asset.filename = filename or asset.filename
    asset.mime_type = asset.mime_type or content_type or guess_type(asset.filename or "")[0]
    asset.status = "uploaded"
    asset.original_url = None
    asset.error_message = None
    asset.upload_token = None
    asset.metadata_json = {
        **(asset.metadata_json or {}),
        "original_filename": asset.filename,
    }
    session.add(asset)
    emit_event(
        session,
        event_type="media_uploaded",
        aggregate_type="media_asset",
        aggregate_id=asset.id,
        actor_id=user_id,
        payload={"kind": asset.kind, "size_bytes": asset.size_bytes, "mime_type": asset.mime_type},
    )
    moderation_job = enqueue_job(
        session,
        job_type="media_moderation",
        aggregate_type="media_asset",
        aggregate_id=asset.id,
        payload={"user_id": user_id},
        actor_id=user_id,
    )
    process_job = enqueue_job(
        session,
        job_type="media_processing",
        aggregate_type="media_asset",
        aggregate_id=asset.id,
        payload={"user_id": user_id},
        actor_id=user_id,
    )
    session.commit()

    if should_run_inline():
        _run_inline_media_jobs(session, moderation_job_id=moderation_job.id, process_job_id=process_job.id)
        session.expire(asset)

    refreshed = session.get(MediaAsset, asset.id)
    assert refreshed is not None
    return to_media_asset_read(refreshed)


def max_upload_bytes(kind: str) -> int:
    settings = get_settings()
    return settings.max_video_upload_bytes if kind == "video" else settings.max_image_upload_bytes


def retry_processing(session: Session, user_id: str, asset_id: str) -> MediaAssetRead:
    asset = session.get(MediaAsset, asset_id)
    if asset is None or asset.user_id != user_id:
        raise ValueError("media asset not found")
    if asset.status not in {"failed", "uploaded"}:
        raise ValueError("media asset is not in a retryable state")
    if not asset.storage_key or not storage_path(asset.storage_key).exists():
        raise ValueError("uploaded source is missing")

    process_job = enqueue_job(
        session,
        job_type="media_processing",
        aggregate_type="media_asset",
        aggregate_id=asset.id,
        payload={"user_id": user_id, "retry": True},
        actor_id=user_id,
    )
    session.commit()
    if should_run_inline():
        _run_inline_media_jobs(session, process_job_id=process_job.id)
        session.expire(asset)
    refreshed = session.get(MediaAsset, asset.id)
    assert refreshed is not None
    return to_media_asset_read(refreshed)


def get_media_asset(session: Session, asset_id: str) -> MediaAssetRead:
    asset = session.get(MediaAsset, asset_id)
    if asset is None:
        raise ValueError("media asset not found")
    return to_media_asset_read(asset)


def to_media_asset_read(asset: MediaAsset) -> MediaAssetRead:
    renditions = []
    for rendition in (asset.metadata_json or {}).get("renditions", []):
        storage_key = rendition.get("storage_key")
        if not storage_key:
            continue
        renditions.append(
            MediaRenditionRead(
                label=rendition.get("label", "derived"),
                mime_type=rendition.get("mime_type"),
                width=rendition.get("width"),
                height=rendition.get("height"),
                duration_seconds=rendition.get("duration_seconds"),
                url=f"/api/media/assets/{asset.id}/files/{rendition.get('label', 'derived')}",
                size_bytes=rendition.get("size_bytes"),
            )
        )

    return MediaAssetRead(
        id=asset.id,
        kind=asset.kind,
        source_kind=asset.source_kind,
        filename=asset.filename,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        width=asset.width,
        height=asset.height,
        duration_seconds=asset.duration_seconds,
        status=asset.status,
        moderation_status=asset.moderation_status,
        original_url=asset.original_url or (f"/api/media/assets/{asset.id}/files/original" if asset.storage_key else None),
        playback_url=f"/api/media/assets/{asset.id}/playback" if asset.playback_storage_key else None,
        thumbnail_url=f"/api/media/assets/{asset.id}/thumbnail" if asset.thumbnail_storage_key else None,
        renditions=renditions,
        error_message=asset.error_message,
        metadata_json=asset.metadata_json or {},
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def file_storage_key_for(asset: MediaAsset, variant: str) -> str | None:
    if variant == "playback":
        return asset.playback_storage_key
    if variant == "thumbnail":
        return asset.thumbnail_storage_key
    if variant == "original":
        return asset.playback_storage_key or asset.storage_key
    for rendition in (asset.metadata_json or {}).get("renditions", []):
        if rendition.get("label") == variant:
            return rendition.get("storage_key")
    return None


def _run_inline_media_jobs(
    session: Session,
    *,
    moderation_job_id: str | None = None,
    process_job_id: str | None = None,
) -> None:
    inline_session_factory = sessionmaker(bind=session.get_bind(), autoflush=False, autocommit=False, future=True)
    inline_session = inline_session_factory()
    try:
        if moderation_job_id:
            moderation_job = inline_session.get(WorkflowJob, moderation_job_id)
            if moderation_job is None:
                raise ValueError("media moderation job not found")
            moderate_media_asset(inline_session, moderation_job)
        if process_job_id:
            process_job = inline_session.get(WorkflowJob, process_job_id)
            if process_job is None:
                raise ValueError("media processing job not found")
            try:
                process_media_asset(inline_session, process_job)
            except Exception:
                inline_session.rollback()
                failed_asset = inline_session.get(MediaAsset, process_job.aggregate_id)
                if failed_asset is None or failed_asset.status != "failed":
                    raise
    finally:
        inline_session.close()


def _suffix_for_filename(filename: str, mime_type: str) -> str:
    if "." in filename:
        return "." + filename.rsplit(".", 1)[1].lower()
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
    }.get(mime_type, ".bin")
