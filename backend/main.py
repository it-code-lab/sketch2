from __future__ import annotations

import json
import shutil
import time
import uuid
import zipfile
from pathlib import Path
from typing import Annotated, Any

import numpy as np
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.models import RenderSettings
from backend.services.asset_manager import list_hand_assets, save_hand_asset, resolve_hand_asset, update_asset_metadata
from backend.services.hand_presets import list_hand_presets, get_hand_preset
from backend.services.hand_tip_detector import detect_tip_from_asset_path
from backend.services.profile_store import list_profiles, get_profile, save_profile, delete_profile
from backend.services.job_store import JobStore
from backend.services.sketch_pipeline import image_to_data_url, make_stroke_plan
from backend.services.render_engine import render_plan_to_mp4
from backend.services.timeline_renderer import render_multi_scene_timeline
from backend.services.svg_tracer import maybe_trace_to_svg, tracer_status
from backend.services.art_director import analyze_image_bytes, analyze_timeline_images

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

jobs = JobStore()

app = FastAPI(
    title="AI Street Sketch Video Studio Backend",
    version="0.14.0",
    description="Photo/sketch to realistic street-artist stroke video renderer with AI-ready Art Director analysis, quality scoring, visual timeline editor, scene reordering, storyboard preview, multi-layer audio design, scene-based sound automation, camera moves, zoom/pan framing per scene, transition presets, multi-scene timeline stitching, pro render quality modes, advanced brush simulation, stroke-to-hand contact correction, saved user profiles, hand asset library, presets, automatic pencil-tip detection, centerline stroke extraction, transparent hand video overlay, calibration controls, and job queue.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_path = FRONTEND_DIR / "index.html"
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "0.14.0",
        "ffmpeg_found": shutil.which("ffmpeg") is not None,
        "tracing": tracer_status(),
        "hand_assets": len(list_hand_assets(ROOT)),
        "hand_presets": len(list_hand_presets()),
        "profiles": len(list_profiles(ROOT)),
        "timeline_rendering": True,
        "camera_presets": ["static", "zoom_in", "zoom_out", "pan_left_to_right", "pan_right_to_left", "pan_top_to_bottom", "pan_bottom_to_top", "ken_burns", "push_in_left", "push_in_right"],
        "transition_presets": ["cut", "fade", "dipblack", "wipe_left", "wipe_right", "zoomfade"],
        "ambient_tracks": ["none", "studio_room", "paper_rustle", "street_busker"],
        "timeline_editor": True,
        "art_director": True,
        "quality_scoring": True,
    }


@app.get("/api/assets/hand")
def hand_assets() -> dict[str, Any]:
    assets = list_hand_assets(ROOT)
    for asset in assets:
        asset["url"] = "/assets/" + str(asset["filename"])
    return {"assets": assets}


@app.get("/api/presets/hand")
def hand_presets() -> dict[str, Any]:
    return {"presets": list_hand_presets()}


@app.get("/api/profiles")
def profiles() -> dict[str, Any]:
    return {"profiles": list_profiles(ROOT)}


@app.get("/api/profiles/{name}")
def profile_detail(name: str) -> dict[str, Any]:
    profile = get_profile(ROOT, name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.post("/api/profiles")
async def profile_save(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    notes = str(payload.get("notes", "")).strip()
    settings = payload.get("settings", {})
    if not isinstance(settings, dict):
        raise HTTPException(status_code=400, detail="settings must be an object")
    try:
        saved = save_profile(ROOT, name, settings, notes=notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return saved


@app.delete("/api/profiles/{name}")
def profile_delete(name: str) -> dict[str, Any]:
    deleted = delete_profile(ROOT, name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"ok": True, "name": name}


@app.post("/api/hand/auto-tip")
async def hand_auto_tip(
    hand_asset: Annotated[UploadFile | None, File()] = None,
    asset_filename: Annotated[str, Form()] = "",
    hand_side: Annotated[str, Form()] = "right",
):
    asset_path = ""
    if hand_asset and hand_asset.filename:
        asset_path = await save_hand_asset(hand_asset, ROOT)
    elif asset_filename:
        asset_path = resolve_hand_asset(ROOT, asset_filename)
    else:
        raise HTTPException(status_code=400, detail="Provide a hand asset upload or an asset filename from the library.")
    detection = detect_tip_from_asset_path(asset_path, hand_side=hand_side or "right")
    detection["asset_name"] = Path(asset_path).name
    update_asset_metadata(ROOT, Path(asset_path).name, {
        "last_detected_tip_x": detection["tip_x"],
        "last_detected_tip_y": detection["tip_y"],
        "hand_side": hand_side or "right",
    })
    return detection




@app.post("/api/art-director/analyze")
async def art_director_analyze(file: Annotated[UploadFile, File()]):
    data = await read_upload_image(file)
    return analyze_image_bytes(data, file.filename or "image.png")


@app.post("/api/art-director/timeline")
async def art_director_timeline(files: Annotated[list[UploadFile], File()]):
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one image.")
    rows: list[tuple[str, bytes]] = []
    for upload in files:
        rows.append((upload.filename or f"scene_{len(rows)+1}.png", await read_upload_image(upload)))
    return analyze_timeline_images(rows)


async def read_upload_image(file: UploadFile) -> bytes:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image is too large. Please use an image under 25 MB.")
    return data


def form_to_settings(**values: Any) -> RenderSettings:
    return RenderSettings.from_form(values)


def apply_hand_preset(settings: RenderSettings) -> RenderSettings:
    if not settings.hand_preset:
        return settings
    preset = get_hand_preset(settings.hand_preset)
    if not preset:
        return settings
    for key, value in preset.items():
        if key in {"id", "name", "notes", "camera_angle", "style_type"}:
            continue
        if hasattr(settings, key):
            setattr(settings, key, value)
    # Style in preset can nudge the drawing style only when user leaves it at default-like value.
    if preset.get("style_type") and settings.style_type == "pencil":
        settings.style_type = preset["style_type"]
    return settings


def public_result(result: dict[str, Any]) -> dict[str, str]:
    public: dict[str, str] = {}
    for key in ["mp4", "plan", "preview", "svg", "manifest", "audio"]:
        value = result.get(key)
        if value:
            public[key] = "/outputs/" + Path(str(value)).name
    return public


def run_render_job(job_id: str, image_bytes: bytes, settings: RenderSettings) -> None:
    try:
        jobs.update(job_id, status="analyzing", progress=4, message="Analyzing sketch and planning human-like stroke order")
        plan, source, sketch = make_stroke_plan(image_bytes, settings)
        trace_result = None
        if settings.trace_mode != "opencv":
            trace_result = maybe_trace_to_svg(np.array(sketch.convert("L")), settings.trace_mode, OUTPUT_DIR, job_id)
            if trace_result.warnings:
                plan.warnings.extend(trace_result.warnings)

        def progress(value: float, message: str) -> None:
            jobs.update(job_id, status="rendering" if value < 88 else "encoding", progress=value, message=message)

        result = render_plan_to_mp4(plan, source, sketch, settings, OUTPUT_DIR, progress_callback=progress)
        if trace_result and trace_result.svg_path:
            result["svg"] = trace_result.svg_path
        payload = {
            "job_id": result["job_id"],
            "stroke_count": len(plan.strokes),
            "duration_seconds": result["duration_seconds"],
            "frame_count": result["frame_count"],
            "files": public_result(result),
            "warnings": plan.warnings + list(result.get("warnings", [])),
            "pass_summary": plan.pass_summary,
            "art_director": plan.art_director,
            "semantic_regions": plan.semantic_regions,
            "layer_plan": plan.layer_plan,
        }
        jobs.update(job_id, status="done", progress=100, message="Render complete", result=payload)
    except Exception as exc:
        jobs.update(job_id, status="failed", progress=100, message="Render failed", error=str(exc))


def run_timeline_render_job(job_id: str, upload_map: dict[str, bytes], timeline_json: str, settings: RenderSettings, project_name: str) -> None:
    try:
        jobs.update(job_id, status="timeline", progress=3, message="Preparing multi-scene timeline")

        def progress(value: float, message: str) -> None:
            state = "timeline" if value < 80 else "encoding"
            jobs.update(job_id, status=state, progress=value, message=message)

        result = render_multi_scene_timeline(upload_map, timeline_json, settings, OUTPUT_DIR, project_name=project_name, progress_callback=progress)
        payload = {
            "scene_count": result["scene_count"],
            "duration_seconds": result["duration_seconds"],
            "frame_count": result["frame_count"],
            "files": public_result(result),
            "warnings": list(result.get("warnings", [])),
            "timeline": True,
        }
        jobs.update(job_id, status="done", progress=100, message="Timeline render complete", result=payload)
    except Exception as exc:
        jobs.update(job_id, status="failed", progress=100, message="Timeline render failed", error=str(exc))


# This function keeps the endpoint signatures readable while still exposing every premium setting.
def values_to_settings(
    input_type: str,
    subject_type: str,
    style_type: str,
    ratio: str,
    render_quality: str,
    sketch_strength: int,
    stroke_density: int,
    human_randomness: int,
    duration_seconds: int,
    fps: int,
    max_strokes: int,
    paper_texture: bool,
    construction_pass: bool,
    accent_pass: bool,
    hand_overlay: bool,
    pencil_audio: bool,
    seed: int,
    trace_mode: str,
    stroke_extraction_mode: str,
    planning_mode: str,
    art_director_json: str,
    camera_motion: bool,
    camera_move_preset: str,
    camera_zoom_start: int,
    camera_zoom_end: int,
    camera_pan_start_x: int,
    camera_pan_start_y: int,
    camera_pan_end_x: int,
    camera_pan_end_y: int,
    smudge_pass: bool,
    eraser_pass: bool,
    target_reveal: bool,
    target_reveal_strength: int,
    title_card_text: str,
    watermark_text: str,
    hand_mode: str,
    hand_preset: str,
    hand_side: str,
    hand_asset_filename: str,
    hand_scale: int,
    hand_opacity: int,
    hand_rotation: int,
    hand_tip_x: int,
    hand_tip_y: int,
    hand_video_loop: bool = True,
    hand_video_playback_rate: int = 100,
    hand_video_frame_offset: int = 0,
    hand_video_chroma_key: bool = False,
    hand_lift_px: int = 14,
    hand_shadow_strength: int = 70,
    contact_correction_strength: int = 72,
    contact_position_smoothing: int = 58,
    reposition_arc_strength: int = 55,
    graphite_grain: int = 65,
    charcoal_dust: int = 55,
    ink_bleed: int = 28,
    marker_overlap: int = 42,
    stroke_taper: int = 58,
    motion_blur_strength: int = 14,
    ambient_track: str = "none",
    ambient_level: int = 18,
    drawing_audio_level: int = 70,
    transition_sfx: bool = True,
    transition_sfx_level: int = 30,
) -> RenderSettings:
    return form_to_settings(
        input_type=input_type,
        subject_type=subject_type,
        style_type=style_type,
        ratio=ratio,
        render_quality=render_quality,
        sketch_strength=sketch_strength,
        stroke_density=stroke_density,
        human_randomness=human_randomness,
        duration_seconds=duration_seconds,
        fps=fps,
        max_strokes=max_strokes,
        paper_texture=paper_texture,
        construction_pass=construction_pass,
        accent_pass=accent_pass,
        hand_overlay=hand_overlay,
        pencil_audio=pencil_audio,
        seed=seed,
        trace_mode=trace_mode,
        stroke_extraction_mode=stroke_extraction_mode,
        planning_mode=planning_mode,
        art_director_json=art_director_json,
        camera_motion=camera_motion,
        camera_move_preset=camera_move_preset,
        camera_zoom_start=camera_zoom_start,
        camera_zoom_end=camera_zoom_end,
        camera_pan_start_x=camera_pan_start_x,
        camera_pan_start_y=camera_pan_start_y,
        camera_pan_end_x=camera_pan_end_x,
        camera_pan_end_y=camera_pan_end_y,
        smudge_pass=smudge_pass,
        eraser_pass=eraser_pass,
        target_reveal=target_reveal,
        target_reveal_strength=target_reveal_strength,
        title_card_text=title_card_text,
        watermark_text=watermark_text,
        hand_mode=hand_mode,
        hand_preset=hand_preset,
        hand_side=hand_side,
        hand_asset_filename=hand_asset_filename,
        hand_scale=hand_scale,
        hand_opacity=hand_opacity,
        hand_rotation=hand_rotation,
        hand_tip_x=hand_tip_x,
        hand_tip_y=hand_tip_y,
        hand_video_loop=hand_video_loop,
        hand_video_playback_rate=hand_video_playback_rate,
        hand_video_frame_offset=hand_video_frame_offset,
        hand_video_chroma_key=hand_video_chroma_key,
        hand_lift_px=hand_lift_px,
        hand_shadow_strength=hand_shadow_strength,
        contact_correction_strength=contact_correction_strength,
        contact_position_smoothing=contact_position_smoothing,
        reposition_arc_strength=reposition_arc_strength,
        graphite_grain=graphite_grain,
        charcoal_dust=charcoal_dust,
        ink_bleed=ink_bleed,
        marker_overlap=marker_overlap,
        stroke_taper=stroke_taper,
        motion_blur_strength=motion_blur_strength,
        ambient_track=ambient_track,
        ambient_level=ambient_level,
        drawing_audio_level=drawing_audio_level,
        transition_sfx=transition_sfx,
        transition_sfx_level=transition_sfx_level,
    )


@app.post("/api/analyze")
async def analyze(
    file: Annotated[UploadFile, File()],
    input_type: Annotated[str, Form()] = "photo",
    subject_type: Annotated[str, Form()] = "auto",
    style_type: Annotated[str, Form()] = "pencil",
    ratio: Annotated[str, Form()] = "9:16",
    render_quality: Annotated[str, Form()] = "standard",
    sketch_strength: Annotated[int, Form()] = 70,
    stroke_density: Annotated[int, Form()] = 60,
    human_randomness: Annotated[int, Form()] = 35,
    duration_seconds: Annotated[int, Form()] = 18,
    fps: Annotated[int, Form()] = 24,
    max_strokes: Annotated[int, Form()] = 1800,
    paper_texture: Annotated[bool, Form()] = True,
    construction_pass: Annotated[bool, Form()] = True,
    accent_pass: Annotated[bool, Form()] = True,
    hand_overlay: Annotated[bool, Form()] = True,
    pencil_audio: Annotated[bool, Form()] = True,
    seed: Annotated[int, Form()] = 12345,
    trace_mode: Annotated[str, Form()] = "opencv",
    stroke_extraction_mode: Annotated[str, Form()] = "hybrid",
    planning_mode: Annotated[str, Form()] = "rule",
    art_director_json: Annotated[str, Form()] = "",
    camera_motion: Annotated[bool, Form()] = True,
    camera_move_preset: Annotated[str, Form()] = "static",
    camera_zoom_start: Annotated[int, Form()] = 100,
    camera_zoom_end: Annotated[int, Form()] = 100,
    camera_pan_start_x: Annotated[int, Form()] = 0,
    camera_pan_start_y: Annotated[int, Form()] = 0,
    camera_pan_end_x: Annotated[int, Form()] = 0,
    camera_pan_end_y: Annotated[int, Form()] = 0,
    smudge_pass: Annotated[bool, Form()] = True,
    eraser_pass: Annotated[bool, Form()] = False,
    target_reveal: Annotated[bool, Form()] = False,
    target_reveal_strength: Annotated[int, Form()] = 85,
    title_card_text: Annotated[str, Form()] = "",
    watermark_text: Annotated[str, Form()] = "",
    hand_mode: Annotated[str, Form()] = "procedural",
    hand_preset: Annotated[str, Form()] = "",
    hand_side: Annotated[str, Form()] = "right",
    hand_asset_filename: Annotated[str, Form()] = "",
    hand_scale: Annotated[int, Form()] = 32,
    hand_opacity: Annotated[int, Form()] = 95,
    hand_rotation: Annotated[int, Form()] = -18,
    hand_tip_x: Annotated[int, Form()] = 18,
    hand_tip_y: Annotated[int, Form()] = 78,
    hand_video_loop: Annotated[bool, Form()] = True,
    hand_video_playback_rate: Annotated[int, Form()] = 100,
    hand_video_frame_offset: Annotated[int, Form()] = 0,
    hand_video_chroma_key: Annotated[bool, Form()] = False,
    hand_lift_px: Annotated[int, Form()] = 14,
    hand_shadow_strength: Annotated[int, Form()] = 70,
    contact_correction_strength: Annotated[int, Form()] = 72,
    contact_position_smoothing: Annotated[int, Form()] = 58,
    reposition_arc_strength: Annotated[int, Form()] = 55,
    graphite_grain: Annotated[int, Form()] = 65,
    charcoal_dust: Annotated[int, Form()] = 55,
    ink_bleed: Annotated[int, Form()] = 28,
    marker_overlap: Annotated[int, Form()] = 42,
    stroke_taper: Annotated[int, Form()] = 58,
    motion_blur_strength: Annotated[int, Form()] = 14,
    ambient_track: Annotated[str, Form()] = "none",
    ambient_level: Annotated[int, Form()] = 18,
    drawing_audio_level: Annotated[int, Form()] = 70,
    transition_sfx: Annotated[bool, Form()] = True,
    transition_sfx_level: Annotated[int, Form()] = 30,
):
    image_bytes = await read_upload_image(file)
    settings = values_to_settings(
        input_type, subject_type, style_type, ratio, render_quality, sketch_strength, stroke_density, human_randomness,
        duration_seconds, fps, max_strokes, paper_texture, construction_pass, accent_pass, hand_overlay,
        pencil_audio, seed, trace_mode, stroke_extraction_mode, planning_mode, art_director_json, camera_motion, camera_move_preset, camera_zoom_start, camera_zoom_end, camera_pan_start_x, camera_pan_start_y, camera_pan_end_x, camera_pan_end_y, smudge_pass,
        eraser_pass, target_reveal, target_reveal_strength, title_card_text, watermark_text, hand_mode, hand_preset, hand_side, hand_asset_filename, hand_scale, hand_opacity, hand_rotation,
        hand_tip_x, hand_tip_y, hand_video_loop, hand_video_playback_rate, hand_video_frame_offset,
        hand_video_chroma_key, hand_lift_px, hand_shadow_strength, contact_correction_strength, contact_position_smoothing, reposition_arc_strength,
        graphite_grain, charcoal_dust, ink_bleed, marker_overlap, stroke_taper, motion_blur_strength, ambient_track, ambient_level, drawing_audio_level, transition_sfx, transition_sfx_level,
    )
    settings = apply_hand_preset(settings)
    if not settings.hand_asset_path and hand_asset_filename and hand_mode in {"uploaded", "video"}:
        settings.hand_asset_path = resolve_hand_asset(ROOT, hand_asset_filename)
    plan, source, sketch = make_stroke_plan(image_bytes, settings)
    return JSONResponse({
        "plan": plan.to_dict(include_strokes=True),
        "source_preview": image_to_data_url(source),
        "sketch_preview": image_to_data_url(sketch),
        "health": health(),
    })


@app.post("/api/render")
async def render(
    file: Annotated[UploadFile, File()],
    hand_asset: Annotated[UploadFile | None, File()] = None,
    input_type: Annotated[str, Form()] = "photo",
    subject_type: Annotated[str, Form()] = "auto",
    style_type: Annotated[str, Form()] = "pencil",
    ratio: Annotated[str, Form()] = "9:16",
    render_quality: Annotated[str, Form()] = "standard",
    sketch_strength: Annotated[int, Form()] = 70,
    stroke_density: Annotated[int, Form()] = 60,
    human_randomness: Annotated[int, Form()] = 35,
    duration_seconds: Annotated[int, Form()] = 18,
    fps: Annotated[int, Form()] = 24,
    max_strokes: Annotated[int, Form()] = 1800,
    paper_texture: Annotated[bool, Form()] = True,
    construction_pass: Annotated[bool, Form()] = True,
    accent_pass: Annotated[bool, Form()] = True,
    hand_overlay: Annotated[bool, Form()] = True,
    pencil_audio: Annotated[bool, Form()] = True,
    seed: Annotated[int, Form()] = 12345,
    trace_mode: Annotated[str, Form()] = "opencv",
    stroke_extraction_mode: Annotated[str, Form()] = "hybrid",
    planning_mode: Annotated[str, Form()] = "rule",
    art_director_json: Annotated[str, Form()] = "",
    camera_motion: Annotated[bool, Form()] = True,
    camera_move_preset: Annotated[str, Form()] = "static",
    camera_zoom_start: Annotated[int, Form()] = 100,
    camera_zoom_end: Annotated[int, Form()] = 100,
    camera_pan_start_x: Annotated[int, Form()] = 0,
    camera_pan_start_y: Annotated[int, Form()] = 0,
    camera_pan_end_x: Annotated[int, Form()] = 0,
    camera_pan_end_y: Annotated[int, Form()] = 0,
    smudge_pass: Annotated[bool, Form()] = True,
    eraser_pass: Annotated[bool, Form()] = False,
    target_reveal: Annotated[bool, Form()] = False,
    target_reveal_strength: Annotated[int, Form()] = 85,
    title_card_text: Annotated[str, Form()] = "",
    watermark_text: Annotated[str, Form()] = "",
    hand_mode: Annotated[str, Form()] = "procedural",
    hand_preset: Annotated[str, Form()] = "",
    hand_side: Annotated[str, Form()] = "right",
    hand_asset_filename: Annotated[str, Form()] = "",
    hand_scale: Annotated[int, Form()] = 32,
    hand_opacity: Annotated[int, Form()] = 95,
    hand_rotation: Annotated[int, Form()] = -18,
    hand_tip_x: Annotated[int, Form()] = 18,
    hand_tip_y: Annotated[int, Form()] = 78,
    hand_video_loop: Annotated[bool, Form()] = True,
    hand_video_playback_rate: Annotated[int, Form()] = 100,
    hand_video_frame_offset: Annotated[int, Form()] = 0,
    hand_video_chroma_key: Annotated[bool, Form()] = False,
    hand_lift_px: Annotated[int, Form()] = 14,
    hand_shadow_strength: Annotated[int, Form()] = 70,
    contact_correction_strength: Annotated[int, Form()] = 72,
    contact_position_smoothing: Annotated[int, Form()] = 58,
    reposition_arc_strength: Annotated[int, Form()] = 55,
    graphite_grain: Annotated[int, Form()] = 65,
    charcoal_dust: Annotated[int, Form()] = 55,
    ink_bleed: Annotated[int, Form()] = 28,
    marker_overlap: Annotated[int, Form()] = 42,
    stroke_taper: Annotated[int, Form()] = 58,
    motion_blur_strength: Annotated[int, Form()] = 14,
    ambient_track: Annotated[str, Form()] = "none",
    ambient_level: Annotated[int, Form()] = 18,
    drawing_audio_level: Annotated[int, Form()] = 70,
    transition_sfx: Annotated[bool, Form()] = True,
    transition_sfx_level: Annotated[int, Form()] = 30,
):
    image_bytes = await read_upload_image(file)
    settings = values_to_settings(
        input_type, subject_type, style_type, ratio, render_quality, sketch_strength, stroke_density, human_randomness,
        duration_seconds, fps, max_strokes, paper_texture, construction_pass, accent_pass, hand_overlay,
        pencil_audio, seed, trace_mode, stroke_extraction_mode, planning_mode, art_director_json, camera_motion, camera_move_preset, camera_zoom_start, camera_zoom_end, camera_pan_start_x, camera_pan_start_y, camera_pan_end_x, camera_pan_end_y, smudge_pass,
        eraser_pass, target_reveal, target_reveal_strength, title_card_text, watermark_text, hand_mode, hand_preset, hand_side, hand_asset_filename, hand_scale, hand_opacity, hand_rotation,
        hand_tip_x, hand_tip_y, hand_video_loop, hand_video_playback_rate, hand_video_frame_offset,
        hand_video_chroma_key, hand_lift_px, hand_shadow_strength, contact_correction_strength, contact_position_smoothing, reposition_arc_strength,
        graphite_grain, charcoal_dust, ink_bleed, marker_overlap, stroke_taper, motion_blur_strength, ambient_track, ambient_level, drawing_audio_level, transition_sfx, transition_sfx_level,
    )
    settings = apply_hand_preset(settings)
    if hand_asset and hand_mode in {"uploaded", "video"}:
        settings.hand_asset_path = await save_hand_asset(hand_asset, ROOT)
    elif hand_asset_filename and hand_mode in {"uploaded", "video"}:
        settings.hand_asset_path = resolve_hand_asset(ROOT, hand_asset_filename)
    plan, source, sketch = make_stroke_plan(image_bytes, settings)
    trace_result = None
    if settings.trace_mode != "opencv":
        trace_result = maybe_trace_to_svg(np.array(sketch.convert("L")), settings.trace_mode, OUTPUT_DIR, f"sync_{settings.seed}_{int(time.time())}")
        if trace_result.warnings:
            plan.warnings.extend(trace_result.warnings)
    result = render_plan_to_mp4(plan, source, sketch, settings, OUTPUT_DIR)
    if trace_result and trace_result.svg_path:
        result["svg"] = trace_result.svg_path
    return JSONResponse({
        "job_id": result["job_id"],
        "stroke_count": len(plan.strokes),
        "duration_seconds": result["duration_seconds"],
        "frame_count": result["frame_count"],
        "files": public_result(result),
        "warnings": plan.warnings + list(result.get("warnings", [])),
        "pass_summary": plan.pass_summary,
        "art_director": plan.art_director,
        "semantic_regions": plan.semantic_regions,
        "layer_plan": plan.layer_plan,
    })


@app.post("/api/render-queued")
async def render_queued(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    hand_asset: Annotated[UploadFile | None, File()] = None,
    input_type: Annotated[str, Form()] = "photo",
    subject_type: Annotated[str, Form()] = "auto",
    style_type: Annotated[str, Form()] = "pencil",
    ratio: Annotated[str, Form()] = "9:16",
    render_quality: Annotated[str, Form()] = "standard",
    sketch_strength: Annotated[int, Form()] = 70,
    stroke_density: Annotated[int, Form()] = 60,
    human_randomness: Annotated[int, Form()] = 35,
    duration_seconds: Annotated[int, Form()] = 18,
    fps: Annotated[int, Form()] = 24,
    max_strokes: Annotated[int, Form()] = 1800,
    paper_texture: Annotated[bool, Form()] = True,
    construction_pass: Annotated[bool, Form()] = True,
    accent_pass: Annotated[bool, Form()] = True,
    hand_overlay: Annotated[bool, Form()] = True,
    pencil_audio: Annotated[bool, Form()] = True,
    seed: Annotated[int, Form()] = 12345,
    trace_mode: Annotated[str, Form()] = "opencv",
    stroke_extraction_mode: Annotated[str, Form()] = "hybrid",
    planning_mode: Annotated[str, Form()] = "rule",
    art_director_json: Annotated[str, Form()] = "",
    camera_motion: Annotated[bool, Form()] = True,
    camera_move_preset: Annotated[str, Form()] = "static",
    camera_zoom_start: Annotated[int, Form()] = 100,
    camera_zoom_end: Annotated[int, Form()] = 100,
    camera_pan_start_x: Annotated[int, Form()] = 0,
    camera_pan_start_y: Annotated[int, Form()] = 0,
    camera_pan_end_x: Annotated[int, Form()] = 0,
    camera_pan_end_y: Annotated[int, Form()] = 0,
    smudge_pass: Annotated[bool, Form()] = True,
    eraser_pass: Annotated[bool, Form()] = False,
    target_reveal: Annotated[bool, Form()] = False,
    target_reveal_strength: Annotated[int, Form()] = 85,
    title_card_text: Annotated[str, Form()] = "",
    watermark_text: Annotated[str, Form()] = "",
    hand_mode: Annotated[str, Form()] = "procedural",
    hand_preset: Annotated[str, Form()] = "",
    hand_side: Annotated[str, Form()] = "right",
    hand_asset_filename: Annotated[str, Form()] = "",
    hand_scale: Annotated[int, Form()] = 32,
    hand_opacity: Annotated[int, Form()] = 95,
    hand_rotation: Annotated[int, Form()] = -18,
    hand_tip_x: Annotated[int, Form()] = 18,
    hand_tip_y: Annotated[int, Form()] = 78,
    hand_video_loop: Annotated[bool, Form()] = True,
    hand_video_playback_rate: Annotated[int, Form()] = 100,
    hand_video_frame_offset: Annotated[int, Form()] = 0,
    hand_video_chroma_key: Annotated[bool, Form()] = False,
    hand_lift_px: Annotated[int, Form()] = 14,
    hand_shadow_strength: Annotated[int, Form()] = 70,
    contact_correction_strength: Annotated[int, Form()] = 72,
    contact_position_smoothing: Annotated[int, Form()] = 58,
    reposition_arc_strength: Annotated[int, Form()] = 55,
    graphite_grain: Annotated[int, Form()] = 65,
    charcoal_dust: Annotated[int, Form()] = 55,
    ink_bleed: Annotated[int, Form()] = 28,
    marker_overlap: Annotated[int, Form()] = 42,
    stroke_taper: Annotated[int, Form()] = 58,
    motion_blur_strength: Annotated[int, Form()] = 14,
    ambient_track: Annotated[str, Form()] = "none",
    ambient_level: Annotated[int, Form()] = 18,
    drawing_audio_level: Annotated[int, Form()] = 70,
    transition_sfx: Annotated[bool, Form()] = True,
    transition_sfx_level: Annotated[int, Form()] = 30,
):
    image_bytes = await read_upload_image(file)
    settings = values_to_settings(
        input_type, subject_type, style_type, ratio, render_quality, sketch_strength, stroke_density, human_randomness,
        duration_seconds, fps, max_strokes, paper_texture, construction_pass, accent_pass, hand_overlay,
        pencil_audio, seed, trace_mode, stroke_extraction_mode, planning_mode, art_director_json, camera_motion, camera_move_preset, camera_zoom_start, camera_zoom_end, camera_pan_start_x, camera_pan_start_y, camera_pan_end_x, camera_pan_end_y, smudge_pass,
        eraser_pass, target_reveal, target_reveal_strength, title_card_text, watermark_text, hand_mode, hand_preset, hand_side, hand_asset_filename, hand_scale, hand_opacity, hand_rotation,
        hand_tip_x, hand_tip_y, hand_video_loop, hand_video_playback_rate, hand_video_frame_offset,
        hand_video_chroma_key, hand_lift_px, hand_shadow_strength, contact_correction_strength, contact_position_smoothing, reposition_arc_strength,
        graphite_grain, charcoal_dust, ink_bleed, marker_overlap, stroke_taper, motion_blur_strength, ambient_track, ambient_level, drawing_audio_level, transition_sfx, transition_sfx_level,
    )
    settings = apply_hand_preset(settings)
    if hand_asset and hand_mode in {"uploaded", "video"}:
        settings.hand_asset_path = await save_hand_asset(hand_asset, ROOT)
    elif hand_asset_filename and hand_mode in {"uploaded", "video"}:
        settings.hand_asset_path = resolve_hand_asset(ROOT, hand_asset_filename)
    job_id = f"queued_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    jobs.create(job_id)
    background_tasks.add_task(run_render_job, job_id, image_bytes, settings)
    return JSONResponse({"job_id": job_id, "status_url": f"/api/jobs/{job_id}"})


@app.post("/api/timeline/render-queued")
async def render_timeline_queued(
    background_tasks: BackgroundTasks,
    files: Annotated[list[UploadFile], File()],
    timeline_json: Annotated[str, Form()] = "",
    project_name: Annotated[str, Form()] = "sketch_timeline",
    input_type: Annotated[str, Form()] = "photo",
    subject_type: Annotated[str, Form()] = "auto",
    style_type: Annotated[str, Form()] = "pencil",
    ratio: Annotated[str, Form()] = "9:16",
    render_quality: Annotated[str, Form()] = "standard",
    sketch_strength: Annotated[int, Form()] = 70,
    stroke_density: Annotated[int, Form()] = 60,
    human_randomness: Annotated[int, Form()] = 35,
    duration_seconds: Annotated[int, Form()] = 18,
    fps: Annotated[int, Form()] = 24,
    max_strokes: Annotated[int, Form()] = 1800,
    paper_texture: Annotated[bool, Form()] = True,
    construction_pass: Annotated[bool, Form()] = True,
    accent_pass: Annotated[bool, Form()] = True,
    hand_overlay: Annotated[bool, Form()] = True,
    pencil_audio: Annotated[bool, Form()] = True,
    seed: Annotated[int, Form()] = 12345,
    trace_mode: Annotated[str, Form()] = "opencv",
    stroke_extraction_mode: Annotated[str, Form()] = "hybrid",
    planning_mode: Annotated[str, Form()] = "rule",
    art_director_json: Annotated[str, Form()] = "",
    camera_motion: Annotated[bool, Form()] = True,
    camera_move_preset: Annotated[str, Form()] = "static",
    camera_zoom_start: Annotated[int, Form()] = 100,
    camera_zoom_end: Annotated[int, Form()] = 100,
    camera_pan_start_x: Annotated[int, Form()] = 0,
    camera_pan_start_y: Annotated[int, Form()] = 0,
    camera_pan_end_x: Annotated[int, Form()] = 0,
    camera_pan_end_y: Annotated[int, Form()] = 0,
    smudge_pass: Annotated[bool, Form()] = True,
    eraser_pass: Annotated[bool, Form()] = False,
    target_reveal: Annotated[bool, Form()] = False,
    target_reveal_strength: Annotated[int, Form()] = 85,
    title_card_text: Annotated[str, Form()] = "",
    watermark_text: Annotated[str, Form()] = "",
    hand_mode: Annotated[str, Form()] = "procedural",
    hand_preset: Annotated[str, Form()] = "",
    hand_side: Annotated[str, Form()] = "right",
    hand_asset_filename: Annotated[str, Form()] = "",
    hand_scale: Annotated[int, Form()] = 32,
    hand_opacity: Annotated[int, Form()] = 95,
    hand_rotation: Annotated[int, Form()] = -18,
    hand_tip_x: Annotated[int, Form()] = 18,
    hand_tip_y: Annotated[int, Form()] = 78,
    hand_video_loop: Annotated[bool, Form()] = True,
    hand_video_playback_rate: Annotated[int, Form()] = 100,
    hand_video_frame_offset: Annotated[int, Form()] = 0,
    hand_video_chroma_key: Annotated[bool, Form()] = False,
    hand_lift_px: Annotated[int, Form()] = 14,
    hand_shadow_strength: Annotated[int, Form()] = 70,
    contact_correction_strength: Annotated[int, Form()] = 72,
    contact_position_smoothing: Annotated[int, Form()] = 58,
    reposition_arc_strength: Annotated[int, Form()] = 55,
    graphite_grain: Annotated[int, Form()] = 65,
    charcoal_dust: Annotated[int, Form()] = 55,
    ink_bleed: Annotated[int, Form()] = 28,
    marker_overlap: Annotated[int, Form()] = 42,
    stroke_taper: Annotated[int, Form()] = 58,
    motion_blur_strength: Annotated[int, Form()] = 14,
    ambient_track: Annotated[str, Form()] = "none",
    ambient_level: Annotated[int, Form()] = 18,
    drawing_audio_level: Annotated[int, Form()] = 70,
    transition_sfx: Annotated[bool, Form()] = True,
    transition_sfx_level: Annotated[int, Form()] = 30,
    hand_asset: Annotated[UploadFile | None, File()] = None,
):
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one image for the timeline.")
    upload_map: dict[str, bytes] = {}
    for file in files:
        upload_map[file.filename or f"scene_{len(upload_map)+1}.png"] = await read_upload_image(file)
    settings = values_to_settings(
        input_type, subject_type, style_type, ratio, render_quality, sketch_strength, stroke_density, human_randomness,
        duration_seconds, fps, max_strokes, paper_texture, construction_pass, accent_pass, hand_overlay,
        pencil_audio, seed, trace_mode, stroke_extraction_mode, planning_mode, art_director_json, camera_motion, camera_move_preset, camera_zoom_start, camera_zoom_end, camera_pan_start_x, camera_pan_start_y, camera_pan_end_x, camera_pan_end_y, smudge_pass,
        eraser_pass, target_reveal, target_reveal_strength, title_card_text, watermark_text, hand_mode, hand_preset, hand_side, hand_asset_filename, hand_scale, hand_opacity, hand_rotation,
        hand_tip_x, hand_tip_y, hand_video_loop, hand_video_playback_rate, hand_video_frame_offset,
        hand_video_chroma_key, hand_lift_px, hand_shadow_strength, contact_correction_strength, contact_position_smoothing, reposition_arc_strength,
        graphite_grain, charcoal_dust, ink_bleed, marker_overlap, stroke_taper, motion_blur_strength, ambient_track, ambient_level, drawing_audio_level, transition_sfx, transition_sfx_level,
    )
    settings = apply_hand_preset(settings)
    if hand_asset and hand_mode in {"uploaded", "video"}:
        settings.hand_asset_path = await save_hand_asset(hand_asset, ROOT)
    elif hand_asset_filename and hand_mode in {"uploaded", "video"}:
        settings.hand_asset_path = resolve_hand_asset(ROOT, hand_asset_filename)
    job_id = f"timeline_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    jobs.create(job_id)
    background_tasks.add_task(run_timeline_render_job, job_id, upload_map, timeline_json, settings, project_name.strip() or "sketch_timeline")
    return JSONResponse({"job_id": job_id, "status_url": f"/api/jobs/{job_id}"})


@app.get("/api/jobs")
def list_jobs() -> dict[str, Any]:
    return {"jobs": jobs.recent()}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> JSONResponse:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(job.to_dict())


@app.post("/api/batch-render")
async def batch_render(
    files: Annotated[list[UploadFile], File()],
    input_type: Annotated[str, Form()] = "photo",
    subject_type: Annotated[str, Form()] = "auto",
    style_type: Annotated[str, Form()] = "pencil",
    ratio: Annotated[str, Form()] = "9:16",
    render_quality: Annotated[str, Form()] = "standard",
    sketch_strength: Annotated[int, Form()] = 70,
    stroke_density: Annotated[int, Form()] = 55,
    human_randomness: Annotated[int, Form()] = 35,
    duration_seconds: Annotated[int, Form()] = 12,
    fps: Annotated[int, Form()] = 24,
    max_strokes: Annotated[int, Form()] = 1300,
    paper_texture: Annotated[bool, Form()] = True,
    construction_pass: Annotated[bool, Form()] = True,
    accent_pass: Annotated[bool, Form()] = True,
    hand_overlay: Annotated[bool, Form()] = True,
    pencil_audio: Annotated[bool, Form()] = True,
    seed: Annotated[int, Form()] = 12345,
    trace_mode: Annotated[str, Form()] = "opencv",
    stroke_extraction_mode: Annotated[str, Form()] = "hybrid",
    planning_mode: Annotated[str, Form()] = "rule",
    art_director_json: Annotated[str, Form()] = "",
    camera_motion: Annotated[bool, Form()] = True,
    camera_move_preset: Annotated[str, Form()] = "static",
    camera_zoom_start: Annotated[int, Form()] = 100,
    camera_zoom_end: Annotated[int, Form()] = 100,
    camera_pan_start_x: Annotated[int, Form()] = 0,
    camera_pan_start_y: Annotated[int, Form()] = 0,
    camera_pan_end_x: Annotated[int, Form()] = 0,
    camera_pan_end_y: Annotated[int, Form()] = 0,
    smudge_pass: Annotated[bool, Form()] = True,
    eraser_pass: Annotated[bool, Form()] = False,
    title_card_text: Annotated[str, Form()] = "",
    watermark_text: Annotated[str, Form()] = "",
):
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one image.")
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Batch render currently supports up to 20 images at a time.")

    settings = values_to_settings(
        input_type, subject_type, style_type, ratio, render_quality, sketch_strength, stroke_density, human_randomness,
        duration_seconds, fps, max_strokes, paper_texture, construction_pass, accent_pass, hand_overlay,
        pencil_audio, seed, trace_mode, stroke_extraction_mode, planning_mode, art_director_json, camera_motion, camera_move_preset, camera_zoom_start, camera_zoom_end, camera_pan_start_x, camera_pan_start_y, camera_pan_end_x, camera_pan_end_y, smudge_pass,
        eraser_pass, title_card_text, watermark_text, "procedural", "", "right", "", 32, 95, -18, 18, 78, True, 100, 0, False, 14, 70, 72, 58, 55, 65, 55, 28, 42, 58, 14, ambient_track, ambient_level, drawing_audio_level, transition_sfx, transition_sfx_level,
    )
    zip_path = OUTPUT_DIR / f"batch_sketch_videos_{seed}_{int(time.time())}.zip"
    rendered = []
    warnings = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, upload in enumerate(files, start=1):
            image_bytes = await read_upload_image(upload)
            settings.seed = seed + idx
            plan, source, sketch = make_stroke_plan(image_bytes, settings)
            result = render_plan_to_mp4(plan, source, sketch, settings, OUTPUT_DIR)
            warnings.extend(plan.warnings + list(result.get("warnings", [])))
            if result.get("mp4") and Path(str(result["mp4"])).exists():
                arcname = f"{idx:02d}_{Path(upload.filename or 'sketch').stem}.mp4"
                zf.write(str(result["mp4"]), arcname)
                rendered.append(arcname)
            if result.get("plan") and Path(str(result["plan"])).exists():
                zf.write(str(result["plan"]), f"plans/{idx:02d}_{Path(upload.filename or 'sketch').stem}_plan.json")
    return JSONResponse({
        "zip": "/outputs/" + zip_path.name,
        "rendered": rendered,
        "warnings": warnings,
    })


@app.get("/api/download/{filename}")
def download(filename: str) -> FileResponse:
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename)
