# AI Street Sketch Video Studio — Batch 3 Premium Upgrade

This package upgrades Batch 2 into a more premium local app for creating realistic sketching videos from a final image or a final sketch.

The goal is not just to reveal lines. The goal is to simulate a believable professional artist workflow:

1. loose construction marks
2. main contour structure
3. key focal features
4. secondary details
5. texture strokes
6. shading / hatching
7. smudging / optional eraser highlights
8. final dark accents
9. optional hand overlay, audio, title card, watermark, and MP4 export

## What is new in Batch 3

### Real hand overlay support

Batch 2 had a procedural pencil/hand overlay. Batch 3 adds support for uploading a real transparent PNG/WebP/JPEG hand asset.

Controls included:

- hand mode: procedural, uploaded, or none
- uploaded hand asset
- scale
- opacity
- rotation
- tip X/Y anchor percentage

Tip X/Y tells the renderer which point on your hand image should follow the active drawing stroke. For example, if the pencil tip is near the lower-left area of the PNG, try:

```text
Tip X: 18
Tip Y: 78
```

### Render queue and progress

Batch 3 adds queued rendering:

- `POST /api/render-queued`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs`

The frontend now polls render progress and shows frame/render/encode status.

### Art Director JSON

The app still works with rule-based planning, but you can now provide a planning JSON to influence drawing order.

Example:

```json
{
  "subject_type": "portrait",
  "region_priority": {
    "left_eye": -22,
    "right_eye": -22,
    "nose": -10,
    "mouth": -7,
    "hair_top": 12,
    "neck_clothing": 18
  },
  "region_layer_overrides": {
    "left_eye": "key",
    "right_eye": "key"
  }
}
```

Lower priority values draw earlier. Higher values draw later.

This is designed so a future vision model can act as the “art director,” while your deterministic renderer still creates the final video reliably.

### SVG tracing hooks

The core animation still uses the OpenCV stroke extractor. Batch 3 adds optional SVG sidecar export hooks for:

- Potrace
- VTracer

If either command-line tool is installed and selected in the UI, the backend can create an SVG sidecar for inspection/future vector-path workflows. If the tool is not installed, the app falls back to OpenCV stroke extraction.

### More realism effects

Batch 3 adds:

- smudge pass
- optional eraser/highlight pass
- subtle camera drift
- opening title card
- watermark
- improved cropped-stroke rendering for better performance
- render job progress tracking

## Run locally

```bash
cd sketch-video-studio-batch3
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_backend.py
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python run_backend.py
```

Open:

```text
http://127.0.0.1:8080
```

## FFmpeg requirement

MP4 export requires FFmpeg on PATH.

Check:

```bash
ffmpeg -version
```

The app health box will also show whether FFmpeg is detected.

## Suggested first test settings

For a quick test:

```text
Ratio: 9:16
Duration: 5–8 seconds
FPS: 12
Max strokes: 250–700
Hand mode: none or procedural
Pencil audio: off for first test
```

For a better social video:

```text
Ratio: 9:16
Duration: 18–35 seconds
FPS: 24
Max strokes: 1200–3000
Hand mode: uploaded or procedural
Pencil audio: on
Smudge pass: on
Final accent pass: on
```

## Output resolution

Batch 3 defaults are optimized for local rendering speed:

```text
9:16  -> 540 x 960
1:1   -> 720 x 720
16:9  -> 960 x 540
```

You can increase these in `backend/models.py` inside `ratio_to_size()` after the renderer and queue are stable on your machine.

## API overview

### Health

```http
GET /api/health
```

Returns FFmpeg and tracer availability.

### Analyze

```http
POST /api/analyze
```

Returns:

- source preview
- sketch preview
- full stroke plan JSON
- pass summary
- warnings

### Render immediately

```http
POST /api/render
```

Renders in the request and returns MP4/plan/preview links.

### Render with queue

```http
POST /api/render-queued
```

Returns a job id.

Then poll:

```http
GET /api/jobs/{job_id}
```

## File structure

```text
backend/
  main.py
  models.py
  services/
    asset_manager.py
    audio.py
    job_store.py
    render_engine.py
    sketch_pipeline.py
    svg_tracer.py
frontend/
  index.html
  styles.css
  app.js
assets/
  .gitkeep
outputs/
  .gitkeep
requirements.txt
run_backend.py
```

## Notes for future Batch 4

Recommended next upgrades:

1. true SVG path parsing into stroke paths
2. object/face-part detection for better automatic region planning
3. real brush/pencil sound library instead of procedural audio
4. GPU-accelerated preview rendering
5. 1080p/4K final render profile
6. multiple hand assets and hand pose library
7. background music and final reveal template
8. reusable preset templates for portrait, temple, pet, product, and logo videos
