from __future__ import annotations

import copy
import json
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from backend.models import RenderSettings
from backend.services.audio import generate_layered_audio
from backend.services.render_engine import quality_encode_options, render_plan_to_mp4
from backend.services.sketch_pipeline import make_stroke_plan


@dataclass
class SceneSpec:
    scene_id: str
    source_name: str
    title: str = ""
    duration_seconds: int = 6
    transition: str = "fade"
    transition_duration: float = 0.6
    subject_type: str = ""
    style_type: str = ""
    planning_mode: str = ""
    notes: str = ""
    camera_move_preset: str = ""
    camera_zoom_start: int | None = None
    camera_zoom_end: int | None = None
    camera_pan_start_x: int | None = None
    camera_pan_start_y: int | None = None
    camera_pan_end_x: int | None = None
    camera_pan_end_y: int | None = None
    ambient_track: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], fallback_index: int) -> "SceneSpec":
        source_name = str(data.get("source") or data.get("source_name") or "").strip()
        return cls(
            scene_id=str(data.get("scene_id") or f"scene_{fallback_index:02d}"),
            source_name=source_name,
            title=str(data.get("title") or "").strip(),
            duration_seconds=max(1, min(120, int(data.get("duration_seconds") or 6))),
            transition=str(data.get("transition") or "fade").strip().lower() or "fade",
            transition_duration=max(0.0, min(3.0, float(data.get("transition_duration") or 0.6))),
            subject_type=str(data.get("subject_type") or "").strip(),
            style_type=str(data.get("style_type") or "").strip(),
            planning_mode=str(data.get("planning_mode") or "").strip(),
            notes=str(data.get("notes") or "").strip(),
            camera_move_preset=str(data.get("camera_move_preset") or "").strip(),
            camera_zoom_start=(int(data["camera_zoom_start"]) if data.get("camera_zoom_start") is not None else None),
            camera_zoom_end=(int(data["camera_zoom_end"]) if data.get("camera_zoom_end") is not None else None),
            camera_pan_start_x=(int(data["camera_pan_start_x"]) if data.get("camera_pan_start_x") is not None else None),
            camera_pan_start_y=(int(data["camera_pan_start_y"]) if data.get("camera_pan_start_y") is not None else None),
            camera_pan_end_x=(int(data["camera_pan_end_x"]) if data.get("camera_pan_end_x") is not None else None),
            camera_pan_end_y=(int(data["camera_pan_end_y"]) if data.get("camera_pan_end_y") is not None else None),
            ambient_track=str(data.get("ambient_track") or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "source_name": self.source_name,
            "title": self.title,
            "duration_seconds": self.duration_seconds,
            "transition": self.transition,
            "transition_duration": self.transition_duration,
            "subject_type": self.subject_type,
            "style_type": self.style_type,
            "planning_mode": self.planning_mode,
            "notes": self.notes,
            "camera_move_preset": self.camera_move_preset,
            "camera_zoom_start": self.camera_zoom_start,
            "camera_zoom_end": self.camera_zoom_end,
            "camera_pan_start_x": self.camera_pan_start_x,
            "camera_pan_start_y": self.camera_pan_start_y,
            "camera_pan_end_x": self.camera_pan_end_x,
            "camera_pan_end_y": self.camera_pan_end_y,
            "ambient_track": self.ambient_track,
        }


def build_default_timeline(filenames: list[str]) -> list[SceneSpec]:
    scenes: list[SceneSpec] = []
    for idx, name in enumerate(filenames, start=1):
        scenes.append(
            SceneSpec(
                scene_id=f"scene_{idx:02d}",
                source_name=name,
                title=Path(name).stem.replace("_", " ").title(),
                duration_seconds=6,
                transition="fade" if idx > 1 else "cut",
                transition_duration=0.6,
            )
        )
    return scenes


def parse_timeline_json(timeline_json: str, filenames: list[str]) -> list[SceneSpec]:
    if not timeline_json.strip():
        return build_default_timeline(filenames)
    try:
        raw = json.loads(timeline_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Timeline JSON could not be parsed: {exc}") from exc
    if not isinstance(raw, list):
        raise ValueError("Timeline JSON must be an array of scene objects.")
    scenes = [SceneSpec.from_dict(item if isinstance(item, dict) else {}, idx + 1) for idx, item in enumerate(raw)]
    if not scenes:
        return build_default_timeline(filenames)
    # Fill any missing source names from upload order.
    available = list(filenames)
    used: set[str] = set()
    for scene in scenes:
        if scene.source_name and scene.source_name in filenames:
            used.add(scene.source_name)
    fallback_iter = iter([name for name in available if name not in used] or available)
    for scene in scenes:
        if not scene.source_name:
            scene.source_name = next(fallback_iter, available[min(len(available) - 1, 0)] if available else "")
    return scenes


def _load_frame_paths(frames_dir: Path) -> list[Path]:
    return sorted(frames_dir.glob("frame_*.png"))


def _blend_frames(a: Image.Image, b: Image.Image, n: int, transition: str = "fade") -> list[Image.Image]:
    if n <= 0:
        return []
    frames: list[Image.Image] = []
    a = a.convert("RGBA")
    b = b.convert("RGBA")
    black = Image.new("RGBA", a.size, (0, 0, 0, 255))
    transition = (transition or "fade").lower()
    for idx in range(1, n + 1):
        alpha = idx / (n + 1)
        if transition == "dipblack":
            if alpha < 0.5:
                frame = Image.blend(a, black, alpha * 2.0)
            else:
                frame = Image.blend(black, b, (alpha - 0.5) * 2.0)
        elif transition == "wipe_left":
            frame = a.copy()
            cut = int(round(a.width * alpha))
            frame.alpha_composite(b.crop((0, 0, cut, b.height)), (0, 0))
        elif transition == "wipe_right":
            frame = a.copy()
            cut = int(round(a.width * alpha))
            crop = b.crop((b.width - cut, 0, b.width, b.height))
            frame.alpha_composite(crop, (a.width - cut, 0))
        elif transition == "zoomfade":
            zoom = 1.0 + 0.08 * alpha
            crop_w = max(8, int(round(b.width / zoom)))
            crop_h = max(8, int(round(b.height / zoom)))
            left = max(0, (b.width - crop_w) // 2)
            top = max(0, (b.height - crop_h) // 2)
            bz = b.crop((left, top, left + crop_w, top + crop_h)).resize(b.size, Image.LANCZOS)
            frame = Image.blend(a, bz, alpha)
        else:
            frame = Image.blend(a, b, alpha)
        frames.append(frame)
    return frames


def stitch_scene_frames(
    scene_results: list[dict[str, Any]],
    output_dir: Path,
    base_settings: RenderSettings,
    project_name: str,
) -> tuple[Path, int, float, list[str]]:
    final_frames_dir = output_dir / f"timeline_{project_name}_{int(time.time())}_{uuid.uuid4().hex[:6]}_frames"
    final_frames_dir.mkdir(parents=True, exist_ok=True)
    fps = base_settings.fps
    warnings: list[str] = []
    frame_index = 0
    total_duration = 0.0
    previous_last: Image.Image | None = None

    for scene_idx, item in enumerate(scene_results):
        scene = item["scene"]
        frames = _load_frame_paths(Path(item["result"]["frames_dir"]))
        if not frames:
            warnings.append(f"Scene {scene.scene_id} produced no frames and was skipped in the timeline stitch.")
            continue
        if scene_idx > 0 and previous_last is not None and scene.transition == "fade":
            trans_frames = max(0, int(scene.transition_duration * fps))
            first_current = Image.open(frames[0]).convert("RGBA")
            for blended in _blend_frames(previous_last, first_current, trans_frames, scene.transition):
                blended.save(final_frames_dir / f"frame_{frame_index:05d}.png")
                frame_index += 1
            total_duration += trans_frames / max(1, fps)
        # Append actual scene frames. For fade, skip duplicate first frame because transition leads into it.
        start_index = 1 if (scene_idx > 0 and scene.transition == "fade") else 0
        for frame_path in frames[start_index:]:
            shutil.copy2(frame_path, final_frames_dir / f"frame_{frame_index:05d}.png")
            frame_index += 1
        total_duration += max(0.0, item["result"].get("duration_seconds", scene.duration_seconds))
        previous_last = Image.open(frames[-1]).convert("RGBA")

    return final_frames_dir, frame_index, total_duration, warnings


def encode_timeline_mp4(
    frames_dir: Path,
    total_frames: int,
    duration_seconds: float,
    settings: RenderSettings,
    output_dir: Path,
    project_name: str,
    scene_results: list[dict[str, Any]] | None = None,
) -> tuple[str, str, list[str]]:
    ffmpeg = shutil.which("ffmpeg")
    mp4_path = output_dir / f"timeline_{project_name}_{int(time.time())}.mp4"
    audio_path = output_dir / f"timeline_{project_name}_{int(time.time())}.wav"
    warnings: list[str] = []
    if settings.pencil_audio:
        scene_mix: list[dict[str, Any]] = []
        transition_events: list[dict[str, Any]] = []
        cursor = 0.0
        for item in scene_results or []:
            scene = item["scene"]
            scene_duration = max(0.0, float(item["result"].get("duration_seconds", scene.duration_seconds)))
            scene_mix.append({
                "start_time": cursor,
                "end_time": cursor + scene_duration,
                "style_type": scene.style_type or item.get("style_type") or getattr(settings, "style_type", "pencil"),
                "ambient_track": scene.ambient_track or getattr(settings, "ambient_track", "none"),
                "ambient_level": getattr(settings, "ambient_level", 18),
                "drawing_level": getattr(settings, "drawing_audio_level", 70),
            })
            cursor += scene_duration
            if scene.transition != "cut":
                transition_events.append({"time": max(0.0, cursor - min(scene.transition_duration, 0.4)), "transition": scene.transition})
        generate_layered_audio(
            audio_path,
            max(0.1, duration_seconds),
            seed=settings.seed + 999,
            style_type=getattr(settings, "style_type", "pencil"),
            ambient_track=getattr(settings, "ambient_track", "none"),
            ambient_level=getattr(settings, "ambient_level", 18),
            drawing_level=getattr(settings, "drawing_audio_level", 70),
            transition_sfx=getattr(settings, "transition_sfx", True),
            transition_sfx_level=getattr(settings, "transition_sfx_level", 30),
            transition_events=transition_events,
            scene_mix=scene_mix,
        )
    if not ffmpeg:
        warnings.append("FFmpeg was not found on PATH. The stitched frame sequence was created, but MP4 export was skipped.")
        return "", str(audio_path) if audio_path.exists() else "", warnings
    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        str(settings.fps),
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
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=max(90, int(duration_seconds * 10)))
    if proc.returncode != 0:
        warnings.append("FFmpeg failed to encode the stitched timeline MP4.")
        warnings.append(proc.stderr[-1200:])
    return str(mp4_path) if mp4_path.exists() else "", str(audio_path) if audio_path.exists() else "", warnings


def render_multi_scene_timeline(
    upload_map: dict[str, bytes],
    timeline_json: str,
    base_settings: RenderSettings,
    output_dir: Path,
    project_name: str = "sketch_timeline",
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    filenames = list(upload_map.keys())
    scenes = parse_timeline_json(timeline_json, filenames)
    if not scenes:
        raise ValueError("The timeline does not contain any scenes.")

    scene_results: list[dict[str, Any]] = []
    warnings: list[str] = []
    total = len(scenes)
    for idx, scene in enumerate(scenes, start=1):
        if scene.source_name not in upload_map:
            raise ValueError(f"Scene '{scene.scene_id}' refers to source '{scene.source_name}', which was not uploaded.")
        if progress_callback:
            progress_callback(5 + (idx - 1) * 55 / max(1, total), f"Rendering scene {idx} of {total}: {scene.title or scene.source_name}")
        settings = copy.deepcopy(base_settings)
        settings.duration_seconds = scene.duration_seconds
        if scene.subject_type:
            settings.subject_type = scene.subject_type  # type: ignore[assignment]
        if scene.style_type:
            settings.style_type = scene.style_type  # type: ignore[assignment]
        if scene.planning_mode:
            settings.planning_mode = scene.planning_mode  # type: ignore[assignment]
        if scene.title:
            settings.title_card_text = scene.title
        if scene.camera_move_preset:
            settings.camera_move_preset = scene.camera_move_preset
        for key in ["camera_zoom_start", "camera_zoom_end", "camera_pan_start_x", "camera_pan_start_y", "camera_pan_end_x", "camera_pan_end_y"]:
            value = getattr(scene, key)
            if value is not None:
                setattr(settings, key, value)
        settings.seed = base_settings.seed + idx * 101
        image_bytes = upload_map[scene.source_name]
        plan, source, sketch = make_stroke_plan(image_bytes, settings)
        result = render_plan_to_mp4(plan, source, sketch, settings, output_dir)
        warnings.extend(plan.warnings + list(result.get("warnings", [])))
        scene_results.append({
            "scene": scene,
            "result": result,
            "stroke_count": len(plan.strokes),
            "subject_type": plan.subject_type,
            "style_type": settings.style_type,
        })

    if progress_callback:
        progress_callback(64, "Stitching scene frames into one timeline")
    stitched_frames_dir, total_frames, total_duration, stitch_warnings = stitch_scene_frames(scene_results, output_dir, base_settings, project_name)
    warnings.extend(stitch_warnings)

    if progress_callback:
        progress_callback(83, "Encoding final stitched MP4")
    mp4, audio, encode_warnings = encode_timeline_mp4(stitched_frames_dir, total_frames, total_duration, base_settings, output_dir, project_name, scene_results=scene_results)
    warnings.extend(encode_warnings)

    manifest_path = output_dir / f"timeline_{project_name}_{int(time.time())}_manifest.json"
    manifest_path.write_text(json.dumps({
        "project_name": project_name,
        "scene_count": len(scene_results),
        "total_frames": total_frames,
        "duration_seconds": round(total_duration, 3),
        "scenes": [
            {
                **item["scene"].to_dict(),
                "mp4": item["result"].get("mp4", ""),
                "preview": item["result"].get("preview", ""),
                "frames_dir": item["result"].get("frames_dir", ""),
                "subject_type_detected": item["subject_type"],
                "stroke_count": item["stroke_count"],
            }
            for item in scene_results
        ],
        "warnings": warnings,
    }, indent=2), encoding="utf-8")

    preview_path = scene_results[0]["result"].get("preview", "") if scene_results else ""
    if progress_callback:
        progress_callback(100, "Timeline render complete")
    return {
        "mp4": mp4,
        "audio": audio,
        "stitched_frames_dir": str(stitched_frames_dir),
        "manifest": str(manifest_path),
        "preview": preview_path,
        "duration_seconds": round(total_duration, 3),
        "frame_count": total_frames,
        "scene_count": len(scene_results),
        "warnings": warnings,
    }
