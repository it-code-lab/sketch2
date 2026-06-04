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
from backend.services.asset_manager import list_hand_assets, save_hand_asset
from backend.services.job_store import JobStore
from backend.services.sketch_pipeline import image_to_data_url, make_stroke_plan
from backend.services.render_engine import render_plan_to_mp4
from backend.services.svg_tracer import maybe_trace_to_svg, tracer_status

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

jobs = JobStore()

app = FastAPI(
    title="AI Street Sketch Video Studio Backend",
    version="0.3.0",
    description="Photo/sketch to realistic street-artist stroke video renderer with premium hand overlay and job queue.",
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
        "version": "0.3.0",
        "ffmpeg_found": shutil.which("ffmpeg") is not None,
        "tracing": tracer_status(),
        "hand_assets": len(list_hand_assets(ROOT)),
    }


@app.get("/api/assets/hand")
def hand_assets() -> dict[str, Any]:
    assets = list_hand_assets(ROOT)
    for asset in assets:
        asset["url"] = "/assets/" + str(asset["filename"])
    return {"assets": assets}


async def read_upload_image(file: UploadFile) -> bytes:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image is too large. Please use an image under 25 MB.")
    return data


def form_to_settings(**values: Any) -> RenderSettings:
    return RenderSettings.from_form(values)


def public_result(result: dict[str, Any]) -> dict[str, str]:
    public: dict[str, str] = {}
    for key in ["mp4", "plan", "preview", "svg"]:
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
        }
        jobs.update(job_id, status="done", progress=100, message="Render complete", result=payload)
    except Exception as exc:
        jobs.update(job_id, status="failed", progress=100, message="Render failed", error=str(exc))


# This function keeps the endpoint signatures readable while still exposing every Batch 3 setting.
def values_to_settings(
    input_type: str,
    subject_type: str,
    style_type: str,
    ratio: str,
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
    planning_mode: str,
    art_director_json: str,
    camera_motion: bool,
    smudge_pass: bool,
    eraser_pass: bool,
    title_card_text: str,
    watermark_text: str,
    hand_mode: str,
    hand_scale: int,
    hand_opacity: int,
    hand_rotation: int,
    hand_tip_x: int,
    hand_tip_y: int,
) -> RenderSettings:
    return form_to_settings(
        input_type=input_type,
        subject_type=subject_type,
        style_type=style_type,
        ratio=ratio,
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
        planning_mode=planning_mode,
        art_director_json=art_director_json,
        camera_motion=camera_motion,
        smudge_pass=smudge_pass,
        eraser_pass=eraser_pass,
        title_card_text=title_card_text,
        watermark_text=watermark_text,
        hand_mode=hand_mode,
        hand_scale=hand_scale,
        hand_opacity=hand_opacity,
        hand_rotation=hand_rotation,
        hand_tip_x=hand_tip_x,
        hand_tip_y=hand_tip_y,
    )


@app.post("/api/analyze")
async def analyze(
    file: Annotated[UploadFile, File()],
    input_type: Annotated[str, Form()] = "photo",
    subject_type: Annotated[str, Form()] = "auto",
    style_type: Annotated[str, Form()] = "pencil",
    ratio: Annotated[str, Form()] = "9:16",
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
    planning_mode: Annotated[str, Form()] = "rule",
    art_director_json: Annotated[str, Form()] = "",
    camera_motion: Annotated[bool, Form()] = True,
    smudge_pass: Annotated[bool, Form()] = True,
    eraser_pass: Annotated[bool, Form()] = False,
    title_card_text: Annotated[str, Form()] = "",
    watermark_text: Annotated[str, Form()] = "",
    hand_mode: Annotated[str, Form()] = "procedural",
    hand_scale: Annotated[int, Form()] = 32,
    hand_opacity: Annotated[int, Form()] = 95,
    hand_rotation: Annotated[int, Form()] = -18,
    hand_tip_x: Annotated[int, Form()] = 18,
    hand_tip_y: Annotated[int, Form()] = 78,
):
    image_bytes = await read_upload_image(file)
    settings = values_to_settings(
        input_type, subject_type, style_type, ratio, sketch_strength, stroke_density, human_randomness,
        duration_seconds, fps, max_strokes, paper_texture, construction_pass, accent_pass, hand_overlay,
        pencil_audio, seed, trace_mode, planning_mode, art_director_json, camera_motion, smudge_pass,
        eraser_pass, title_card_text, watermark_text, hand_mode, hand_scale, hand_opacity, hand_rotation,
        hand_tip_x, hand_tip_y,
    )
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
    planning_mode: Annotated[str, Form()] = "rule",
    art_director_json: Annotated[str, Form()] = "",
    camera_motion: Annotated[bool, Form()] = True,
    smudge_pass: Annotated[bool, Form()] = True,
    eraser_pass: Annotated[bool, Form()] = False,
    title_card_text: Annotated[str, Form()] = "",
    watermark_text: Annotated[str, Form()] = "",
    hand_mode: Annotated[str, Form()] = "procedural",
    hand_scale: Annotated[int, Form()] = 32,
    hand_opacity: Annotated[int, Form()] = 95,
    hand_rotation: Annotated[int, Form()] = -18,
    hand_tip_x: Annotated[int, Form()] = 18,
    hand_tip_y: Annotated[int, Form()] = 78,
):
    image_bytes = await read_upload_image(file)
    settings = values_to_settings(
        input_type, subject_type, style_type, ratio, sketch_strength, stroke_density, human_randomness,
        duration_seconds, fps, max_strokes, paper_texture, construction_pass, accent_pass, hand_overlay,
        pencil_audio, seed, trace_mode, planning_mode, art_director_json, camera_motion, smudge_pass,
        eraser_pass, title_card_text, watermark_text, hand_mode, hand_scale, hand_opacity, hand_rotation,
        hand_tip_x, hand_tip_y,
    )
    if hand_asset and hand_mode == "uploaded":
        settings.hand_asset_path = await save_hand_asset(hand_asset, ROOT)
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
    planning_mode: Annotated[str, Form()] = "rule",
    art_director_json: Annotated[str, Form()] = "",
    camera_motion: Annotated[bool, Form()] = True,
    smudge_pass: Annotated[bool, Form()] = True,
    eraser_pass: Annotated[bool, Form()] = False,
    title_card_text: Annotated[str, Form()] = "",
    watermark_text: Annotated[str, Form()] = "",
    hand_mode: Annotated[str, Form()] = "procedural",
    hand_scale: Annotated[int, Form()] = 32,
    hand_opacity: Annotated[int, Form()] = 95,
    hand_rotation: Annotated[int, Form()] = -18,
    hand_tip_x: Annotated[int, Form()] = 18,
    hand_tip_y: Annotated[int, Form()] = 78,
):
    image_bytes = await read_upload_image(file)
    settings = values_to_settings(
        input_type, subject_type, style_type, ratio, sketch_strength, stroke_density, human_randomness,
        duration_seconds, fps, max_strokes, paper_texture, construction_pass, accent_pass, hand_overlay,
        pencil_audio, seed, trace_mode, planning_mode, art_director_json, camera_motion, smudge_pass,
        eraser_pass, title_card_text, watermark_text, hand_mode, hand_scale, hand_opacity, hand_rotation,
        hand_tip_x, hand_tip_y,
    )
    if hand_asset and hand_mode == "uploaded":
        settings.hand_asset_path = await save_hand_asset(hand_asset, ROOT)
    job_id = f"queued_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    jobs.create(job_id)
    background_tasks.add_task(run_render_job, job_id, image_bytes, settings)
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
    planning_mode: Annotated[str, Form()] = "rule",
    art_director_json: Annotated[str, Form()] = "",
    camera_motion: Annotated[bool, Form()] = True,
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
        input_type, subject_type, style_type, ratio, sketch_strength, stroke_density, human_randomness,
        duration_seconds, fps, max_strokes, paper_texture, construction_pass, accent_pass, hand_overlay,
        pencil_audio, seed, trace_mode, planning_mode, art_director_json, camera_motion, smudge_pass,
        eraser_pass, title_card_text, watermark_text, "procedural", 32, 95, -18, 18, 78,
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
