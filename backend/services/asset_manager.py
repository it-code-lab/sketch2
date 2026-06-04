from __future__ import annotations

import hashlib
import io
import json
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

ASSET_DIR_NAME = "assets"
MANIFEST_NAME = "hand_assets_manifest.json"
ALLOWED_IMAGE_TYPES = {"image/png", "image/webp", "image/jpeg", "image/jpg"}
ALLOWED_VIDEO_TYPES = {"video/webm", "video/mp4", "video/quicktime", "video/x-matroska"}
ALLOWED_VIDEO_SUFFIXES = {".webm", ".mp4", ".mov", ".mkv"}


def ensure_asset_dir(root: Path) -> Path:
    path = root / ASSET_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    (path / ".gitkeep").touch(exist_ok=True)
    return path


def manifest_path(root: Path) -> Path:
    return ensure_asset_dir(root) / MANIFEST_NAME


def load_asset_manifest(root: Path) -> dict[str, Any]:
    path = manifest_path(root)
    if not path.exists():
        return {"assets": {}}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict) and isinstance(data.get('assets'), dict):
            return data
    except Exception:
        pass
    return {"assets": {}}


def save_asset_manifest(root: Path, manifest: dict[str, Any]) -> None:
    path = manifest_path(root)
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def update_asset_metadata(root: Path, filename: str, metadata: dict[str, Any]) -> None:
    manifest = load_asset_manifest(root)
    current = manifest.setdefault('assets', {}).get(filename, {})
    current.update(metadata)
    manifest['assets'][filename] = current
    save_asset_manifest(root, manifest)


def get_asset_metadata(root: Path, filename: str) -> dict[str, Any]:
    manifest = load_asset_manifest(root)
    return dict(manifest.get('assets', {}).get(filename, {}))


def resolve_hand_asset(root: Path, filename: str | None) -> str:
    if not filename:
        return ""
    path = ensure_asset_dir(root) / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Hand asset '{filename}' not found in library.")
    return str(path)


async def save_hand_asset(upload: UploadFile | None, root: Path) -> str:
    if upload is None or not upload.filename:
        return ""

    suffix = Path(upload.filename).suffix.lower()
    content_type = upload.content_type or ""
    data = await upload.read()
    asset_dir = ensure_asset_dir(root)
    digest = hashlib.sha1(data[:1024 * 1024]).hexdigest()[:10]
    safe_stem = Path(upload.filename).stem.replace(" ", "_")[:40] or "hand"

    if content_type in ALLOWED_VIDEO_TYPES or suffix in ALLOWED_VIDEO_SUFFIXES:
        if len(data) > 90 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Hand video asset is too large. Use a video under 90 MB.")
        if suffix not in ALLOWED_VIDEO_SUFFIXES:
            suffix = ".webm"
        filename = f"hand_video_{int(time.time())}_{digest}_{safe_stem}{suffix}"
        path = asset_dir / filename
        path.write_bytes(data)
        update_asset_metadata(root, filename, {
            'type': 'video', 'filename': filename, 'original_name': upload.filename, 'size_bytes': len(data), 'modified': int(time.time())
        })
        return str(path)

    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Hand asset must be PNG, WebP, JPEG, WebM, MP4, MOV, or MKV.")
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Hand image asset is too large. Use an image under 12 MB.")
    try:
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image).convert("RGBA")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read the hand asset image.") from exc

    max_side = 1200
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.LANCZOS)

    filename = f"hand_{int(time.time())}_{digest}_{safe_stem}.png"
    path = asset_dir / filename
    image.save(path)
    update_asset_metadata(root, filename, {
        'type': 'image', 'filename': filename, 'original_name': upload.filename, 'size_bytes': path.stat().st_size,
        'modified': int(time.time()), 'width': image.width, 'height': image.height,
    })
    return str(path)


def list_hand_assets(root: Path) -> list[dict[str, Any]]:
    asset_dir = ensure_asset_dir(root)
    manifest = load_asset_manifest(root).get('assets', {})
    assets = []
    patterns = ["hand_*.png", "hand_video_*.webm", "hand_video_*.mp4", "hand_video_*.mov", "hand_video_*.mkv"]
    paths = []
    for pattern in patterns:
        paths.extend(asset_dir.glob(pattern))
    for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
        meta = dict(manifest.get(path.name, {}))
        assets.append({
            "filename": path.name,
            "path": str(path),
            "type": "video" if path.name.startswith("hand_video_") else "image",
            "size_bytes": path.stat().st_size,
            "modified": int(path.stat().st_mtime),
            **meta,
        })
    return assets
