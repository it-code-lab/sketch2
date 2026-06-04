# AI Street Sketch Video Studio — Batch 2

Batch 2 turns the browser MVP into a premium local renderer for realistic sketching videos.

It supports:

- image/photo upload
- photo-to-sketch conversion with OpenCV
- contour extraction
- hatching/shading stroke generation
- subject-aware human drawing order
- artist passes: layout, contour, key details, secondary details, texture, shading, final accents
- browser preview of the generated stroke plan
- Python/FFmpeg MP4 export
- optional paper texture
- optional stylized hand/pencil overlay
- optional procedural pencil scratch audio
- batch rendering to a ZIP file
- downloadable JSON stroke plan for debugging or reuse

---

## Project structure

```text
sketch-video-studio-batch2/
  backend/
    main.py
    models.py
    services/
      sketch_pipeline.py
      render_engine.py
      audio.py
  frontend/
    index.html
    styles.css
    app.js
  outputs/
  requirements.txt
  run_backend.py
  README.md
  .gitignore
```

---

## Install

Use Python 3.10+.

```bash
cd sketch-video-studio-batch2
python -m venv .venv
```

Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Install FFmpeg and make sure `ffmpeg` is available on PATH.

Windows options:

```bash
winget install Gyan.FFmpeg
```

or install manually and add the `bin` folder to PATH.

Check:

```bash
ffmpeg -version
```

---

## Run

```bash
python run_backend.py
```

Open:

```text
http://127.0.0.1:8080
```

---

## Recommended settings

### Fast test

```text
Duration: 8–12 seconds
FPS: 12–24
Max strokes: 500–1000
Stroke density: 35–55
```

### YouTube Shorts quality

```text
Ratio: 9:16
Duration: 18–35 seconds
FPS: 24
Max strokes: 1500–3000
Stroke density: 55–75
Paper texture: on
Hand overlay: on
Pencil audio: on
```

### Detailed portrait sketch

```text
Subject: Portrait
Sketch style: Pencil or Charcoal
Sketch strength: 65–85
Stroke density: 65–85
Human randomness: 30–50
Final accents: on
```

### Temple / architecture sketch

```text
Subject: Temple / architecture
Sketch style: Ink or Pencil
Sketch strength: 70–90
Stroke density: 60–80
Construction pass: on
Final accents: on
```

---

## How human-like ordering works

The backend does not reveal pixels randomly. It converts the sketch into strokes and classifies them into artist-intent layers:

```text
layout → main contours → key focal details → secondary details → texture → shading → final accents
```

Then it adjusts ordering using subject-specific rules.

For portraits:

```text
face outline and guides → eyes → nose → mouth → hair/clothing → shading → dark accents
```

For temples/buildings:

```text
silhouette → roof/shikhara → entrance → pillars/walls → carvings → stone texture → shadows/final accents
```

For pets:

```text
head/body outline → eyes/nose → ears → fur strokes → body texture → shadows → accents
```

The renderer also adds:

- non-uniform stroke duration
- pauses between passes
- small jumps between nearby regions
- pressure/opacity variation
- pencil/charcoal/ink/marker styling
- optional hand/pencil overlay at the active stroke tip

---

## API endpoints

### Health

```text
GET /api/health
```

Returns backend status and whether FFmpeg was found.

### Analyze stroke plan

```text
POST /api/analyze
```

Multipart form fields:

```text
file
input_type: photo | sketch
subject_type: auto | portrait | architecture | pet | product | landscape
style_type: pencil | charcoal | ink | marker
ratio: 9:16 | 1:1 | 16:9
sketch_strength: 20-100
stroke_density: 10-100
human_randomness: 0-100
duration_seconds: 5-120
fps: 12-60
max_strokes: 250-5000
paper_texture: true | false
construction_pass: true | false
accent_pass: true | false
hand_overlay: true | false
pencil_audio: true | false
seed: integer
```

Returns:

- source preview
- sketch preview
- full stroke plan JSON

### Render MP4

```text
POST /api/render
```

Same form fields as analyze.

Returns links to:

- MP4
- plan JSON
- sketch PNG

### Batch render

```text
POST /api/batch-render
```

Uses `files` as a multi-file field.

Returns a ZIP file containing rendered videos and plans.

---

## Performance notes

MP4 rendering creates PNG frames first, then encodes with FFmpeg.

Rendering cost roughly increases with:

```text
video duration × FPS × stroke count × resolution
```

For quick testing, reduce duration, FPS, and max strokes.

For final videos, use 24 FPS and higher stroke counts.

---

## Current limitations

This batch intentionally uses deterministic image processing instead of heavy AI models.

Limitations:

- Stroke extraction is based on OpenCV contours and synthetic hatching, not true hand-drawn vector reconstruction.
- The hand overlay is stylized/procedural, not a real green-screen hand asset yet.
- AI region planning is not included yet.
- Potrace/VTracer SVG tracing is not included yet.
- Real smudging/eraser passes are not included yet.

---

## Suggested Batch 3

Next premium upgrades:

1. Real hand overlay asset support
2. Potrace/VTracer SVG path tracing option
3. AI art director step for subject/region ordering
4. Multiple hand angles and tool assets
5. Smudge/eraser/highlight passes
6. Voiceover/music integration
7. Preset templates for portrait, temple, pet, product, and logo sketch videos
8. Queue-based rendering with progress updates
9. Packaged desktop app using Electron or Tauri

---

## Commercial positioning

Possible product name:

```text
AI Street Sketch Video Studio
```

One-line pitch:

```text
Turn any photo or sketch into a realistic time-lapse video of a professional street artist drawing it stroke by stroke.
```
