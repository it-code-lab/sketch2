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
    hand_tip_smoothed: tuple[float, float] | None = None
    hand_angle_smoothed: float | None = None

    for frame_idx in range(total_frames):
        if progress_callback and (frame_idx == 0 or frame_idx % max(1, total_frames // 40) == 0):
            progress_callback(8 + 72 * frame_idx / max(1, total_frames - 1), f"Rendering frame {frame_idx + 1} of {total_frames}")
        t = frame_idx / max(1, total_frames - 1) * duration_ms
        frame = completed.copy()

        # Draw newly completed strokes only once onto the completed layer.
        while last_completed_index + 1 < len(strokes) and strokes[last_completed_index + 1].end_ms < t:
            last_completed_index += 1
            draw_stroke(completed, strokes[last_completed_index], settings, progress=1.0)

        active_state: dict[str, object] | None = None
        for idx in range(last_completed_index + 1, len(strokes)):
            stroke = strokes[idx]
            if stroke.start_ms <= t <= stroke.end_ms:
                progress = (t - stroke.start_ms) / max(1, stroke.duration_ms)
                tip, heading = partial_tip_and_heading(stroke.points, progress)
                active_state = {"tip": tip, "heading": heading, "contact": True, "lift": 0.0}
                draw_stroke(frame, stroke, settings, progress=progress)
            elif stroke.start_ms > t:
                break

        if active_state is None:
            active_state = reposition_hand_state(strokes, last_completed_index, t)

        if settings.hand_overlay and active_state is not None:
            desired_tip = active_state["tip"]  # type: ignore[assignment]
            desired_angle = float(active_state.get("heading", 0.0))
            if hand_tip_smoothed is None:
                hand_tip_smoothed = desired_tip  # type: ignore[assignment]
            else:
                hand_tip_smoothed = smooth_point(hand_tip_smoothed, desired_tip, 0.38 if active_state.get("contact") else 0.22)  # type: ignore[arg-type]
            if hand_angle_smoothed is None:
                hand_angle_smoothed = desired_angle
            else:
                hand_angle_smoothed = smooth_angle(hand_angle_smoothed, desired_angle, 0.22)
            draw_hand_overlay(
                frame,
                hand_tip_smoothed,
                settings,
                frame_idx,
                heading=hand_angle_smoothed,
                contact=bool(active_state.get("contact", True)),
                lift=float(active_state.get("lift", 0.0)),
            )

        apply_camera_motion_and_labels(frame, settings, frame_idx, total_frames)
        frame.convert("RGB").save(frames_dir / f"frame_{frame_idx:05d}.png", optimize=False)



def reposition_hand_state(strokes: list[Stroke], last_completed_index: int, t: float) -> dict[str, object] | None:
    """Move the hand between strokes instead of popping it off-screen.

    During pauses, the hand follows a small lifted arc from the previous stroke end
    to the next stroke start. This makes the animation look like a real artist
    repositioning their hand before drawing again.
    """
    if not strokes:
        return None
    next_index = last_completed_index + 1
    if next_index >= len(strokes):
        last = strokes[-1]
        tip, heading = partial_tip_and_heading(last.points, 1.0)
        return {"tip": tip, "heading": heading, "contact": False, "lift": 1.0}
    next_stroke = strokes[next_index]
    if last_completed_index < 0:
        start = next_stroke.points[0]
        return {"tip": start, "heading": stroke_initial_heading(next_stroke), "contact": False, "lift": 1.0}
    previous = strokes[last_completed_index]
    gap_start = previous.end_ms
    gap_end = next_stroke.start_ms
    if gap_end <= gap_start:
        return None
    gap = gap_end - gap_start
    if gap > 1600:
        # For long planning pauses, hide the hand until it is close to the next action.
        if t < gap_end - 850:
            return None
        gap_start = gap_end - 850
        gap = gap_end - gap_start
    u = max(0.0, min(1.0, (t - gap_start) / max(1.0, gap)))
    eased = ease_in_out(u)
    a = previous.points[-1]
    b = next_stroke.points[0]
    arc_height = min(42.0, 10.0 + distance(a, b) * 0.10)
    x = a[0] + (b[0] - a[0]) * eased
    y = a[1] + (b[1] - a[1]) * eased - math.sin(math.pi * eased) * arc_height
    heading = interpolate_angle(stroke_final_heading(previous), stroke_initial_heading(next_stroke), eased)
    lift = math.sin(math.pi * u)
    return {"tip": (x, y), "heading": heading, "contact": False, "lift": lift}


def smooth_point(current: tuple[float, float], target: tuple[float, float], amount: float) -> tuple[float, float]:
    return (current[0] + (target[0] - current[0]) * amount, current[1] + (target[1] - current[1]) * amount)


def smooth_angle(current: float, target: float, amount: float) -> float:
    diff = math.atan2(math.sin(target - current), math.cos(target - current))
    return current + diff * amount


def interpolate_angle(a: float, b: float, u: float) -> float:
    return smooth_angle(a, b, u)


def ease_in_out(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def stroke_initial_heading(stroke: Stroke) -> float:
    if len(stroke.points) < 2:
        return 0.0
    a, b = stroke.points[0], stroke.points[1]
    return math.atan2(b[1] - a[1], b[0] - a[0])


def stroke_final_heading(stroke: Stroke) -> float:
    if len(stroke.points) < 2:
        return 0.0
    a, b = stroke.points[-2], stroke.points[-1]
    return math.atan2(b[1] - a[1], b[0] - a[0])


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


def draw_hand_overlay(
    image: Image.Image,
    tip: tuple[float, float],
    settings: RenderSettings,
    frame_idx: int,
    heading: float = 0.0,
    contact: bool = True,
    lift: float = 0.0,
) -> None:
    if getattr(settings, "hand_mode", "procedural") == "none":
        return
    # Lift the visual hand/tip slightly during repositioning while keeping the
    # logical pencil tip aligned with the stroke endpoint.
    lifted_tip = (tip[0], tip[1] - lift * 14.0)
    if getattr(settings, "hand_mode", "procedural") == "uploaded" and getattr(settings, "hand_asset_path", ""):
        if draw_uploaded_hand_overlay(image, lifted_tip, settings, frame_idx, heading, contact, lift):
            return
    draw_procedural_hand_overlay(image, lifted_tip, settings, frame_idx, heading, contact, lift)


def draw_contact_shadow(image: Image.Image, tip: tuple[float, float], contact: bool, lift: float) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    x, y = tip
    alpha = int(58 if contact else max(12, 34 * (1 - lift)))
    radius_x = 17 + lift * 16
    radius_y = 5 + lift * 5
    draw.ellipse((x - radius_x, y + 5 - radius_y, x + radius_x, y + 5 + radius_y), fill=(25, 20, 15, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=3.4 + lift * 2.0))
    image.alpha_composite(overlay)


def alpha_shadow(asset: Image.Image, opacity: int = 72, blur: float = 5.5) -> Image.Image:
    alpha = asset.getchannel("A")
    shadow = Image.new("RGBA", asset.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.point(lambda v: int(v * opacity / 255)))
    return shadow.filter(ImageFilter.GaussianBlur(radius=blur))


def draw_uploaded_hand_overlay(
    image: Image.Image,
    tip: tuple[float, float],
    settings: RenderSettings,
    frame_idx: int,
    heading: float,
    contact: bool,
    lift: float,
) -> bool:
    path = Path(getattr(settings, "hand_asset_path", ""))
    if not path.exists():
        return False
    try:
        asset = Image.open(path).convert("RGBA")
    except Exception:
        return False

    draw_contact_shadow(image, tip, contact, lift)
    base_side = min(settings.width, settings.height)
    target_w = max(32, int(base_side * (settings.hand_scale / 100)))
    scale = target_w / max(1, asset.width)
    target_h = max(32, int(asset.height * scale))
    asset = asset.resize((target_w, target_h), Image.LANCZOS)

    # Small live wobble helps even static assets feel filmed. We also allow the
    # hand to respond slightly to stroke direction without spinning too much.
    wobble = math.sin(frame_idx * 0.11) * (1.2 if contact else 2.0)
    heading_degrees = math.degrees(heading) * 0.10
    rotation = settings.hand_rotation + heading_degrees + wobble + lift * 3.0
    anchor = (asset.width * settings.hand_tip_x / 100, asset.height * settings.hand_tip_y / 100)
    rotated, rotated_anchor = rotate_with_anchor(asset, rotation, anchor)

    if settings.hand_opacity < 100:
        alpha = rotated.getchannel("A").point(lambda v: int(v * settings.hand_opacity / 100))
        rotated.putalpha(alpha)

    x, y = tip
    paste_x = int(x - rotated_anchor[0])
    paste_y = int(y - rotated_anchor[1] - lift * 10)
    shadow = alpha_shadow(rotated, opacity=54 if contact else 34, blur=5.5 + lift * 3)
    image.alpha_composite(shadow, (paste_x + int(7 + lift * 6), paste_y + int(9 + lift * 8)))
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


def draw_procedural_hand_overlay(
    image: Image.Image,
    tip: tuple[float, float],
    settings: RenderSettings,
    frame_idx: int,
    heading: float,
    contact: bool,
    lift: float,
) -> None:
    x, y = tip
    draw_contact_shadow(image, tip, contact, lift)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    phase = math.sin(frame_idx * 0.14) * (1.2 if contact else 2.8)
    # Pencil body follows stroke direction a little, while preserving the user
    # supplied hand_rotation as the main grip angle.
    base_angle = math.radians(settings.hand_rotation) if hasattr(settings, "hand_rotation") else -0.70
    pencil_angle = base_angle + heading * 0.13 + lift * 0.08
    length = 145 if settings.ratio != "16:9" else 105
    back_x = x + math.cos(pencil_angle) * length
    back_y = y + math.sin(pencil_angle) * length - lift * 12
    opacity = int(2.55 * getattr(settings, "hand_opacity", 95))

    # Pencil shadow under the barrel.
    draw.line([(back_x + 8, back_y + 11 + lift * 5), (x + 8, y + 11 + lift * 5)], fill=(20, 16, 12, 45 if contact else 26), width=13)
    draw.line([(back_x, back_y), (x, y)], fill=(91, 62, 38, min(230, opacity)), width=10)
    draw.line([(back_x + 4, back_y + 2), (x + 4, y + 2)], fill=(245, 202, 112, min(190, opacity)), width=3)
    tip_alpha = min(245, opacity) if contact else min(150, opacity)
    draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(25, 21, 18, tip_alpha))

    # Stylized hand shadow/fingers near the pencil.
    palm_x, palm_y = back_x + 32, back_y + 28 + phase
    shadow_alpha = 54 if contact else 34
    draw.ellipse((palm_x - 42, palm_y - 16 + lift * 5, palm_x + 54, palm_y + 44 + lift * 5), fill=(20, 16, 12, shadow_alpha))
    draw.ellipse((palm_x - 32, palm_y - 22, palm_x + 45, palm_y + 34), fill=(176, 126, 86, min(145, opacity // 2)))
    for i in range(4):
        fx = palm_x - 18 + i * 15
        fy = palm_y + 4 + math.sin(frame_idx * 0.09 + i) * (1.6 if contact else 3.2)
        draw.rounded_rectangle((fx, fy, fx + 12, fy + 56), radius=6, fill=(183, 132, 91, min(150, opacity // 2)))
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


def partial_tip_and_heading(points: list[tuple[float, float]], progress: float) -> tuple[tuple[float, float], float]:
    partial = partial_polyline(points, progress)
    if not partial:
        return ((0.0, 0.0), 0.0)
    tip = partial[-1]
    if len(partial) >= 2:
        prev = partial[-2]
    elif len(points) >= 2:
        prev = points[0]
    else:
        prev = tip
    heading = math.atan2(tip[1] - prev[1], tip[0] - prev[0])
    return tip, heading
