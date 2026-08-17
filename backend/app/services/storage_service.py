from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


def storage_root() -> Path:
    root = Path(get_settings().media_storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_parent(storage_key: str) -> Path:
    path = storage_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def storage_path(storage_key: str) -> Path:
    root = storage_root()
    key = Path(storage_key)
    if not storage_key.strip() or key.is_absolute():
        raise ValueError("invalid storage key")

    candidate = (root / key).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as err:
        raise ValueError("storage key escapes storage root") from err
    if candidate == root:
        raise ValueError("invalid storage key")
    return candidate


def write_bytes(storage_key: str, content: bytes) -> Path:
    path = ensure_parent(storage_key)
    path.write_bytes(content)
    return path


def copy_storage_object(source_key: str, target_key: str) -> Path:
    source = storage_path(source_key)
    target = ensure_parent(target_key)
    target.write_bytes(source.read_bytes())
    return target


def exists(storage_key: str | None) -> bool:
    if not storage_key:
        return False
    return storage_path(storage_key).exists()
