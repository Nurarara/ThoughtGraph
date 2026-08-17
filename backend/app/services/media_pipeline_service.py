from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.models.media_asset import MediaAsset
from app.models.workflow_job import WorkflowJob
from app.services.event_service import emit_event
from app.services.storage_service import copy_storage_object, storage_path, write_bytes
from app.services.workflow_service import complete_job, fail_job, start_job


def process_media_asset(session: Session, job: WorkflowJob) -> None:
    start_job(session, job)
    asset = session.get(MediaAsset, job.aggregate_id)
    if asset is None:
        fail_job(session, job, "media asset not found")
        session.commit()
        return
    if not asset.storage_key:
        fail_job(session, job, "media asset has no uploaded source")
        session.commit()
        return

    asset.status = "processing"
    session.add(asset)
    emit_event(
        session,
        event_type="media_processing_started",
        aggregate_type="media_asset",
        aggregate_id=asset.id,
        actor_id=asset.user_id,
        payload={"kind": asset.kind},
    )
    session.flush()

    try:
        if asset.kind == "image":
            _process_image_asset(asset)
        elif asset.kind == "video":
            _process_video_asset(asset)
        else:
            raise ValueError(f"unsupported media kind: {asset.kind}")

        asset.status = "ready"
        asset.error_message = None
        asset.metadata_json = {
            **(asset.metadata_json or {}),
            "ready_at": datetime.now(timezone.utc).isoformat(),
        }
        session.add(asset)
        emit_event(
            session,
            event_type="media_processed",
            aggregate_type="media_asset",
            aggregate_id=asset.id,
            actor_id=asset.user_id,
            payload={
                "kind": asset.kind,
                "playback_storage_key": asset.playback_storage_key,
                "thumbnail_storage_key": asset.thumbnail_storage_key,
            },
        )
        complete_job(session, job, {"asset_id": asset.id, "status": asset.status})
        session.commit()
    except Exception as exc:  # pragma: no cover - defensive workflow state
        asset.status = "failed"
        asset.error_message = str(exc)
        session.add(asset)
        emit_event(
            session,
            event_type="media_processing_failed",
            aggregate_type="media_asset",
            aggregate_id=asset.id,
            actor_id=asset.user_id,
            payload={"error": str(exc), "kind": asset.kind},
        )
        fail_job(session, job, str(exc))
        session.commit()
        raise


def moderate_media_asset(session: Session, job: WorkflowJob) -> None:
    start_job(session, job)
    asset = session.get(MediaAsset, job.aggregate_id)
    if asset is None:
        fail_job(session, job, "media asset not found")
        session.commit()
        return

    # The local prototype has no real classifier or human review integration.
    # Completing this job records that moderation was deferred; it must not
    # manufacture an approval decision.
    asset.moderation_status = "unreviewed"
    session.add(asset)
    emit_event(
        session,
        event_type="media_moderation_deferred",
        aggregate_type="media_asset",
        aggregate_id=asset.id,
        actor_id=asset.user_id,
        payload={
            "status": asset.moderation_status,
            "kind": asset.kind,
            "reason": "prototype moderation provider is not configured",
        },
    )
    complete_job(session, job, {"asset_id": asset.id, "moderation_status": asset.moderation_status})
    session.commit()


def _process_image_asset(asset: MediaAsset) -> None:
    source = storage_path(asset.storage_key)
    with Image.open(source) as image:
        image.load()
        asset.width, asset.height = image.size
        thumbnail = image.copy()
        thumbnail.thumbnail((960, 960))

        original_suffix = _suffix_for(asset.mime_type, asset.filename, default=".bin")
        thumb_suffix = ".png" if image.mode in {"RGBA", "LA", "P"} else ".jpg"
        asset.playback_storage_key = f"media/{asset.user_id}/{asset.id}/original{original_suffix}"
        asset.thumbnail_storage_key = f"media/{asset.user_id}/{asset.id}/thumbnail{thumb_suffix}"
        copy_storage_object(asset.storage_key, asset.playback_storage_key)

        buffer = BytesIO()
        if thumb_suffix == ".png":
            thumbnail.save(buffer, format="PNG", optimize=True)
            thumb_mime = "image/png"
        else:
            thumbnail = thumbnail.convert("RGB")
            thumbnail.save(buffer, format="JPEG", quality=86, optimize=True)
            thumb_mime = "image/jpeg"
        write_bytes(asset.thumbnail_storage_key, buffer.getvalue())

        asset.metadata_json = {
            **(asset.metadata_json or {}),
            "renditions": [
                {
                    "label": "original",
                    "mime_type": asset.mime_type,
                    "width": asset.width,
                    "height": asset.height,
                    "storage_key": asset.playback_storage_key,
                    "size_bytes": source.stat().st_size,
                },
                {
                    "label": "thumbnail",
                    "mime_type": thumb_mime,
                    "width": thumbnail.width,
                    "height": thumbnail.height,
                    "storage_key": asset.thumbnail_storage_key,
                    "size_bytes": len(buffer.getvalue()),
                },
            ],
            "processing_mode": "pillow",
        }
        asset.duration_seconds = None


def _process_video_asset(asset: MediaAsset) -> None:
    source = storage_path(asset.storage_key)
    suffix = _suffix_for(asset.mime_type, asset.filename, default=".mp4")
    asset.playback_storage_key = f"media/{asset.user_id}/{asset.id}/playback{suffix}"
    asset.thumbnail_storage_key = f"media/{asset.user_id}/{asset.id}/poster.svg"
    copy_storage_object(asset.storage_key, asset.playback_storage_key)
    poster = _video_poster_svg(asset)
    write_bytes(asset.thumbnail_storage_key, poster.encode("utf-8"))
    asset.metadata_json = {
        **(asset.metadata_json or {}),
        "renditions": [
            {
                "label": "playback",
                "mime_type": asset.mime_type,
                "storage_key": asset.playback_storage_key,
                "size_bytes": source.stat().st_size,
            },
            {
                "label": "poster",
                "mime_type": "image/svg+xml",
                "width": 1280,
                "height": 720,
                "storage_key": asset.thumbnail_storage_key,
                "size_bytes": len(poster.encode("utf-8")),
            },
        ],
        "processing_mode": "passthrough",
        "transcode_note": "ffmpeg not configured locally; serving original upload as playback rendition",
    }


def _video_poster_svg(asset: MediaAsset) -> str:
    title = escape(asset.filename or "Video asset")
    subtitle = escape((asset.metadata_json or {}).get("title_hint", "Playback preview"))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<defs>
  <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#13203b"/>
    <stop offset="100%" stop-color="#0a111d"/>
  </linearGradient>
</defs>
<rect width="1280" height="720" fill="url(#g)"/>
<circle cx="640" cy="360" r="112" fill="rgba(125,255,227,0.12)" stroke="rgba(125,255,227,0.46)" stroke-width="3"/>
<polygon points="610,305 610,415 705,360" fill="#7dffe3"/>
<text x="96" y="600" fill="#f4f7ff" font-size="42" font-family="Segoe UI, Arial, sans-serif">{title}</text>
<text x="96" y="648" fill="rgba(244,247,255,0.72)" font-size="26" font-family="Segoe UI, Arial, sans-serif">{subtitle}</text>
</svg>"""


def _suffix_for(mime_type: str | None, filename: str | None, default: str) -> str:
    if filename:
        suffix = Path(filename).suffix
        if suffix:
            return suffix.lower()
    mime_lookup = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
    }
    return mime_lookup.get(mime_type or "", default)
