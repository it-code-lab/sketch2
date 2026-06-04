from __future__ import annotations

import json
import math
import os
import random
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from backend.models import RenderSettings, Stroke, StrokePlan
from backend.services.audio import generate_pencil_audio

STYLE_COLORS = {
    "pencil": (34, 32, 29),
    "charcoal": (24, 22, 20),
    "ink": (12, 12, 12),
    "marker": (20, 20, 20),
}

PAPER_BASE = (242, 235, 219)


def render_plan_to_mp4(
    plan: StrokePlan,
    source_image: Image.Image,
    sketch_preview: Image.Image,
    settings: RenderSettings,
    output_dir: Path,
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, str | int | float | list[str]]:
    """Render a stroke plan to an MP4 file via FFmpeg."""
    def progress(value: float, message: str) -> None:
        if progress_callback:
            progress_callback(value, message)

    progress(2, "Preparing render folders")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time() * 1000)
    job_id = f"sketch_{timestamp}_{settings.seed}"
    frames_dir = output_dir / f"{job_id}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = output_dir / f"{job_id}.mp4"
    plan_path = output_dir / f"{job_id}_plan.json"
    preview_path = output_dir / f"{job_id}_sketch.png"
    audio_path = output_dir / f"{job_id}_scratch.wav"

    duration = settings.duration_seconds
    fps = settings.fps
    total_frames = max(1, int(duration * fps))

    background = create_paper_background(settings.width, settings.height, settings.paper_texture, settings.seed)
    render_frames(plan.strokes, background, settings, frames_dir, total_frames, progress_callback=progress)

    progress(82, "Saving preview and stroke plan")
    sketch_preview.save(preview_path)
    plan_path.write_text(json.dumps(plan.to_dict(include_strokes=True), indent=2), encoding="utf-8")

    warnings: list[str] = []
    if settings.pencil_audio:
        progress(84, "Generating pencil scratch audio")
        generate_pencil_audio(audio_path, duration, settings.seed)
    progress(88, "Encoding MP4 with FFmpeg")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        warnings.append("FFmpeg was not found on PATH. Frames and plan were generated, but MP4 export was skipped.")
        return {
            "job_id": job_id,
            "mp4": "",
            "frames_dir": str(frames_dir),
            "plan": str(plan_path),
            "preview": str(preview_path),
            "frame_count": total_frames,
            "duration_seconds": duration,
            "warnings": warnings,
        }

    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "frame_%05d.png"),
    ]
    if settings.pencil_audio and audio_path.exists():
        cmd += ["-i", str(audio_path), "-shortest"]
    cmd += [
        "-frames:v",
        str(total_frames),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-crf",
        "20",
        str(mp4_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(90, int(duration * 8)),
        )
    except subprocess.TimeoutExpired as exc:
        warnings.append("FFmpeg timed out while encoding MP4. Frames, preview, and plan are still available.")
        warnings.append(str(exc)[-1200:])
        proc = None

    if proc is not None and proc.returncode != 0:
        warnings.append("FFmpeg failed to encode MP4. Frames, preview, and plan are still available.")
        warnings.append(proc.stderr[-1200:])
    elif proc is not None:
        # Keep the frames folder for debugging/quality review in Batch 3.
        # A later cleanup task can remove these after download.
        pass

    progress(100, "Render complete" if mp4_path.exists() else "Render finished with warnings")
    return {
        "job_id": job_id,
        "mp4": str(mp4_path) if mp4_path.exists() else "",
        "frames_dir": str(frames_dir) if frames_dir.exists() else "",
        "plan": str(plan_path),
        "preview": str(preview_path),
        "frame_count": total_frames,
        "duration_seconds": duration,
        "warnings": warnings,
    }


def render_frames(strokes: list[Stroke], background: Image.Image, settings: RenderSettings, frames_dir: Path, total_frames: int, progress_callback: Callable[[float, str], None] | None = None) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    duration_ms = settings.duration_seconds * 1000
    # Drawing all strokes from scratch per frame is expensive, so cache completed strokes onto a base image.
    completed = background.copy().convert("RGBA")
    last_completed_index = -1
    active_cache: dict[int, Image.Image] = {}

    for frame_idx in range(total_frames):
        if progress_callback and (frame_idx == 0 or frame_idx % max(1, total_frames // 40) == 0):
            progress_callback(8 + 72 * frame_idx / max(1, total_frames - 1), f"Rendering frame {frame_idx + 1} of {total_frames}")
        t = frame_idx / max(1, total_frames - 1) * duration_ms
        frame = completed.copy()

        # Draw newly completed strokes only once onto the completed layer.
        while last_completed_index + 1 < len(strokes) and strokes[last_completed_index + 1].end_ms < t:
            last_completed_index += 1
            draw_stroke(completed, strokes[last_completed_index], settings, progress=1.0)

        active_tip: tuple[float, float] | None = None
        for idx in range(last_completed_index + 1, len(strokes)):
            stroke = strokes[idx]
            if stroke.start_ms <= t <= stroke.end_ms:
                progress = (t - stroke.start_ms) / max(1, stroke.duration_ms)
                active_tip = partial_tip(stroke.points, progress)
                draw_stroke(frame, stroke, settings, progress=progress)
            elif stroke.start_ms > t:
                break

        if settings.hand_overlay and active_tip is not None:
            draw_hand_overlay(frame, active_tip, settings, frame_idx)

        apply_camera_motion_and_labels(frame, settings, frame_idx, total_frames)
        frame.convert("RGB").save(frames_dir / f"frame_{frame_idx:05d}.png", optimize=False)



def apply_camera_motion_and_labels(frame: Image.Image, settings: RenderSettings, frame_idx: int, total_frames: int) -> None:
    # Subtle handheld camera drift. It is intentionally tiny so stroke coordinates remain accurate.
    if getattr(settings, "camera_motion", False):
        drift_x = int(math.sin(frame_idx * 0.013) * 2)
        drift_y = int(math.cos(frame_idx * 0.011) * 2)
        if drift_x or drift_y:
            shifted = Image.new("RGBA", frame.size, PAPER_BASE + (255,))
            shifted.alpha_composite(frame, (drift_x, drift_y))
            frame.paste(shifted)

    draw = ImageDraw.Draw(frame, "RGBA")
    if getattr(settings, "title_card_text", "") and frame_idx < max(1, total_frames * 0.12):
        alpha = int(220 * (1 - frame_idx / max(1, total_frames * 0.12)))
        text = settings.title_card_text
        draw.rounded_rectangle((34, 42, frame.width - 34, 132), radius=20, fill=(255, 250, 238, min(190, alpha)))
        draw.text((56, 72), text, fill=(30, 26, 22, alpha))
    if getattr(settings, "watermark_text", ""):
        text = settings.watermark_text
        draw.text((frame.width - 24 - len(text) * 7, frame.height - 38), text, fill=(40, 35, 29, 95))

def create_paper_background(width: int, height: int, texture: bool, seed: int) -> Image.Image:
    base = Image.new("RGBA", (width, height), PAPER_BASE + (255,))
    if not texture:
        return base
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 7, (height, width)).clip(-22, 22).astype(np.int16)
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    arr[..., 0] = np.clip(PAPER_BASE[0] + noise, 0, 255)
    arr[..., 1] = np.clip(PAPER_BASE[1] + noise, 0, 255)
    arr[..., 2] = np.clip(PAPER_BASE[2] + noise, 0, 255)
    arr[..., 3] = 255
    paper = Image.fromarray(arr, "RGBA").filter(ImageFilter.GaussianBlur(radius=0.35))
    draw = ImageDraw.Draw(paper, "RGBA")
    random.seed(seed)
    for _ in range(max(120, int(width * height / 6500))):
        x = random.randint(0, width)
        y = random.randint(0, height)
        length = random.randint(8, 80)
        alpha = random.randint(5, 18)
        draw.line([(x, y), (x + random.randint(-length, length), y + random.randint(-8, 8))], fill=(92, 75, 52, alpha), width=1)
    return paper


def draw_stroke(image: Image.Image, stroke: Stroke, settings: RenderSettings, progress: float) -> None:
    if len(stroke.points) < 2 or progress <= 0:
        return
    points = partial_polyline(stroke.points, min(1.0, max(0.0, progress)))
    if len(points) < 2:
        return

    # Performance critical: draw into a cropped layer around the stroke instead of
    # allocating a full-canvas transparent layer for every stroke.
    min_x = min(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_x = max(p[0] for p in points)
    max_y = max(p[1] for p in points)
    pad = int(max(18, stroke.thickness * 8 + stroke.jitter * 4 + 18))
    x0 = max(0, int(math.floor(min_x)) - pad)
    y0 = max(0, int(math.floor(min_y)) - pad)
    x1 = min(image.width, int(math.ceil(max_x)) + pad)
    y1 = min(image.height, int(math.ceil(max_y)) + pad)
    if x1 <= x0 or y1 <= y0:
        return
    local_points = [(x - x0, y - y0) for x, y in points]

    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    if getattr(stroke, "effect", "draw") == "erase":
        draw.line(local_points, fill=(255, 250, 238, int(180 * stroke.opacity)), width=max(2, int(stroke.thickness)), joint="curve")
        layer = layer.filter(ImageFilter.GaussianBlur(radius=1.1))
        image.alpha_composite(layer, (x0, y0))
        return
    if getattr(stroke, "effect", "draw") == "smudge":
        draw.line(local_points, fill=(45, 39, 32, int(105 * stroke.opacity)), width=max(3, int(stroke.thickness)), joint="curve")
        layer = layer.filter(ImageFilter.GaussianBlur(radius=2.8 + stroke.thickness * 0.25))
        image.alpha_composite(layer, (x0, y0))
        return
    rng = random.Random(hash((stroke.id, settings.seed)) & 0xFFFFFFFF)
    color_base = STYLE_COLORS.get(settings.style_type, STYLE_COLORS["pencil"])
    alpha = int(255 * stroke.opacity)
    width = max(1, int(round(stroke.thickness)))

    if settings.style_type == "charcoal":
        # Soft body plus dark center.
        draw_textured_line(draw, local_points, color_base + (int(alpha * 0.42),), width + 5, stroke.jitter * 1.4, rng)
        layer = layer.filter(ImageFilter.GaussianBlur(radius=0.55 + stroke.thickness * 0.08))
        draw = ImageDraw.Draw(layer, "RGBA")
        draw_textured_line(draw, local_points, color_base + (alpha,), width + 1, stroke.jitter, rng)
    elif settings.style_type == "marker":
        draw.line(local_points, fill=color_base + (int(alpha * 0.72),), width=width + 3, joint="curve")
        draw.line(local_points, fill=color_base + (alpha,), width=max(1, width), joint="curve")
    elif settings.style_type == "ink":
        draw.line(local_points, fill=color_base + (alpha,), width=width, joint="curve")
    else:
        draw_textured_line(draw, local_points, color_base + (alpha,), width, stroke.jitter, rng)
        # Light duplicate scratch lines create pencil grain.
        if stroke.layer in {"shading", "texture", "layout"}:
            for _ in range(1):
                draw_textured_line(draw, local_points, color_base + (int(alpha * 0.28),), max(1, width - 1), stroke.jitter + 0.9, rng)

    image.alpha_composite(layer, (x0, y0))


def draw_textured_line(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill: tuple[int, int, int, int], width: int, jitter: float, rng: random.Random) -> None:
    if len(points) < 2:
        return
    passes = 1 if jitter < 0.35 else 2
    for _ in range(passes):
        jittered = [(x + rng.uniform(-jitter, jitter), y + rng.uniform(-jitter, jitter)) for x, y in points]
        draw.line(jittered, fill=fill, width=max(1, width), joint="curve")
        # Tiny gaps create hand-drawn roughness for pencil/charcoal.
        if jitter > 0.4 and len(jittered) > 2:
            for a, b in zip(jittered[::3], jittered[1::3]):
                if rng.random() < 0.12:
                    draw.line([a, b], fill=(255, 255, 255, min(45, fill[3] // 3)), width=max(1, width - 1))


def draw_hand_overlay(image: Image.Image, tip: tuple[float, float], settings: RenderSettings, frame_idx: int) -> None:
    if getattr(settings, "hand_mode", "procedural") == "none":
        return
    if getattr(settings, "hand_mode", "procedural") == "uploaded" and getattr(settings, "hand_asset_path", ""):
        if draw_uploaded_hand_overlay(image, tip, settings, frame_idx):
            return
    draw_procedural_hand_overlay(image, tip, settings, frame_idx)


def draw_uploaded_hand_overlay(image: Image.Image, tip: tuple[float, float], settings: RenderSettings, frame_idx: int) -> bool:
    path = Path(getattr(settings, "hand_asset_path", ""))
    if not path.exists():
        return False
    try:
        asset = Image.open(path).convert("RGBA")
    except Exception:
        return False

    base_side = min(settings.width, settings.height)
    target_w = max(32, int(base_side * (settings.hand_scale / 100)))
    scale = target_w / max(1, asset.width)
    target_h = max(32, int(asset.height * scale))
    asset = asset.resize((target_w, target_h), Image.LANCZOS)

    # Small live wobble helps even static assets feel filmed.
    wobble = math.sin(frame_idx * 0.11) * 1.4
    rotation = settings.hand_rotation + wobble
    anchor = (asset.width * settings.hand_tip_x / 100, asset.height * settings.hand_tip_y / 100)
    rotated, rotated_anchor = rotate_with_anchor(asset, rotation, anchor)

    if settings.hand_opacity < 100:
        alpha = rotated.getchannel("A").point(lambda v: int(v * settings.hand_opacity / 100))
        rotated.putalpha(alpha)

    x, y = tip
    paste_x = int(x - rotated_anchor[0])
    paste_y = int(y - rotated_anchor[1])
    image.alpha_composite(rotated, (paste_x, paste_y))
    return True


def rotate_with_anchor(asset: Image.Image, angle_degrees: float, anchor: tuple[float, float]) -> tuple[Image.Image, tuple[float, float]]:
    """Rotate image while tracking where a point in the original image lands."""
    w, h = asset.size
    angle = math.radians(angle_degrees)
    cx, cy = w / 2, h / 2
    corners = [(0, 0), (w, 0), (w, h), (0, h), anchor]

    def rot(pt: tuple[float, float]) -> tuple[float, float]:
        x, y = pt[0] - cx, pt[1] - cy
        xr = x * math.cos(angle) - y * math.sin(angle) + cx
        yr = x * math.sin(angle) + y * math.cos(angle) + cy
        return xr, yr

    rotated_points = [rot(p) for p in corners]
    min_x = min(p[0] for p in rotated_points[:4])
    min_y = min(p[1] for p in rotated_points[:4])
    rotated = asset.rotate(angle_degrees, expand=True, resample=Image.BICUBIC)
    anchor_rot = rotated_points[-1]
    return rotated, (anchor_rot[0] - min_x, anchor_rot[1] - min_y)


def draw_procedural_hand_overlay(image: Image.Image, tip: tuple[float, float], settings: RenderSettings, frame_idx: int) -> None:
    x, y = tip
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    phase = math.sin(frame_idx * 0.14) * 2.0
    # Brush/pencil body.
    pencil_angle = math.radians(settings.hand_rotation) if hasattr(settings, "hand_rotation") else -0.70
    length = 145 if settings.ratio != "16:9" else 105
    back_x = x + math.cos(pencil_angle) * length
    back_y = y + math.sin(pencil_angle) * length
    opacity = int(2.55 * getattr(settings, "hand_opacity", 95))
    draw.line([(back_x, back_y), (x, y)], fill=(91, 62, 38, min(230, opacity)), width=10)
    draw.line([(back_x + 4, back_y + 2), (x + 4, y + 2)], fill=(245, 202, 112, min(190, opacity)), width=3)
    draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(25, 21, 18, min(240, opacity)))
    # Stylized hand shadow/fingers near the pencil.
    palm_x, palm_y = back_x + 32, back_y + 28 + phase
    draw.ellipse((palm_x - 32, palm_y - 22, palm_x + 45, palm_y + 34), fill=(176, 126, 86, min(135, opacity // 2)))
    for i in range(4):
        fx = palm_x - 18 + i * 15
        fy = palm_y + 4 + math.sin(frame_idx * 0.09 + i) * 1.8
        draw.rounded_rectangle((fx, fy, fx + 12, fy + 56), radius=6, fill=(183, 132, 91, min(145, opacity // 2)))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.35))
    image.alpha_composite(overlay)


def partial_polyline(points: list[tuple[float, float]], progress: float) -> list[tuple[float, float]]:
    if progress >= 1:
        return points
    total = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    if total <= 0:
        return points[:1]
    target = total * progress
    acc = 0.0
    out = [points[0]]
    for a, b in zip(points, points[1:]):
        seg = math.dist(a, b)
        if acc + seg <= target:
            out.append(b)
            acc += seg
        else:
            ratio = (target - acc) / max(1e-6, seg)
            out.append((a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio))
            break
    return out


def partial_tip(points: list[tuple[float, float]], progress: float) -> tuple[float, float]:
    partial = partial_polyline(points, progress)
    return partial[-1]
