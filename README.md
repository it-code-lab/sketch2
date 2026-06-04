# AI Street Sketch Video Studio

## Batch 14 upgrade highlights

This batch adds three product-focused improvements on top of Batch 6:

- **Hand asset library**: uploaded hand images/videos are now reusable from a saved library.
- **Hand presets**: built-in presets for pencil, charcoal, ink, marker, right/left-handed, and different camera angles.
- **Automatic pencil-tip detection**: the server can analyze an uploaded or saved hand asset and propose Tip X / Tip Y calibration values automatically.

### New endpoints

- `GET /api/presets/hand` — list available hand presets
- `GET /api/assets/hand` — list saved hand assets in the library
- `POST /api/hand/auto-tip` — auto-detect the pencil-tip anchor from an uploaded or saved hand asset

### Typical workflow for Batch 14

1. Pick a **hand preset**.
2. Upload a new hand image/video or select one from the **saved hand asset library**.
3. Click **Auto-detect tip**.
4. Fine-tune Tip X / Tip Y manually if needed.
5. Analyze and render as usual.

### Notes

- Auto tip detection is a heuristic, so you should still review the crosshair visually before rendering long jobs.
- If both a saved library asset and a new upload exist, the new upload is used for the render.
- When a saved asset is selected from the library, you do not need to re-upload it each time.

 — Batch 14

Batch 14 is a premium local app that turns a final image or sketch into a realistic stroke-by-stroke street-artist video. It includes photo-to-sketch conversion, semantic region planning, true centerline stroke extraction, MP4 rendering, pencil scratch audio, render queue/progress tracking, and real hand overlay support.

Batch 14 specifically adds:

- Real transparent hand video overlay support
- Pencil-tip calibration UI
- Optional green-screen removal for hand footage
- Hand lift, contact shadow, frame offset, loop, and playback controls
- Improved hand movement along generated stroke paths

---

## 1. Current Feature Set

### Image and sketch input

You can upload:

- A normal photo
- A final pencil/charcoal/ink sketch
- A product/object image
- A temple/building image
- A portrait/pet/logo/landscape image

The app can either convert the image into a sketch or treat the upload as an existing sketch.

### Human-like drawing process

The renderer does not simply reveal the image. It builds a believable artist workflow using:

- Semantic region detection
- Layer-based planning
- Centerline stroke extraction
- Contour fallback extraction
- Construction/layout passes
- Focal detail passes
- Texture/hatching passes
- Shading/smudge passes
- Final accent passes

### Semantic subject templates

Supported subject templates:

- Auto
- Portrait
- Temple / Architecture
- Pet / Animal
- Product / Object
- Landscape
- Logo / Icon

Examples:

- Portrait mode prioritizes face outline, eyes, nose, mouth, hair, cheek/jaw, and clothing.
- Temple/architecture mode prioritizes roof, central structure, entrance, pillars, carvings, and ground.
- Pet mode prioritizes head, eyes, nose, ears, and body fur.
- Product mode prioritizes main object, detail core, shadow base, and outer details.

### Stroke extraction modes

```text
hybrid      Recommended default. Uses centerline strokes plus contour fallback.
centerline  Best for clean black-and-white sketches and line art.
contour     Older fallback mode. Useful when centerline output is too sparse.
```

### Hand overlay modes

```text
procedural  Draws a generated hand/pencil overlay.
uploaded    Uses a static uploaded image such as PNG/WebP/JPEG.
video       Uses a real hand video asset such as transparent WebM or green-screen footage.
none        Disables hand overlay.
```

---

## 2. Project Structure

```text
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
```

Important files:

| File | Purpose |
|---|---|
| `backend/services/sketch_pipeline.py` | Main image-to-stroke planning pipeline |
| `backend/services/semantic_planning.py` | Semantic region detection and layer planning |
| `backend/services/centerline_extractor.py` | Skeleton/centerline-based stroke extraction |
| `backend/services/render_engine.py` | Frame rendering, MP4 export, hand overlay compositing |
| `backend/services/asset_manager.py` | Hand image/video asset handling |
| `frontend/app.js` | UI controls, render queue polling, calibration UI |
| `frontend/index.html` | Main browser interface |

---

## 3. Setup

### 3.1 Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3.2 Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3.3 Install FFmpeg

FFmpeg is required for:

- MP4 export
- Pencil audio muxing
- Transparent hand video frame extraction
- Green-screen hand footage processing

Check FFmpeg:

```bash
ffmpeg -version
```

If this command fails, install FFmpeg and make sure it is available on PATH.

---

## 4. Running the App

Start the backend:

```bash
python run_backend.py
```

Open the app in your browser:

```text
http://127.0.0.1:8080
```

Recommended browser:

- Chrome
- Edge
- Any modern Chromium browser

---

## 5. Basic End-to-End Usage

### Step 1 — Upload source image

Upload either:

- A photo that should be converted to sketch
- A final sketch image

### Step 2 — Choose input type

Use:

```text
Photo → sketch
```

when the upload is a normal photo.

Use:

```text
Already a sketch
```

when the upload is already a line drawing, pencil sketch, ink sketch, or charcoal sketch.

### Step 3 — Choose subject template

For best results, avoid `Auto` when you already know the subject.

Examples:

```text
Portrait              for human face images
Temple / Architecture for temples, buildings, monuments, interiors
Pet / Animal          for dogs, cats, birds, animals
Product / Object      for tools, products, objects, icons
Logo / Icon           for clean logo reveal videos
```

### Step 4 — Choose stroke extraction

Recommended default:

```text
Hybrid centerline + contour
```

Use centerline-only for clean sketch input:

```text
True centerline only
```

Use contour fallback if the centerline output looks too sparse:

```text
Contour fallback only
```

### Step 5 — Analyze stroke plan

Click:

```text
Analyze stroke plan
```

Review:

- Sketch preview
- Pass summary
- Semantic regions
- Warnings/logs

### Step 6 — Configure hand overlay

Choose one of:

```text
Procedural hand/pen
Uploaded hand image
Transparent hand video
No hand
```

For a premium result, use:

```text
Transparent hand video
```

### Step 7 — Calibrate pencil tip

Upload the hand asset and click the exact pencil tip in the preview.

The UI automatically updates:

```text
Tip X %
Tip Y %
```

Then adjust:

```text
Scale
Opacity
Rotation
Hand lift px
Shadow strength
```

### Step 8 — Render MP4

Click:

```text
Render MP4 with queue
```

When complete, download:

- MP4 video
- JSON stroke plan
- Sketch preview
- Optional SVG sidecar if tracing is enabled

---

## 6. Recommended Settings

### 6.1 Fast preview render

Use this while testing:

```text
Ratio: 1:1
Duration: 5–8 seconds
FPS: 12
Max strokes: 300–700
Stroke extraction: hybrid
Hand mode: procedural or uploaded image
Pencil audio: off or on
Camera motion: off or on
```

### 6.2 Professional YouTube Shorts render

Use this for final social videos:

```text
Ratio: 9:16
Duration: 18–35 seconds
FPS: 24
Max strokes: 1500–3500
Stroke extraction: hybrid
Subject template: portrait / temple / product / pet
Hand mode: transparent hand video
Pencil audio: on
Camera motion: on
Smudge pass: on
Final accent pass: on
```

### 6.3 Clean line-art sketch input

```text
Input type: Already a sketch
Stroke extraction: centerline
Sketch strength: 55–75
Stroke density: 45–70
Max strokes: 1200–3000
```

### 6.4 Photo input

```text
Input type: Photo → sketch
Stroke extraction: hybrid
Sketch strength: 70–90
Stroke density: 55–80
Max strokes: 1800–3500
```

### 6.5 Temple / architecture videos

```text
Subject template: Temple / Architecture
Stroke extraction: hybrid
Construction pass: on
Final accent pass: on
Smudge pass: on
Stroke density: 60–85
Max strokes: 2000–4500
Hand mode: transparent hand video
```

### 6.6 Portrait videos

```text
Subject template: Portrait
Stroke extraction: hybrid
Sketch strength: 65–85
Stroke density: 55–75
Human randomness: 25–45
Final accent pass: on
Smudge pass: on
Hand mode: transparent hand video
```

---

## 7. AI Art Director + Quality Scoring Usage

### 7.1 Best hand video format

Best quality:

```text
Format: WebM VP9 with alpha
Background: transparent
Length: 1–5 seconds
Resolution: 400–900 px wide
Camera angle: same as drawing canvas angle
Lighting: neutral and soft
Pencil tip: always visible
```

This gives the cleanest overlay because the background is already transparent.

### 7.2 Acceptable formats

The app accepts:

```text
WebM
MP4
MOV
MKV
PNG
WebP
JPEG
```

Important: most MP4 videos do not contain transparency. They can still be used, but they will appear as normal rectangular footage unless you use green-screen removal.

### 7.3 Green-screen hand video

If your hand video has a green background:

1. Choose `Transparent hand video`.
2. Upload the green-screen hand clip.
3. Enable `Remove green-screen background`.
4. Calibrate the pencil tip.
5. Render a short preview first.

Green-screen removal is useful, but transparent WebM is still better for clean edges.

### 7.4 Recording your own hand clip

For best results:

- Record the hand from above or at a slight angle.
- Keep the pencil/charcoal tip visible in every frame.
- Avoid strong shadows on the hand asset itself.
- Use a plain green background if you cannot record transparency.
- Keep the hand clip short and loopable.
- Avoid moving the hand too much inside the clip; the app moves the hand along the generated stroke path.

A good clip is mostly a natural drawing-hand pose with slight finger/hand motion.

---

## 8. Pencil-Tip Calibration UI

The pencil-tip anchor tells the renderer which point in the hand asset should touch the generated stroke path.

### How to calibrate

1. Upload the hand image/video.
2. Wait for the preview to load.
3. Click the exact pencil/marker/charcoal tip.
4. Confirm the app updates:

```text
Tip X %
Tip Y %
```

5. Adjust scale and rotation until the hand visually fits the canvas.
6. Render a short test video.

### Calibration tips

If the hand is too far from the line:

```text
Re-click the exact pencil tip
Reduce or increase rotation
Adjust scale slightly
Reduce hand lift px
```

If the hand covers too much of the drawing:

```text
Reduce scale
Reduce opacity slightly
Increase hand lift px
Use a smaller hand asset
```

If the pencil tip appears behind the stroke:

```text
Try a different hand rotation
Use a hand clip with a clearer tip
Make sure the clicked tip is the actual contact point
```

---

## 9. Hand Overlay Controls

### `hand_mode`

```text
procedural  generated hand/pencil overlay
uploaded    uploaded static hand image
video       uploaded hand video overlay
none        no hand overlay
```

### `hand_tip_x`, `hand_tip_y`

The pencil tip anchor inside the hand asset.

```text
0,0     top-left
50,50   center
100,100 bottom-right
```

Use the calibration UI instead of typing these manually when possible.

### `hand_scale`

Controls hand asset size.

Typical values:

```text
25–45 for normal hand video
15–30 for large source assets
45–70 for small source assets
```

### `hand_rotation`

Rotates the hand asset.

Typical values:

```text
-25 to -5 for right-hand pencil angle
5 to 25 for opposite angle
```

### `hand_opacity`

Controls overlay opacity.

Recommended:

```text
85–100 for realistic hand overlay
50–75 for semi-transparent debug preview
```

### `hand_lift_px`

Adds a visible lift/reposition effect between strokes.

Recommended:

```text
0–10 subtle
10–25 realistic
25–50 more dramatic
```

### `hand_shadow_strength`

Controls contact shadow under the pencil/hand.

Recommended:

```text
15–35 subtle
35–60 strong studio look
```

### `hand_video_loop`

Loops the hand video frames during the render.

Use `true` for short loopable clips.

### `hand_video_playback_rate`

Controls how fast the hand video animation itself plays.

Recommended:

```text
75–125 normal
50 slower hand motion
150 faster hand motion
```

### `hand_video_frame_offset`

Starts the hand video at a different frame/time offset.

Use this when the best hand pose happens slightly later in the source clip.

### `hand_video_chroma_key`

Removes green-screen background.

Use only for green-screen hand footage.

---

## 10. API Notes

Main endpoints:

```text
GET  /api/health
GET  /api/assets/hand
POST /api/analyze
POST /api/render
POST /api/render-queued
GET  /api/jobs/{job_id}
GET  /api/jobs
POST /api/batch-render
```

Important form fields:

```text
input_type = photo | sketch
subject_type = auto | portrait | architecture | pet | product | landscape | logo
style_type = pencil | charcoal | ink | marker
ratio = 9:16 | 1:1 | 16:9
stroke_extraction_mode = hybrid | centerline | contour
hand_mode = procedural | uploaded | video | none
hand_asset = uploaded image/video file
hand_tip_x = 0..100
hand_tip_y = 0..100
hand_scale = 8..120
hand_rotation = -180..180
hand_opacity = 5..100
hand_video_loop = true | false
hand_video_playback_rate = 25..400
hand_video_frame_offset = -2000..2000
hand_video_chroma_key = true | false
hand_lift_px = 0..80
hand_shadow_strength = 0..100
```

---

## 11. Troubleshooting

### 11.1 Backend not reachable

Check that you ran:

```bash
python run_backend.py
```

Then open:

```text
http://127.0.0.1:8080
```

### 11.2 FFmpeg missing

Check:

```bash
ffmpeg -version
```

If missing, install FFmpeg and add it to PATH.

### 11.3 The hand video does not appear

Check:

- Hand mode is set to `Transparent hand video`.
- A video file was uploaded before rendering.
- FFmpeg is installed and available on PATH.
- The video is readable by FFmpeg.
- Opacity is not too low.
- Scale is not too small.
- Tip calibration is not outside the visible asset.

### 11.4 The video background is not transparent

Use transparent WebM where possible.

For green-screen footage:

```text
Enable Remove green-screen background
```

Most standard MP4 files are opaque and do not contain transparency.

### 11.5 Pencil tip does not touch the line

Use the calibration panel:

- Click the exact pencil tip point.
- Adjust Tip X and Tip Y.
- Reduce rotation if the hand drifts away.
- Increase/decrease scale until the pencil tip visually matches the stroke.
- Render a 5-second preview before final export.

### 11.6 Hand is too jumpy

Try:

```text
Reduce human randomness
Reduce hand lift px
Use a smoother hand video
Use longer duration
Use fewer strokes for preview
```

### 11.7 Rendering is slow

Try:

```text
FPS: 12 for previews
Duration: 5–8 seconds
Max strokes: 300–700
Smaller hand video asset
Shorter hand loop
hand_mode = uploaded for previews
```

### 11.8 Centerline extraction looks sparse

Use:

```text
Stroke extraction: hybrid
Sketch strength: higher
Stroke density: higher
```

Centerline-only mode works best on clean black-and-white sketch images.

### 11.9 Too many tiny strokes

Try:

```text
Lower stroke density
Lower max strokes
Use contour fallback only
Use a cleaner sketch input
```

### 11.10 Output looks like a reveal, not a real artist

Use:

```text
Subject template: not Auto
Construction pass: on
Final accent pass: on
Smudge pass: on
Human randomness: 25–45
Stroke extraction: hybrid
Hand mode: transparent hand video
```

---

## 12. Cleanup

Generated outputs are saved inside:

```text
outputs/
```

You can safely delete old files from this folder after downloading your videos.

Do not delete:

```text
outputs/.gitkeep
```

unless you do not care about preserving the folder in Git.

---

## 13. Next Phases / Professional Roadmap

The app is now a strong local premium renderer. The next phases should focus on quality, automation, and productization.

### Phase 7 — Hand Asset Library + Presets

Goal: make hand overlay setup easy for non-technical users.

Implement:

- Built-in hand clip library
- Pencil hand preset
- Charcoal hand preset
- Marker hand preset
- Ink pen preset
- Right-hand and left-hand presets
- Top-down and angled camera presets
- Preset calibration values per asset
- Automatic matching between selected art style and hand asset

Why this matters:

The current system supports hand video, but users still need to supply and calibrate assets. A preset library makes the product feel complete.

### Phase 8 — Automatic Pencil-Tip Detection

Goal: reduce manual calibration.

Implement:

- First-frame analysis of hand asset
- Pencil/pen tip candidate detection
- Optional color marker detection on the pencil tip
- Edge/line intersection analysis
- Auto-filled Tip X/Y
- Manual override remains available

Why this matters:

Manual calibration works, but automatic tip detection makes the workflow much faster.

### Phase 9 — Stroke-to-Hand Contact Correction

Goal: make the hand feel physically attached to the drawing action.

Implement:

- Tip contact verification per stroke
- Per-segment angle correction
- Hand orientation smoothing
- Contact shadow tied to pressure/darkness
- Lift/reposition arcs between distant strokes
- Prevent hand from covering important focal areas for too long

Why this matters:

This is one of the biggest realism improvements after transparent hand video.

### Phase 10 — Pro Render Quality Modes

Goal: support final production quality.

Implement:

- 1080x1920 Shorts export
- 1920x1080 YouTube export
- 4K landscape export
- Higher-quality anti-aliasing
- Motion blur for hand movement
- Better paper grain
- Better pencil/charcoal/ink texture
- Optional render preview at low resolution, final render at high resolution

Why this matters:

Current defaults are optimized for local rendering speed. Final commercial exports need higher resolution and better visual polish.

### Phase 11 — Advanced Brush and Medium Simulation

Goal: make pencil, charcoal, ink, and marker feel visually different.

Implement:

- Graphite grain shader
- Charcoal dust and smudge buildup
- Ink bleed and taper
- Marker overlap and wet edge effect
- Variable pressure simulation
- Stroke taper at start/end
- Repeated darkening on accent strokes

Why this matters:

The app should not only draw in different colors/thicknesses. Each medium should feel different.

### Phase 12 — AI Art Director Integration

Goal: use AI to improve region planning and drawing order.

Implement:

- Optional vision-model analysis of uploaded image
- AI-generated semantic region map
- AI-suggested drawing order
- AI quality notes before render
- AI prompt-to-style settings
- User editable art-director JSON

Why this matters:

Rule-based semantic planning is good, but AI can better understand complex images like crowded temples, family portraits, and product scenes.

### Phase 13 — Batch Generation Workflow

Goal: support creators producing many videos.

Implement:

- Multi-image upload
- Shared preset settings
- Per-image overrides
- Queue dashboard
- Bulk MP4 download ZIP
- CSV/JSON job import
- Auto naming by subject/style/date

Why this matters:

This matches YouTube Shorts, Instagram Reels, and TikTok production workflows.

### Phase 14 — Template System for Viral Videos

Goal: turn the renderer into a social-video product.

Implement:

- Before/after reveal templates
- Title card templates
- Music/sound presets
- Caption templates
- Logo/watermark presets
- Temple renovation sketch template
- Portrait memorial sketch template
- Pet sketch reveal template
- Product ad sketch template

Why this matters:

Creators usually want complete video formats, not just a raw sketch animation.

### Phase 15 — Product Packaging and Deployment

Goal: prepare for sale or hosted use.

Implement:

- Desktop installer or one-click local launcher
- Docker setup
- GPU/CPU render mode documentation
- License activation if selling
- User project save/load
- Render history
- Settings preset export/import
- Error reporting logs
- Example assets and sample projects

Why this matters:

The project is moving from prototype to sellable software.

---

## 14. Recommended Immediate Next Batch

Recommended next implementation:

```text
Batch 14: Hand Asset Library + Presets + Automatic Pencil-Tip Detection
```

This should include:

1. Preset hand asset registry
2. Built-in example procedural/video placeholders
3. Calibration presets per hand asset
4. Auto tip detection for uploaded hand images/videos
5. Better UI for choosing hand type
6. Saved hand profiles

This will make the hand overlay workflow much easier and more professional.
