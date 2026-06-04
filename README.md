# AI Street Sketch Video Studio — Batch 5

Batch 5 upgrades the Batch 4 semantic-planning app with **true centerline stroke extraction** and **better hand realism**.

The goal is to make the generated video look less like a simple image reveal and more like a real artist drawing with a pencil/pen tip.

---

## What is new in Batch 5

### 1. True centerline stroke extraction

Earlier batches could extract contours around dark sketch shapes. That is useful for outlines, but it can look like the app is tracing around a line rather than drawing the line itself.

Batch 5 adds a new skeleton/centerline extractor:

```text
sketch image → cleaned binary line art → 1-pixel skeleton → traced centerline paths → human-style stroke segments
```

New file:

```text
backend/services/centerline_extractor.py
```

Supported stroke extraction modes:

```text
Hybrid centerline + contour  Recommended default
True centerline only          Most pencil-like, best for clean sketches
Contour fallback only         Useful for difficult/noisy inputs
```

The new setting is:

```text
stroke_extraction_mode
```

Allowed values:

```text
hybrid
centerline
contour
```

---

### 2. Better hand realism

The renderer now improves the hand/pen illusion with:

```text
smoother hand-tip motion
stroke-direction-aware hand angle
hand repositioning between strokes
small lifted arc during pauses
contact shadow under pencil tip
shadow for uploaded hand assets
less popping between unrelated strokes
procedural hand/pencil motion improvements
```

The hand now follows a more believable sequence:

```text
draw stroke → lift hand → move toward next stroke → lower hand → draw again
```

---

### 3. Improved planning integration

Batch 5 keeps the Batch 4 semantic planning system and combines it with centerline strokes.

The flow is now:

```text
Input image
→ sketch conversion
→ subject inference
→ semantic region detection
→ centerline + contour extraction
→ semantic stroke reassignment
→ layer-based artist order
→ timed rendering
→ hand overlay + audio + MP4
```

---

## Project structure

```text
sketch-video-studio-batch5/
  backend/
    main.py
    models.py
    services/
      asset_manager.py
      audio.py
      centerline_extractor.py
      job_store.py
      render_engine.py
      semantic_planning.py
      sketch_pipeline.py
      svg_tracer.py
  frontend/
    index.html
    styles.css
    app.js
  assets/
  outputs/
  requirements.txt
  run_backend.py
  README.md
```

---

## Requirements

Install Python 3.10+.

Install FFmpeg and make sure it is available on PATH.

Check FFmpeg:

```bash
ffmpeg -version
```

Optional tools:

```text
Potrace
VTracer
```

These are only needed for SVG sidecar tracing. The main Batch 5 centerline renderer does not require them.

---

## Setup on Windows PowerShell

```powershell
cd sketch-video-studio-batch5
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_backend.py
```

Open:

```text
http://127.0.0.1:8080
```

---

## Setup on macOS / Linux

```bash
cd sketch-video-studio-batch5
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_backend.py
```

Open:

```text
http://127.0.0.1:8080
```

---

## Recommended settings

### Clean portrait sketch

```text
Input type: Already a sketch
Subject template: Portrait
Stroke extraction: True centerline only
Sketch strength: 60–75
Stroke density: 55–75
Max strokes: 1800–3500
Duration: 18–35 seconds
FPS: 24
Hand mode: Procedural or uploaded transparent hand PNG
```

### Photo to street sketch video

```text
Input type: Photo → sketch
Subject template: Auto or Portrait
Stroke extraction: Hybrid centerline + contour
Sketch strength: 70–85
Stroke density: 60–80
Max strokes: 2200–4500
Duration: 22–45 seconds
FPS: 24
Smudge pass: On
Final accent pass: On
```

### Temple / architecture sketch

```text
Input type: Photo → sketch or Already a sketch
Subject template: Temple / Architecture
Stroke extraction: Hybrid centerline + contour
Sketch strength: 70–90
Stroke density: 65–85
Max strokes: 3000–6000
Duration: 25–60 seconds
Construction pass: On
Final accent pass: On
Smudge pass: On
```

### Fast testing

```text
Duration: 5–8 seconds
FPS: 12
Max strokes: 250–600
Stroke extraction: Hybrid
Pencil audio: Off
```

---

## API endpoints

```text
GET  /api/health
POST /api/analyze
POST /api/render
POST /api/render-queued
GET  /api/jobs/{job_id}
GET  /api/jobs
POST /api/batch-render
GET  /api/assets/hand
```

---

## Key request fields

```text
input_type: photo | sketch
subject_type: auto | portrait | architecture | pet | product | landscape | logo
style_type: pencil | charcoal | ink | marker
ratio: 9:16 | 1:1 | 16:9
stroke_extraction_mode: hybrid | centerline | contour
trace_mode: opencv | auto | potrace | vtracer
planning_mode: rule | art_director_json
```

---

## Troubleshooting

### Backend does not start

Run from the project root:

```bash
python run_backend.py
```

Make sure dependencies are installed:

```bash
pip install -r requirements.txt
```

---

### MP4 is not created

Check FFmpeg:

```bash
ffmpeg -version
```

If FFmpeg is missing, the app can still create frames, preview, and JSON plan, but MP4 export will be skipped.

---

### Centerline extraction creates too few strokes

Try:

```text
increase Sketch strength
increase Stroke density
use Hybrid centerline + contour
upload a cleaner sketch image
avoid very low contrast images
```

---

### Centerline-only mode loses important outlines

Use:

```text
Stroke extraction: Hybrid centerline + contour
```

Hybrid mode keeps the natural centerline movement while retaining important large silhouettes.

---

### Hand does not align with uploaded hand image

Adjust:

```text
Hand scale
Hand rotation
Tip X %
Tip Y %
```

The transparent hand PNG should have the pencil tip visible. Use Tip X and Tip Y to tell the app where the pencil tip is inside the uploaded hand image.

---

### Rendering is slow

Use lower settings while testing:

```text
FPS: 12
Duration: 5–8 seconds
Max strokes: 500–1000
Ratio: 1:1
Pencil audio: Off
```

Use higher settings only for final exports.

---

## Validation performed

The Batch 5 backend files were compiled successfully with Python.

A small test render was also executed successfully with:

```text
hybrid centerline extraction
hand overlay enabled
MP4 output generated
```

---

## Recommended next upgrades

The next highest-impact professional upgrades are:

```text
1. real transparent hand video overlay, not just static PNG
2. pencil-tip calibration UI with live draggable anchor
3. stroke merge/simplification quality controls
4. subject-specific AI art director using a vision model
5. final 1080p/4K export profiles
6. automatic side-by-side before/after and social-media templates
```
