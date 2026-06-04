from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps


def _extract_video_frame(video_path: Path, frame_offset: int = 0) -> Image.Image:
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        timestamp = max(0.0, frame_offset / 30.0)
        cmd = [
            'ffmpeg', '-y', '-ss', f'{timestamp:.3f}', '-i', str(video_path), '-frames:v', '1', str(tmp_path)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        image = Image.open(tmp_path)
        return ImageOps.exif_transpose(image).convert('RGBA')
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _load_image(path: Path) -> Image.Image:
    suffix = path.suffix.lower()
    if suffix in {'.webm', '.mp4', '.mov', '.mkv'}:
        return _extract_video_frame(path)
    image = Image.open(path)
    return ImageOps.exif_transpose(image).convert('RGBA')


def _choose_tip_from_rgba(rgba: np.ndarray, hand_side: str = 'right') -> tuple[float, float, dict[str, Any]]:
    h, w, _ = rgba.shape
    alpha = rgba[..., 3].astype(np.float32) / 255.0
    rgb = rgba[..., :3].astype(np.float32)
    gray = (rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114) / 255.0

    opaque = alpha > 0.08
    if not opaque.any():
        opaque = np.ones((h, w), dtype=bool)

    y_norm = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    x_norm = np.linspace(0, 1, w, dtype=np.float32)[None, :]

    # Heuristic: the pencil/pen tip tends to be dark, near the lower part of the hand asset,
    # and biased to the right for right-handed clips, or left for left-handed clips.
    darkness = 1.0 - gray
    x_pref = x_norm if hand_side != 'left' else (1.0 - x_norm)
    score = darkness * 0.62 + y_norm * 0.28 + x_pref * 0.10
    score = np.where(opaque, score, -1.0)

    # Focus lower portion to avoid the wrist/arm dominating.
    score[: max(1, int(h * 0.25)), :] *= 0.35
    # Ignore completely bright pixels.
    score = np.where(gray < 0.96, score, -1.0)

    yi, xi = np.unravel_index(int(np.argmax(score)), score.shape)
    confidence = float(max(0.05, min(0.99, score[yi, xi])))

    # Refine by taking a local dark cluster around the best point.
    y1, y2 = max(0, yi - 12), min(h, yi + 13)
    x1, x2 = max(0, xi - 12), min(w, xi + 13)
    local_dark = darkness[y1:y2, x1:x2]
    local_alpha = alpha[y1:y2, x1:x2] > 0.08
    mask = (local_dark > max(0.35, local_dark.max() * 0.72)) & local_alpha
    if mask.any():
        yy, xx = np.where(mask)
        yi = int(np.round(y1 + yy.mean()))
        xi = int(np.round(x1 + xx.mean()))

    tip_x = round((xi / max(1, w - 1)) * 100, 1)
    tip_y = round((yi / max(1, h - 1)) * 100, 1)
    debug = {
        'pixel_x': int(xi),
        'pixel_y': int(yi),
        'width': int(w),
        'height': int(h),
        'hand_side': hand_side,
    }
    return tip_x, tip_y, {'confidence': confidence, 'debug': debug}


def detect_tip_from_asset_path(asset_path: str | Path, hand_side: str = 'right') -> dict[str, Any]:
    path = Path(asset_path)
    image = _load_image(path)
    rgba = np.array(image.convert('RGBA'))
    tip_x, tip_y, meta = _choose_tip_from_rgba(rgba, hand_side=hand_side)
    return {
        'tip_x': tip_x,
        'tip_y': tip_y,
        'confidence': round(float(meta['confidence']), 3),
        'preview_size': {'width': image.width, 'height': image.height},
        'hand_side': hand_side,
        'debug': meta['debug'],
        'asset_name': path.name,
    }
