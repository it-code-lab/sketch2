from __future__ import annotations

import json
from dataclasses import dataclass, field
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
from backend.services.audio import generate_layered_audio

STYLE_COLORS = {
    "pencil": (34, 32, 29),
    "charcoal": (24, 22, 20),
    "ink": (12, 12, 12),
    "marker": (20, 20, 20),
}

PAPER_BASE = (242, 235, 219)


def quality_encode_options(settings: RenderSettings) -> tuple[str, str]:
    quality = getattr(settings, "render_quality", "standard")
    if quality == "preview":
        return "24", "veryfast"
    if quality == "final":
        return "18", "slow"
    if quality == "ultra":
        return "16", "slow"
    return "20", "medium"


@dataclass
class HandVideoOverlay:
    frame_paths: list[Path]
    warnings: list[str] = field(default_factory=list)
    cache: dict[int, Image.Image] = field(default_factory=dict)

    def frame(self, frame_idx: int, settings: RenderSettings) -> Image.Image | None:
        if not self.frame_paths:
            return None
        rate = max(25, min(400, int(getattr(settings, "hand_video_playback_rate", 100)))) / 100.0
        offset = int(getattr(settings, "hand_video_frame_offset", 0))
        raw_index = int(frame_idx * rate) + offset
        if getattr(settings, "hand_video_loop", True):
            idx = raw_index % len(self.frame_paths)
        else:
            idx = max(0, min(len(self.frame_paths) - 1, raw_index))
        if idx not in self.cache:
            try:
                frame = Image.open(self.frame_paths[idx]).convert("RGBA")
                if getattr(settings, "hand_video_chroma_key", False):
                    frame = apply_green_chroma_key(frame)
                self.cache[idx] = frame
                # Keep memory bounded during long renders. Sequential access means
                # dropping older decoded frames is usually fine.
                if len(self.cache) > 96:
                    for key in sorted(self.cache.keys())[:32]:
                        self.cache.pop(key, None)
            except Exception:
                return None
        return self.cache[idx]


def prepare_hand_video_overlay(settings: RenderSettings, output_dir: Path, job_id: str, total_frames: int) -> HandVideoOverlay | None:
    if getattr(settings, "hand_mode", "procedural") != "video":
        return None
    asset_path = Path(getattr(settings, "hand_asset_path", ""))
    if not asset_path.exists():
        return HandVideoOverlay([], ["Hand video mode selected, but no video asset was uploaded."])
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return HandVideoOverlay([], ["FFmpeg is required to extract transparent hand video frames."])

    cache_dir = output_dir / f"{job_id}_hand_video_frames"
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Extract at render FPS. Transparent WebM/MOV assets keep their alpha when
    # decoded into RGBA PNG frames. MP4 normally has no alpha, but is still usable
    # as a regular opaque overlay or with optional green-screen keying.
    cmd = [
        ffmpeg, "-y", "-i", str(asset_path),
        "-vf", f"fps={settings.fps}",
        "-frames:v", str(max(1, min(total_frames * 2, 6000))),
        "-pix_fmt", "rgba",
        str(cache_dir / "hand_%05d.png"),
    ]
    warnings: list[str] = []
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=max(40, int(settings.duration_seconds * 4)))
        if proc.returncode != 0:
            warnings.append("FFmpeg could not extract hand video frames; falling back to procedural hand overlay.")
            warnings.append(proc.stderr[-1200:])
    except subprocess.TimeoutExpired as exc:
        warnings.append("Timed out while extracting hand video frames; falling back to procedural hand overlay.")
        warnings.append(str(exc)[-600:])

    frame_paths = sorted(cache_dir.glob("hand_*.png"))
    if not frame_paths:
        warnings.append("No hand video frames were extracted. Check that the file is a valid WebM/MP4/MOV/MKV video.")
    return HandVideoOverlay(frame_paths, warnings)


def apply_green_chroma_key(frame: Image.Image) -> Image.Image:
    arr = np.array(frame.convert("RGBA"))
    r = arr[..., 0].astype(np.int16)
    g = arr[..., 1].astype(np.int16)
    b = arr[..., 2].astype(np.int16)
    # Conservative green screen removal: strong green and clearly above red/blue.
    mask = (g > 95) & (g > r * 1.25) & (g > b * 1.25)
    softness = np.clip((g - np.maximum(r, b) - 18) * 5, 0, 255).astype(np.uint8)
    alpha = arr[..., 3]
    alpha[mask] = np.minimum(alpha[mask], 255 - softness[mask])
    arr[..., 3] = alpha
    return Image.fromarray(arr, "RGBA")


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
    audio_path = output_dir / f"{job_id}_audio.wav"

    duration = settings.duration_seconds
    fps = settings.fps
    total_frames = max(1, int(duration * fps))

    warnings: list[str] = []
    hand_video_overlay = None
    if getattr(settings, "hand_mode", "procedural") == "video":
        progress(5, "Extracting transparent hand video frames")
        hand_video_overlay = prepare_hand_video_overlay(settings, output_dir, job_id, total_frames)
        if hand_video_overlay:
            warnings.extend(hand_video_overlay.warnings)

    background = create_paper_background(settings.width, settings.height, settings.paper_texture, settings.seed, settings)
    render_frames(plan.strokes, background, settings, frames_dir, total_frames, progress_callback=progress, hand_video_overlay=hand_video_overlay)

    progress(82, "Saving preview and stroke plan")
    sketch_preview.save(preview_path)
    plan_path.write_text(json.dumps(plan.to_dict(include_strokes=True), indent=2), encoding="utf-8")

    if settings.pencil_audio:
        progress(84, "Generating layered drawing audio")
        generate_layered_audio(
            audio_path,
            duration,
            seed=settings.seed,
            style_type=getattr(settings, "style_type", "pencil"),
            ambient_track=getattr(settings, "ambient_track", "none"),
            ambient_level=getattr(settings, "ambient_level", 18),
            drawing_level=getattr(settings, "drawing_audio_level", 70),
            transition_sfx=False,
            transition_sfx_level=getattr(settings, "transition_sfx_level", 30),
        )
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
            "audio": str(audio_path) if audio_path.exists() else "",
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
    crf, preset = quality_encode_options(settings)
    cmd += [
        "-frames:v",
        str(total_frames),
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-crf",
        crf,
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
        "audio": str(audio_path) if audio_path.exists() else "",
        "frame_count": total_frames,
        "duration_seconds": duration,
        "warnings": warnings,
    }


def render_frames(strokes: list[Stroke], background: Image.Image, settings: RenderSettings, frames_dir: Path, total_frames: int, progress_callback: Callable[[float, str], None] | None = None, hand_video_overlay: HandVideoOverlay | None = None) -> None:
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
                tip, heading = contact_tip_and_heading(stroke.points, progress, settings)
                active_state = {"tip": tip, "heading": heading, "contact": True, "lift": 0.0, "progress": progress}
                draw_stroke(frame, stroke, settings, progress=progress)
            elif stroke.start_ms > t:
                break

        if active_state is None:
            active_state = reposition_hand_state(strokes, last_completed_index, t, settings)

        if settings.hand_overlay and active_state is not None:
            desired_tip = active_state["tip"]  # type: ignore[assignment]
            desired_angle = float(active_state.get("heading", 0.0))
            contact_amount = bool(active_state.get("contact", True))
            contact_smoothing = smoothing_amount(settings, contact=contact_amount)
            angle_smoothing = angle_smoothing_amount(settings, contact=contact_amount)
            if hand_tip_smoothed is None:
                hand_tip_smoothed = desired_tip  # type: ignore[assignment]
            else:
                hand_tip_smoothed = smooth_point(hand_tip_smoothed, desired_tip, contact_smoothing)  # type: ignore[arg-type]
                if contact_amount:
                    hand_tip_smoothed = apply_contact_correction(hand_tip_smoothed, desired_tip, settings)
            if hand_angle_smoothed is None:
                hand_angle_smoothed = desired_angle
            else:
                hand_angle_smoothed = smooth_angle(hand_angle_smoothed, desired_angle, angle_smoothing)
            draw_hand_overlay(
                frame,
                hand_tip_smoothed,
                settings,
                frame_idx,
                heading=hand_angle_smoothed,
                contact=bool(active_state.get("contact", True)),
                lift=float(active_state.get("lift", 0.0)),
                hand_video_overlay=hand_video_overlay,
            )

        apply_frame_motion_blur(frame, settings, frame_idx, total_frames)
        apply_camera_motion_and_labels(frame, settings, frame_idx, total_frames)
        frame.convert("RGB").save(frames_dir / f"frame_{frame_idx:05d}.png", optimize=False)



def smoothing_amount(settings: RenderSettings, contact: bool = True) -> float:
    base = max(0.0, min(100.0, float(getattr(settings, "contact_position_smoothing", 58)))) / 100.0
    if contact:
        # More smoothing slider means less snap. Keep contact fairly responsive.
        return max(0.18, min(0.72, 0.78 - base * 0.46))
    return max(0.10, min(0.48, 0.52 - base * 0.24))


def angle_smoothing_amount(settings: RenderSettings, contact: bool = True) -> float:
    base = max(0.0, min(100.0, float(getattr(settings, "contact_position_smoothing", 58)))) / 100.0
    return max(0.10, min(0.52, (0.28 if contact else 0.18) + (0.22 - base * 0.10)))


def apply_contact_correction(current: tuple[float, float], desired: tuple[float, float], settings: RenderSettings) -> tuple[float, float]:
    strength = max(0.0, min(100.0, float(getattr(settings, "contact_correction_strength", 72)))) / 100.0
    blend = 0.16 + strength * 0.52
    return (current[0] + (desired[0] - current[0]) * blend, current[1] + (desired[1] - current[1]) * blend)


def contact_tip_and_heading(points: list[tuple[float, float]], progress: float, settings: RenderSettings) -> tuple[tuple[float, float], float]:
    tip, heading = partial_tip_and_heading(points, progress)
    # Look slightly ahead and behind to stabilize orientation and produce better hand-stroke contact.
    look = 0.02 + max(0.0, min(100.0, float(getattr(settings, "contact_correction_strength", 72)))) / 100.0 * 0.06
    prev_tip = partial_tip(points, max(0.0, progress - look))
    next_tip = partial_tip(points, min(1.0, progress + look))
    dx = next_tip[0] - prev_tip[0]
    dy = next_tip[1] - prev_tip[1]
    if abs(dx) > 1e-5 or abs(dy) > 1e-5:
        heading = math.atan2(dy, dx)
    return tip, heading



def reposition_hand_state(strokes: list[Stroke], last_completed_index: int, t: float, settings: RenderSettings) -> dict[str, object] | None:
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
    arc_scale = max(0.25, min(1.65, getattr(settings, "reposition_arc_strength", 55) / 55.0))
    arc_height = min(58.0, (10.0 + distance(a, b) * 0.10) * arc_scale)
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


def resolve_camera_move(settings: RenderSettings) -> tuple[float, float, float, float, float, float]:
    preset = getattr(settings, "camera_move_preset", "static") or "static"
    zs = float(getattr(settings, "camera_zoom_start", 100))
    ze = float(getattr(settings, "camera_zoom_end", 100))
    psx = float(getattr(settings, "camera_pan_start_x", 0))
    psy = float(getattr(settings, "camera_pan_start_y", 0))
    pex = float(getattr(settings, "camera_pan_end_x", 0))
    pey = float(getattr(settings, "camera_pan_end_y", 0))
    if preset == "zoom_in":
        zs, ze = 100, max(110, ze if ze != 100 else 120)
    elif preset == "zoom_out":
        zs, ze = max(110, zs if zs != 100 else 120), 100
    elif preset == "pan_left_to_right":
        psx, pex = -55, 55
    elif preset == "pan_right_to_left":
        psx, pex = 55, -55
    elif preset == "pan_top_to_bottom":
        psy, pey = -55, 55
    elif preset == "pan_bottom_to_top":
        psy, pey = 55, -55
    elif preset == "ken_burns":
        zs, ze = 108, 126
        psx, psy, pex, pey = -18, -10, 18, 12
    elif preset == "push_in_left":
        zs, ze = 104, 124
        psx, pex = -40, -8
    elif preset == "push_in_right":
        zs, ze = 104, 124
        psx, pex = 40, 8
    return zs, ze, psx, psy, pex, pey


def apply_scene_camera_transform(frame: Image.Image, settings: RenderSettings, frame_idx: int, total_frames: int) -> None:
    preset = getattr(settings, "camera_move_preset", "static") or "static"
    if preset == "static" and all(int(getattr(settings, k, 0)) == default for k, default in [("camera_zoom_start",100),("camera_zoom_end",100),("camera_pan_start_x",0),("camera_pan_start_y",0),("camera_pan_end_x",0),("camera_pan_end_y",0)]):
        return
    t = 0.0 if total_frames <= 1 else frame_idx / max(1, total_frames - 1)
    zs, ze, psx, psy, pex, pey = resolve_camera_move(settings)
    zoom = max(1.0, (zs + (ze - zs) * t) / 100.0)
    src = frame.copy()
    crop_w = max(8, int(round(src.width / zoom)))
    crop_h = max(8, int(round(src.height / zoom)))
    max_dx = max(0.0, (src.width - crop_w) / 2.0)
    max_dy = max(0.0, (src.height - crop_h) / 2.0)
    pan_x = (psx + (pex - psx) * t) / 100.0
    pan_y = (psy + (pey - psy) * t) / 100.0
    cx = src.width / 2.0 + max_dx * pan_x
    cy = src.height / 2.0 + max_dy * pan_y
    left = int(round(max(0, min(src.width - crop_w, cx - crop_w / 2.0))))
    top = int(round(max(0, min(src.height - crop_h, cy - crop_h / 2.0))))
    cropped = src.crop((left, top, left + crop_w, top + crop_h)).resize(src.size, Image.LANCZOS)
    frame.paste(cropped)


def apply_frame_motion_blur(frame: Image.Image, settings: RenderSettings, frame_idx: int, total_frames: int) -> None:
    strength = max(0, min(100, int(getattr(settings, "motion_blur_strength", 14))))
    if strength <= 0:
        return
    quality = getattr(settings, "render_quality", "standard")
    if quality == "preview" and strength < 18:
        return
    radius = 1 if strength < 40 else 2
    alpha = 0.06 + strength / 220.0
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    dx = int(round(math.sin(frame_idx * 0.21) * radius))
    dy = int(round(math.cos(frame_idx * 0.17) * radius))
    if dx == 0 and dy == 0:
        dx = 1
    overlay.alpha_composite(frame, (dx, dy))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.6 + strength / 95.0))
    frame.alpha_composite(overlay, (0, 0))


def apply_camera_motion_and_labels(frame: Image.Image, settings: RenderSettings, frame_idx: int, total_frames: int) -> None:
    apply_scene_camera_transform(frame, settings, frame_idx, total_frames)
    # Subtle handheld camera drift. It is intentionally tiny so stroke coordinates remain accurate.
    if getattr(settings, "camera_motion", False):
        move_preset = getattr(settings, "camera_move_preset", "static") or "static"
        drift_amt = 1 if move_preset == "static" else 2
        drift_x = int(math.sin(frame_idx * 0.013) * drift_amt)
        drift_y = int(math.cos(frame_idx * 0.011) * drift_amt)
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

def create_paper_background(width: int, height: int, texture: bool, seed: int, settings: RenderSettings | None = None) -> Image.Image:
    base = Image.new("RGBA", (width, height), PAPER_BASE + (255,))
    if not texture:
        return base
    rng = np.random.default_rng(seed)
    noise_sigma = 6 if not settings else {"preview": 5, "standard": 6, "final": 7, "ultra": 8}.get(getattr(settings, "render_quality", "standard"), 6)
    noise = rng.normal(0, noise_sigma, (height, width)).clip(-24, 24).astype(np.int16)
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    arr[..., 0] = np.clip(PAPER_BASE[0] + noise, 0, 255)
    arr[..., 1] = np.clip(PAPER_BASE[1] + noise, 0, 255)
    arr[..., 2] = np.clip(PAPER_BASE[2] + noise, 0, 255)
    arr[..., 3] = 255
    paper = Image.fromarray(arr, "RGBA").filter(ImageFilter.GaussianBlur(radius=0.35))
    draw = ImageDraw.Draw(paper, "RGBA")
    random.seed(seed)
    density_factor = {"preview": 0.7, "standard": 1.0, "final": 1.25, "ultra": 1.5}.get(getattr(settings, "render_quality", "standard") if settings else "standard", 1.0)
    for _ in range(max(120, int(width * height / 6500 * density_factor))):
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
    taper_strength = max(0.0, min(1.0, getattr(settings, "stroke_taper", 58) / 100.0))

    if settings.style_type == "charcoal":
        # Soft body plus dark center and dust.
        draw_variable_width_line(draw, local_points, color_base + (int(alpha * 0.34),), width + 6, stroke.jitter * 1.5, rng, taper_strength * 0.35)
        sprinkle_texture(draw, local_points, color_base, int(alpha * 0.18), getattr(settings, "charcoal_dust", 55), rng, radius=8)
        layer = layer.filter(ImageFilter.GaussianBlur(radius=0.7 + stroke.thickness * 0.10 + getattr(settings, "charcoal_dust", 55) / 220))
        draw = ImageDraw.Draw(layer, "RGBA")
        draw_variable_width_line(draw, local_points, color_base + (alpha,), width + 1, stroke.jitter, rng, taper_strength)
    elif settings.style_type == "marker":
        overlap = max(0.0, min(1.0, getattr(settings, "marker_overlap", 42) / 100.0))
        draw_variable_width_line(draw, local_points, color_base + (int(alpha * (0.50 + overlap * 0.18)),), width + 3, stroke.jitter * 0.55, rng, taper_strength * 0.18)
        for offset in [(-1.0, 0.5), (1.2, -0.4)]:
            shifted = [(x + offset[0], y + offset[1]) for x, y in local_points]
            draw_variable_width_line(draw, shifted, color_base + (int(alpha * (0.28 + overlap * 0.12)),), max(1, width), stroke.jitter * 0.35, rng, taper_strength * 0.12)
        draw_variable_width_line(draw, local_points, color_base + (alpha,), max(1, width), stroke.jitter * 0.25, rng, taper_strength * 0.15)
    elif settings.style_type == "ink":
        draw_variable_width_line(draw, local_points, color_base + (alpha,), width, stroke.jitter * 0.18, rng, taper_strength)
        bleed = getattr(settings, "ink_bleed", 28)
        if bleed > 0:
            bleed_layer = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            bleed_draw = ImageDraw.Draw(bleed_layer, "RGBA")
            draw_variable_width_line(bleed_draw, local_points, color_base + (int(alpha * 0.22),), width + 2, stroke.jitter * 0.16, rng, taper_strength * 0.55)
            bleed_layer = bleed_layer.filter(ImageFilter.GaussianBlur(radius=0.4 + bleed / 45.0))
            layer.alpha_composite(bleed_layer)
    else:
        draw_variable_width_line(draw, local_points, color_base + (alpha,), width, stroke.jitter, rng, taper_strength)
        graphite = getattr(settings, "graphite_grain", 65)
        add_graphite_grain(draw, local_points, color_base, int(alpha * 0.22), graphite, rng)
        if stroke.layer in {"shading", "texture", "layout"}:
            draw_variable_width_line(draw, local_points, color_base + (int(alpha * 0.26),), max(1, width - 1), stroke.jitter + 0.9, rng, taper_strength * 0.55)

    image.alpha_composite(layer, (x0, y0))


def tapered_factor(u: float, strength: float) -> float:
    # 1 at center, lower at the ends.
    if strength <= 0.0:
        return 1.0
    edge = abs(u - 0.5) * 2.0
    return max(0.28, 1.0 - edge * strength * 0.85)


def draw_variable_width_line(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill: tuple[int, int, int, int], width: int, jitter: float, rng: random.Random, taper_strength: float = 0.0) -> None:
    if len(points) < 2:
        return
    total_segments = max(1, len(points) - 1)
    jittered = [(x + rng.uniform(-jitter, jitter), y + rng.uniform(-jitter, jitter)) for x, y in points]
    for idx, (a, b) in enumerate(zip(jittered, jittered[1:])):
        u = idx / max(1, total_segments - 1)
        seg_width = max(1, int(round(width * tapered_factor(u, taper_strength))))
        draw.line([a, b], fill=fill, width=seg_width, joint="curve")


def sprinkle_texture(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], color_base: tuple[int, int, int], alpha: int, amount: int, rng: random.Random, radius: int = 6) -> None:
    density = max(0, min(100, amount))
    if density <= 0 or len(points) < 2:
        return
    step = max(2, 7 - density // 18)
    for idx, (x, y) in enumerate(points[::step]):
        count = 1 + density // 28
        for _ in range(count):
            dx = rng.uniform(-radius, radius)
            dy = rng.uniform(-radius * 0.7, radius * 0.7)
            r = max(1, 1 + density // 40)
            a = max(8, min(255, alpha + rng.randint(-14, 14)))
            draw.ellipse((x + dx - r, y + dy - r, x + dx + r, y + dy + r), fill=color_base + (a,))


def add_graphite_grain(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], color_base: tuple[int, int, int], alpha: int, amount: int, rng: random.Random) -> None:
    density = max(0, min(100, amount))
    if density <= 0:
        return
    step = max(2, 9 - density // 14)
    for x, y in points[::step]:
        for _ in range(1 + density // 35):
            dx = rng.uniform(-3.0, 3.0)
            dy = rng.uniform(-2.0, 2.0)
            a = max(8, min(255, alpha + rng.randint(-18, 18)))
            draw.point((x + dx, y + dy), fill=color_base + (a,))


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
    hand_video_overlay: HandVideoOverlay | None = None,
) -> None:
    mode = getattr(settings, "hand_mode", "procedural")
    if mode == "none":
        return
    # Lift the visual hand/tip slightly during repositioning while keeping the
    # logical pencil tip aligned with the stroke endpoint.
    lift_px = float(getattr(settings, "hand_lift_px", 14))
    lifted_tip = (tip[0], tip[1] - lift * lift_px)
    if mode == "video" and hand_video_overlay is not None:
        asset = hand_video_overlay.frame(frame_idx, settings)
        if asset is not None:
            if draw_hand_asset_overlay(image, asset, lifted_tip, settings, frame_idx, heading, contact, lift, video_asset=True):
                return
    if mode == "uploaded" and getattr(settings, "hand_asset_path", ""):
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
    return draw_hand_asset_overlay(image, asset, tip, settings, frame_idx, heading, contact, lift, video_asset=False)


def draw_hand_asset_overlay(
    image: Image.Image,
    asset: Image.Image,
    tip: tuple[float, float],
    settings: RenderSettings,
    frame_idx: int,
    heading: float,
    contact: bool,
    lift: float,
    video_asset: bool = False,
) -> bool:
    if asset.width < 2 or asset.height < 2:
        return False
    draw_contact_shadow(image, tip, contact, lift)
    base_side = min(settings.width, settings.height)
    target_w = max(32, int(base_side * (settings.hand_scale / 100)))
    scale = target_w / max(1, asset.width)
    target_h = max(32, int(asset.height * scale))
    asset = asset.resize((target_w, target_h), Image.LANCZOS)

    # Hand video already contains natural finger/arm motion. Keep stroke-direction
    # response subtle to avoid fighting the real footage. Static assets get more
    # wobble to feel less frozen.
    wobble_size = 0.45 if video_asset else (1.0 if contact else 1.8)
    wobble = math.sin(frame_idx * 0.11) * wobble_size
    correction = max(0.0, min(100.0, float(getattr(settings, "contact_correction_strength", 72)))) / 100.0
    side_sign = -1 if getattr(settings, "hand_side", "right") == "left" else 1
    heading_degrees = math.degrees(heading) * (0.045 + correction * (0.025 if video_asset else 0.07))
    rotation = settings.hand_rotation + heading_degrees + wobble + lift * (1.2 if video_asset else 2.6) + side_sign * (1.6 * correction if contact else 0.0)
    anchor = (asset.width * settings.hand_tip_x / 100, asset.height * settings.hand_tip_y / 100)
    rotated, rotated_anchor = rotate_with_anchor(asset, rotation, anchor)

    if settings.hand_opacity < 100:
        alpha = rotated.getchannel("A").point(lambda v: int(v * settings.hand_opacity / 100))
        rotated.putalpha(alpha)

    x, y = tip
    paste_x = int(x - rotated_anchor[0])
    paste_y = int(y - rotated_anchor[1] - lift * max(4, getattr(settings, "hand_lift_px", 14) * 0.7))
    shadow_strength = max(0, min(100, int(getattr(settings, "hand_shadow_strength", 70)))) / 100.0
    if shadow_strength > 0:
        shadow_opacity = int((54 if contact else 34) * shadow_strength)
        shadow = alpha_shadow(rotated, opacity=shadow_opacity, blur=5.5 + lift * 3)
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
    correction = max(0.0, min(100.0, float(getattr(settings, "contact_correction_strength", 72)))) / 100.0
    side_sign = -1 if getattr(settings, "hand_side", "right") == "left" else 1
    pencil_angle = base_angle + heading * (0.11 + correction * 0.08) + lift * 0.08 + side_sign * correction * 0.04
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
