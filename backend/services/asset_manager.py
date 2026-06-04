from __future__ import annotations

import hashlib
import io
import time
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

ASSET_DIR_NAME = "assets"
ALLOWED_IMAGE_TYPES = {"image/png", "image/webp", "image/jpeg", "image/jpg"}


def ensure_asset_dir(root: Path) -> Path:
    path = root / ASSET_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    (path / ".gitkeep").touch(exist_ok=True)
    return path


async def save_hand_asset(upload: UploadFile | None, root: Path) -> str:
    """Validate and save a transparent hand/pen image asset. Returns absolute path or empty string."""
    if upload is None or not upload.filename:
        return ""
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Hand asset must be PNG, WebP, or JPEG.")
    data = await upload.read()
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Hand asset is too large. Use an image under 12 MB.")
    try:
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image).convert("RGBA")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read the hand asset image.") from exc

    # Trim extreme sizes so overlay rendering remains fast.
    max_side = 1200
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.LANCZOS)

    asset_dir = ensure_asset_dir(root)
    digest = hashlib.sha1(data[:1024 * 1024]).hexdigest()[:10]
    safe_stem = Path(upload.filename).stem.replace(" ", "_")[:40] or "hand"
    filename = f"hand_{int(time.time())}_{digest}_{safe_stem}.png"
    path = asset_dir / filename
    image.save(path)
    return str(path)


def list_hand_assets(root: Path) -> list[dict[str, str | int]]:
    asset_dir = ensure_asset_dir(root)
    assets = []
    for path in sorted(asset_dir.glob("hand_*.png"), key=lambda p: p.stat().st_mtime, reverse=True):
        assets.append({
            "filename": path.name,
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "modified": int(path.stat().st_mtime),
        })
    return assets
