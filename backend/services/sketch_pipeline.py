from __future__ import annotations

import base64
import io
import json
import math
import random
from collections import Counter, defaultdict
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageOps

from backend.models import RenderSettings, Stroke, StrokePlan
from backend.services.centerline_extractor import make_centerline_paths
from backend.services.semantic_planning import (
    SemanticRegion,
    build_layer_plan,
    decide_semantic_layer,
    detect_semantic_regions,
    select_region_for_stroke,
)

PASS_NAMES = {
    "layout": "Loose construction",
    "contour": "Main contours",
    "key": "Key focal details",
    "secondary": "Secondary details",
    "texture": "Texture and repeated marks",
    "shading": "Shading and hatching",
    "accent": "Final dark accents",
}

PASS_DESCRIPTIONS = {
    "layout": "Light guide strokes that make the sketch feel planned before details appear.",
    "contour": "Large confident outlines and structural boundaries.",
    "key": "Subject-defining focal features such as eyes, entrances, symbols, or product edges.",
    "secondary": "Supporting lines, inner contours, clothing, carvings, and form details.",
    "texture": "Small repeated marks for hair, stone, fabric, foliage, paper grain, and surface texture.",
    "shading": "Hatching and shadow passes that build volume and depth.",
    "accent": "Dark final marks, reinforced edges, pupils, cracks, deep shadows, and finishing touches.",
}

LAYER_WEIGHT = {
    "layout": 8,
    "contour": 20,
    "key": 32,
    "secondary": 48,
    "texture": 62,
    "shading": 74,
    "accent": 92,
}

STYLE_DEFAULTS = {
    "pencil": {"thickness": 1.4, "opacity": 0.72, "jitter": 0.85},
    "charcoal": {"thickness": 2.5, "opacity": 0.62, "jitter": 1.55},
    "ink": {"thickness": 1.2, "opacity": 0.92, "jitter": 0.18},
    "marker": {"thickness": 3.2, "opacity": 0.78, "jitter": 0.32},
}


def image_from_bytes(image_bytes: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(image_bytes))
    return ImageOps.exif_transpose(image).convert("RGB")


def fit_image_to_canvas(image: Image.Image, width: int, height: int) -> Image.Image:
    canvas = Image.new("RGB", (width, height), (242, 235, 219))
    src_w, src_h = image.size
    scale = min(width / src_w, height / src_h) * 0.92
    new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
    resized = image.resize(new_size, Image.LANCZOS)
    x = (width - new_size[0]) // 2
    y = (height - new_size[1]) // 2
    canvas.paste(resized, (x, y))
    return canvas


def pil_to_cv_gray(image: Image.Image) -> np.ndarray:
    rgb = np.array(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def create_sketch_map(image: Image.Image, settings: RenderSettings) -> tuple[np.ndarray, np.ndarray, Image.Image]:
    """Return gray sketch image, darkness map 0..1, and preview PIL image."""
    gray = pil_to_cv_gray(image)
    gray = cv2.equalizeHist(gray)
    strength = settings.sketch_strength / 100

    if settings.input_type == "photo":
        inv = 255 - gray
        blur_size = int(13 + strength * 34)
        if blur_size % 2 == 0:
            blur_size += 1
        blur = cv2.GaussianBlur(inv, (blur_size, blur_size), 0)
        dodge = cv2.divide(gray, 255 - blur, scale=256)
        edges = cv2.Canny(gray, int(45 - 20 * strength), int(130 + 60 * strength))
        edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
        adaptive = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            int(8 + strength * 8),
        )
        sketch = cv2.addWeighted(dodge, 0.78, adaptive, 0.22, 0)
        sketch = np.minimum(sketch, 255 - (edges * (0.35 + strength * 0.45))).clip(0, 255).astype(np.uint8)
    else:
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        adaptive = cv2.adaptiveThreshold(
            blur,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            25,
            int(7 + strength * 9),
        )
        sketch = cv2.addWeighted(gray, 0.32, adaptive, 0.68, 0)

    contrast = 1.0 + strength * 0.85
    sketch = np.clip((sketch.astype(np.float32) - 128) * contrast + 128, 0, 255).astype(np.uint8)
    sketch = cv2.medianBlur(sketch, 3)
    darkness = (255 - sketch).astype(np.float32) / 255.0
    darkness[darkness < 0.08] = 0

    preview = Image.fromarray(sketch, mode="L").convert("RGB")
    return sketch, darkness, preview


def image_to_data_url(image: Image.Image, fmt: str = "PNG") -> str:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def infer_subject_type(settings: RenderSettings, darkness: np.ndarray) -> str:
    if settings.subject_type != "auto":
        return settings.subject_type

    h, w = darkness.shape
    ys, xs = np.where(darkness > 0.18)
    if len(xs) < 200:
        return "product"

    x_min, x_max = xs.min() / w, xs.max() / w
    y_min, y_max = ys.min() / h, ys.max() / h
    bw, bh = x_max - x_min, y_max - y_min
    center_density = darkness[int(h * 0.2): int(h * 0.75), int(w * 0.25): int(w * 0.75)].mean()
    top_density = darkness[: int(h * 0.28), :].mean()
    lower_line_density = darkness[int(h * 0.55):, :].mean()

    if center_density > 0.08 and 0.35 < bw < 0.82 and 0.42 < bh < 0.9 and top_density > 0.035:
        return "portrait"
    if lower_line_density > 0.05 and bw > 0.55:
        return "architecture"
    return "product"


def make_stroke_plan(image_bytes: bytes, settings: RenderSettings) -> tuple[StrokePlan, Image.Image, Image.Image]:
    rng = random.Random(settings.seed)
    source = fit_image_to_canvas(image_from_bytes(image_bytes), settings.width, settings.height)
    sketch, darkness, preview = create_sketch_map(source, settings)
    subject = infer_subject_type(settings, darkness)
    art_director = parse_art_director_json(settings.art_director_json) if settings.planning_mode == "art_director_json" else {}
    if art_director.get("subject_type"):
        subject = str(art_director["subject_type"])

    semantic_regions = detect_semantic_regions(darkness, subject, settings.width, settings.height)
    layer_plan = build_layer_plan(subject, semantic_regions)

    strokes: list[Stroke] = []

    if settings.construction_pass:
        strokes.extend(create_layout_strokes(darkness, subject, settings, rng, semantic_regions))

    extraction_mode = getattr(settings, "stroke_extraction_mode", "hybrid")
    contour_strokes: list[Stroke] = []
    centerline_strokes: list[Stroke] = []
    if extraction_mode in {"contour", "hybrid"}:
        contour_strokes = extract_contour_strokes(sketch, darkness, subject, settings, rng)
    if extraction_mode in {"centerline", "hybrid"}:
        centerline_strokes = extract_centerline_strokes(sketch, darkness, subject, settings, rng)
    hatch_strokes = extract_hatching_strokes(darkness, subject, settings, rng)
    accent_strokes = extract_accent_strokes(sketch, darkness, subject, settings, rng) if settings.accent_pass else []
    # Centerline strokes are closer to real pen/pencil movement. In hybrid mode,
    # keep contours for strong silhouettes but let centerlines handle internal details.
    strokes.extend(centerline_strokes)
    strokes.extend(contour_strokes)
    strokes.extend(hatch_strokes)
    strokes.extend(accent_strokes)

    if settings.smudge_pass:
        strokes.extend(create_smudge_strokes(darkness, subject, settings, rng))
    if settings.eraser_pass:
        strokes.extend(create_eraser_strokes(darkness, subject, settings, rng))

    if not strokes:
        strokes.extend(create_fallback_strokes(settings, rng))

    apply_semantic_region_detection(strokes, semantic_regions)
    apply_art_director_to_strokes(strokes, art_director, settings)

    # Limit total strokes while preserving layer variety.
    strokes = limit_strokes(strokes, settings.max_strokes)
    apply_artist_order(strokes, subject, settings, rng)
    apply_art_director_to_order(strokes, art_director)
    assign_timing(strokes, settings, rng)
    summary = summarize_passes(strokes)

    warnings = []
    if len(strokes) < 80:
        warnings.append("Low stroke count detected. Try higher sketch strength or denser input.")
    if settings.pencil_audio and settings.duration_seconds > 90:
        warnings.append("Long audio tracks are generated procedurally and may sound repetitive.")
    if settings.trace_mode != "opencv":
        warnings.append("Vector tracing hook is enabled. If Potrace/VTracer is installed, the renderer can export SVG sidecars; OpenCV strokes are still used for animation in Batch 4.")
    if settings.planning_mode == "art_director_json" and not art_director:
        warnings.append("Art Director JSON mode was selected, but no valid JSON plan was provided. Rule-based planning was used.")
    if getattr(settings, "stroke_extraction_mode", "hybrid") in {"centerline", "hybrid"}:
        center_count = sum(1 for stroke in strokes if stroke.id.startswith("centerline_"))
        if center_count < 30:
            warnings.append("Centerline extraction produced few strokes. Try higher sketch strength or switch to Hybrid mode for stronger contour backup.")
    if not semantic_regions:
        warnings.append("Semantic region detection returned no focused regions, so generic artist planning was used.")

    return StrokePlan(
        subject,
        settings.to_dict(),
        strokes,
        summary,
        warnings,
        art_director,
        semantic_regions=[region.to_dict() for region in semantic_regions],
        layer_plan=layer_plan,
    ), source, preview



def apply_semantic_region_detection(strokes: list[Stroke], semantic_regions: list[SemanticRegion]) -> None:
    if not semantic_regions:
        return
    for stroke in strokes:
        x1, y1, x2, y2 = stroke.bbox
        center = ((x1 + x2) / 2, (y1 + y2) / 2)
        region = select_region_for_stroke(stroke.bbox, center, semantic_regions)
        if region is None:
            continue
        stroke.region = region.name
        stroke.layer = decide_semantic_layer(stroke.layer, region, stroke.length, stroke.darkness, stroke.effect)
        stroke.order_score = min(stroke.order_score, LAYER_WEIGHT.get(stroke.layer, 50) + region.priority)



def parse_art_director_json(raw: str) -> dict[str, object]:
    if not raw or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def apply_art_director_to_strokes(strokes: list[Stroke], plan: dict[str, object], settings: RenderSettings) -> None:
    """Apply a user/AI supplied planning JSON to the deterministic stroke plan.

    Supported JSON shape:
    {
      "subject_type": "portrait",
      "region_priority": {"left_eye": -25, "right_eye": -25, "hair_top": 12},
      "layer_priority": {"layout": 5, "contour": 15, "key": 25},
      "region_layer_overrides": {"left_eye": "key", "right_eye": "key"}
    }
    Lower priority means earlier drawing. Positive means later drawing.
    """
    if not plan:
        return
    region_layer_overrides = plan.get("region_layer_overrides", {})
    if isinstance(region_layer_overrides, dict):
        for stroke in strokes:
            layer = region_layer_overrides.get(stroke.region)
            if isinstance(layer, str) and layer in LAYER_WEIGHT:
                stroke.layer = layer
                stroke.order_score = LAYER_WEIGHT[layer]

    layer_priority = plan.get("layer_priority", {})
    region_priority = plan.get("region_priority", {})
    if not isinstance(layer_priority, dict):
        layer_priority = {}
    if not isinstance(region_priority, dict):
        region_priority = {}
    for stroke in strokes:
        try:
            stroke.order_score += float(layer_priority.get(stroke.layer, 0))
        except (TypeError, ValueError):
            pass
        try:
            stroke.order_score += float(region_priority.get(stroke.region, 0))
        except (TypeError, ValueError):
            pass


def apply_art_director_to_order(strokes: list[Stroke], plan: dict[str, object]) -> None:
    if not plan:
        return
    region_priority = plan.get("region_priority", {})
    layer_priority = plan.get("layer_priority", {})
    if not isinstance(region_priority, dict):
        region_priority = {}
    if not isinstance(layer_priority, dict):
        layer_priority = {}
    for stroke in strokes:
        try:
            stroke.order_score += float(region_priority.get(stroke.region, 0))
        except (TypeError, ValueError):
            pass
        try:
            stroke.order_score += float(layer_priority.get(stroke.layer, 0))
        except (TypeError, ValueError):
            pass
    strokes.sort(key=lambda s: (s.order_score, s.region, s.start_ms))

def create_layout_strokes(darkness: np.ndarray, subject: str, settings: RenderSettings, rng: random.Random, semantic_regions: list[SemanticRegion] | None = None) -> list[Stroke]:
    h, w = darkness.shape
    ys, xs = np.where(darkness > 0.12)
    if len(xs) < 20:
        return []
    x1, x2 = float(xs.min()), float(xs.max())
    y1, y2 = float(ys.min()), float(ys.max())
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    bw, bh = x2 - x1, y2 - y1
    strokes: list[Stroke] = []
    region_lookup = {region.name: region for region in (semantic_regions or [])}

    def add(points: list[tuple[float, float]], name: str, opacity: float = 0.14, region_name: str | None = None):
        region = region_name or region_from_point(cx, cy, subject, settings.width, settings.height)
        strokes.append(build_stroke(
            f"layout_{name}_{len(strokes)}",
            points,
            "layout",
            region,
            0.12,
            settings,
            rng,
            opacity_override=opacity,
            thickness_override=0.8,
        ))

    if subject == "portrait":
        # Oval head guide and face center/feature guides.
        face_box = region_lookup.get("face_outline")
        left_eye = region_lookup.get("left_eye")
        right_eye = region_lookup.get("right_eye")
        mouth = region_lookup.get("mouth")
        if face_box:
            fx1, fy1, fx2, fy2 = face_box.bbox
            fc_x, fc_y = (fx1 + fx2) / 2, (fy1 + fy2) / 2
            f_bw, f_bh = fx2 - fx1, fy2 - fy1
            add(ellipse_points(fc_x, fc_y, f_bw * 0.48, f_bh * 0.52, 70), "head_oval", region_name="face_outline")
            add([(fc_x, fy1 + f_bh * 0.06), (fc_x + rng.uniform(-5, 5), fy2 - f_bh * 0.05)], "centerline", region_name="face_outline")
        else:
            add(ellipse_points(cx, cy, bw * 0.42, bh * 0.48, 70), "head_oval", region_name="face_outline")
            add([(cx, y1 + bh * 0.08), (cx + rng.uniform(-5, 5), y2 - bh * 0.04)], "centerline", region_name="face_outline")
        if left_eye and right_eye:
            lx1, ly1, lx2, ly2 = left_eye.bbox
            rx1, ry1, rx2, ry2 = right_eye.bbox
            y_eye = ((ly1 + ly2) / 2 + (ry1 + ry2) / 2) / 2
            add([(lx1, y_eye), (rx2, y_eye)], "eye_line", region_name="left_eye")
        else:
            add([(x1 + bw * 0.22, y1 + bh * 0.42), (x2 - bw * 0.22, y1 + bh * 0.42)], "eye_line", region_name="left_eye")
        if mouth:
            mx1, my1, mx2, my2 = mouth.bbox
            y_m = (my1 + my2) / 2
            add([(mx1, y_m), (mx2, y_m)], "mouth_line", region_name="mouth")
        else:
            add([(x1 + bw * 0.31, y1 + bh * 0.60), (x2 - bw * 0.31, y1 + bh * 0.60)], "mouth_line", region_name="mouth")
    elif subject == "architecture":
        roof = region_lookup.get("roof")
        entrance = region_lookup.get("entrance")
        ground = region_lookup.get("ground")
        if roof:
            rx1, ry1, rx2, ry2 = roof.bbox
            add([(rx1, y2), ((rx1 + rx2) / 2, ry1), (rx2, y2)], "silhouette", region_name="roof")
        else:
            add([(x1, y2), (cx, y1), (x2, y2)], "silhouette", region_name="roof")
        if ground:
            gx1, gy1, gx2, gy2 = ground.bbox
            add([(gx1, gy1), (gx2, gy1)], "ground", region_name="ground")
        else:
            add([(x1, y2), (x2, y2)], "ground", region_name="ground")
        if entrance:
            ex1, ey1, ex2, ey2 = entrance.bbox
            add(rect_points(ex1, ey1, ex2, ey2), "door_frame", opacity=0.13, region_name="entrance")
        for i in range(1, 4):
            x = x1 + bw * i / 4
            add([(x, y1 + bh * 0.25), (x, y2)], f"vertical_{i}", opacity=0.12, region_name="central_structure")
    else:
        add(rect_points(x1, y1, x2, y2), "bbox", region_name="overall_subject")
        add([(x1, cy), (x2, cy)], "horizontal", region_name="overall_subject")
        add([(cx, y1), (cx, y2)], "vertical", region_name="overall_subject")
    return strokes


def extract_contour_strokes(sketch: np.ndarray, darkness: np.ndarray, subject: str, settings: RenderSettings, rng: random.Random) -> list[Stroke]:
    density = settings.stroke_density / 100
    # Dark binary for contour/line extraction.
    threshold = int(235 - settings.sketch_strength * 1.15)
    binary = (sketch < threshold).astype(np.uint8) * 255
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    strokes: list[Stroke] = []
    min_len = 18 - density * 10
    max_contours = int(220 + 900 * density)
    contours = sorted(contours, key=lambda c: cv2.arcLength(c, False), reverse=True)[:max_contours]

    for idx, contour in enumerate(contours):
        if len(contour) < 4:
            continue
        length = float(cv2.arcLength(contour, False))
        if length < min_len:
            continue
        epsilon = max(0.8, length * 0.006)
        approx = cv2.approxPolyDP(contour, epsilon, False)
        points = [(float(p[0][0]), float(p[0][1])) for p in approx]
        if len(points) < 2:
            continue
        x, y, bw, bh = cv2.boundingRect(contour)
        cx, cy = x + bw / 2, y + bh / 2
        avg_darkness = sample_darkness(darkness, points)
        region = region_from_point(cx, cy, subject, settings.width, settings.height)
        layer = classify_contour_layer(points, length, avg_darkness, (x, y, bw, bh), region, subject, settings)
        if layer == "accent" and not settings.accent_pass:
            layer = "secondary"
        chunked = split_long_polyline(points, max_segment=120 - 65 * density)
        for part_index, part in enumerate(chunked):
            if len(part) < 2 or polyline_length(part) < min_len * 0.7:
                continue
            strokes.append(build_stroke(
                f"contour_{idx}_{part_index}", part, layer, region, avg_darkness, settings, rng
            ))
    return strokes


def extract_centerline_strokes(sketch: np.ndarray, darkness: np.ndarray, subject: str, settings: RenderSettings, rng: random.Random) -> list[Stroke]:
    density = settings.stroke_density / 100
    max_paths = int(250 + settings.max_strokes * (0.62 if getattr(settings, "stroke_extraction_mode", "hybrid") == "centerline" else 0.46))
    min_len = max(8.0, 18 - density * 9)
    paths = make_centerline_paths(sketch, darkness, settings.sketch_strength, max_paths=max_paths, min_length=min_len)
    strokes: list[Stroke] = []
    for idx, path in enumerate(paths):
        x, y, x2, y2 = path.bbox
        bw, bh = max(1, x2 - x), max(1, y2 - y)
        cx, cy = x + bw / 2, y + bh / 2
        region = region_from_point(cx, cy, subject, settings.width, settings.height)
        layer = classify_centerline_layer(path.points, path.length, path.darkness, (x, y, bw, bh), region, subject, settings)
        chunked = split_long_polyline(path.points, max_segment=90 - 45 * density)
        for part_index, part in enumerate(chunked):
            part_len = polyline_length(part)
            if len(part) < 2 or part_len < min_len * 0.65:
                continue
            # Centerlines should feel like a real pencil tip, so use slightly thinner, more confident strokes.
            thickness = STYLE_DEFAULTS[settings.style_type]["thickness"] * (0.58 + path.darkness * 0.95)
            opacity = STYLE_DEFAULTS[settings.style_type]["opacity"] * (0.48 + path.darkness * 0.62)
            strokes.append(build_stroke(
                f"centerline_{idx}_{part_index}",
                part,
                layer,
                region,
                path.darkness,
                settings,
                rng,
                thickness_override=thickness,
                opacity_override=opacity,
            ))
    return strokes


def classify_centerline_layer(
    points: list[tuple[float, float]],
    length: float,
    darkness: float,
    rect: tuple[int, int, int, int],
    region: str,
    subject: str,
    settings: RenderSettings,
) -> str:
    x, y, bw, bh = rect
    area_ratio = (bw * bh) / max(1, settings.width * settings.height)
    if darkness > 0.58 and length < 150:
        return "accent"
    if subject == "portrait" and region in {"left_eye", "right_eye", "nose", "mouth"}:
        return "key"
    if subject == "architecture" and region in {"entrance", "roof", "central_structure", "left_pillars", "right_pillars"}:
        return "key" if darkness > 0.18 or length > 42 else "secondary"
    if subject == "pet" and region in {"left_eye", "right_eye", "nose"}:
        return "key"
    if area_ratio > 0.10 or length > min(settings.width, settings.height) * 0.30:
        return "contour"
    if length < 30 or max(bw, bh) < 22:
        return "texture"
    if darkness > 0.26 and length < 85:
        return "secondary"
    return "secondary"


def extract_hatching_strokes(darkness: np.ndarray, subject: str, settings: RenderSettings, rng: random.Random) -> list[Stroke]:
    h, w = darkness.shape
    density = settings.stroke_density / 100
    step = int(34 - density * 18)
    step = max(10, step)
    strokes: list[Stroke] = []
    gx = cv2.Sobel((darkness * 255).astype(np.uint8), cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel((darkness * 255).astype(np.uint8), cv2.CV_32F, 0, 1, ksize=3)

    for y in range(step, h - step, step):
        for x in range(step, w - step, step):
            block = darkness[max(0, y - step // 2): min(h, y + step // 2), max(0, x - step // 2): min(w, x + step // 2)]
            avg = float(block.mean())
            if avg < 0.08 + (1 - density) * 0.05:
                continue
            if rng.random() > min(0.88, avg * 3.2 + density * 0.25):
                continue

            grad_angle = math.atan2(float(gy[y, x]), float(gx[y, x])) + math.pi / 2
            if abs(float(gx[y, x])) + abs(float(gy[y, x])) < 18:
                # A deliberate hatching angle still feels more human than noise.
                grad_angle = rng.choice([math.radians(35), math.radians(-35), math.radians(12), math.radians(-58)])
            grad_angle += rng.uniform(-0.45, 0.45)
            length = rng.uniform(step * 0.55, step * (1.2 + avg * 2.2))
            dx = math.cos(grad_angle) * length / 2
            dy = math.sin(grad_angle) * length / 2
            points = [(x - dx, y - dy), (x + dx, y + dy)]
            layer = "shading" if avg > 0.16 else "texture"
            region = region_from_point(x, y, subject, settings.width, settings.height)
            strokes.append(build_stroke(
                f"hatch_{len(strokes)}", points, layer, region, avg, settings, rng,
                thickness_override=0.7 + avg * 1.8,
                opacity_override=0.24 + avg * 0.45,
            ))

            # Cross hatch for deeper areas.
            if avg > 0.26 and rng.random() < 0.35 * density:
                angle2 = grad_angle + math.radians(70 + rng.uniform(-12, 12))
                length2 = length * rng.uniform(0.55, 0.9)
                dx2 = math.cos(angle2) * length2 / 2
                dy2 = math.sin(angle2) * length2 / 2
                p2 = [(x - dx2, y - dy2), (x + dx2, y + dy2)]
                strokes.append(build_stroke(
                    f"cross_{len(strokes)}", p2, "shading", region, avg, settings, rng,
                    thickness_override=0.65 + avg * 1.6,
                    opacity_override=0.2 + avg * 0.43,
                ))
    return strokes



def create_smudge_strokes(darkness: np.ndarray, subject: str, settings: RenderSettings, rng: random.Random) -> list[Stroke]:
    """Soft late-pass strokes that blur graphite/charcoal-heavy areas."""
    if settings.style_type not in {"pencil", "charcoal"}:
        return []
    h, w = darkness.shape
    density = settings.stroke_density / 100
    step = max(24, int(58 - density * 24))
    strokes: list[Stroke] = []
    for y in range(step, h - step, step):
        for x in range(step, w - step, step):
            block = darkness[max(0, y - step): min(h, y + step), max(0, x - step): min(w, x + step)]
            avg = float(block.mean())
            if avg < 0.18 or rng.random() > 0.18 + avg * 0.55:
                continue
            angle = rng.choice([0.0, math.radians(22), math.radians(-18), math.radians(55)]) + rng.uniform(-0.18, 0.18)
            length = rng.uniform(step * 0.45, step * 1.05)
            dx = math.cos(angle) * length / 2
            dy = math.sin(angle) * length / 2
            region = region_from_point(x, y, subject, settings.width, settings.height)
            strokes.append(build_stroke(
                f"smudge_{len(strokes)}", [(x - dx, y - dy), (x + dx, y + dy)], "shading", region, avg, settings, rng,
                thickness_override=4.0 + avg * 8.0,
                opacity_override=0.08 + avg * 0.18,
                effect="smudge",
            ))
    return strokes


def create_eraser_strokes(darkness: np.ndarray, subject: str, settings: RenderSettings, rng: random.Random) -> list[Stroke]:
    """Optional light eraser/highlight pass."""
    h, w = darkness.shape
    ys, xs = np.where((darkness > 0.10) & (darkness < 0.24))
    strokes: list[Stroke] = []
    if len(xs) < 100:
        return strokes
    count = min(80, max(10, settings.max_strokes // 60))
    for i in range(count):
        idx = rng.randrange(0, len(xs))
        x = float(xs[idx])
        y = float(ys[idx])
        angle = rng.uniform(-0.55, 0.55)
        length = rng.uniform(18, 85)
        dx = math.cos(angle) * length / 2
        dy = math.sin(angle) * length / 2
        region = region_from_point(x, y, subject, settings.width, settings.height)
        strokes.append(build_stroke(
            f"eraser_{i}", [(x - dx, y - dy), (x + dx, y + dy)], "accent", region, 0.10, settings, rng,
            thickness_override=rng.uniform(4, 11),
            opacity_override=0.24,
            effect="erase",
        ))
    return strokes

def extract_accent_strokes(sketch: np.ndarray, darkness: np.ndarray, subject: str, settings: RenderSettings, rng: random.Random) -> list[Stroke]:
    mask = (darkness > 0.43).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((2, 2), np.uint8), iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:300]
    strokes: list[Stroke] = []
    for idx, contour in enumerate(contours):
        length = float(cv2.arcLength(contour, False))
        area = float(cv2.contourArea(contour))
        if length < 7 or area < 2:
            continue
        epsilon = max(0.7, length * 0.01)
        approx = cv2.approxPolyDP(contour, epsilon, False)
        points = [(float(p[0][0]), float(p[0][1])) for p in approx]
        if len(points) < 2:
            continue
        x, y, bw, bh = cv2.boundingRect(contour)
        cx, cy = x + bw / 2, y + bh / 2
        region = region_from_point(cx, cy, subject, settings.width, settings.height)
        avg = max(0.48, sample_darkness(darkness, points))
        strokes.append(build_stroke(
            f"accent_{idx}", points, "accent", region, avg, settings, rng,
            thickness_override=1.0 + avg * STYLE_DEFAULTS[settings.style_type]["thickness"] * 1.45,
            opacity_override=min(0.95, 0.45 + avg * 0.62),
        ))
    return strokes


def build_stroke(
    stroke_id: str,
    points: list[tuple[float, float]],
    layer: str,
    region: str,
    darkness: float,
    settings: RenderSettings,
    rng: random.Random,
    opacity_override: float | None = None,
    thickness_override: float | None = None,
    effect: str = "draw",
) -> Stroke:
    defaults = STYLE_DEFAULTS[settings.style_type]
    length = polyline_length(points)
    bbox = bbox_from_points(points)
    darkness = float(max(0.02, min(1.0, darkness)))
    thickness = thickness_override if thickness_override is not None else defaults["thickness"] * (0.72 + darkness * 1.35)
    opacity = opacity_override if opacity_override is not None else defaults["opacity"] * (0.52 + darkness * 0.72)
    jitter = defaults["jitter"] * (settings.human_randomness / 60 if settings.human_randomness else 0.05)
    return Stroke(
        id=stroke_id,
        points=clip_points(points, settings.width, settings.height),
        layer=layer,
        region=region,
        order_score=LAYER_WEIGHT.get(layer, 50),
        darkness=darkness,
        thickness=max(0.35, float(thickness)),
        speed=stroke_speed(layer, length, darkness),
        opacity=max(0.05, min(1.0, float(opacity))),
        jitter=max(0.0, float(jitter)),
        bbox=bbox,
        length=float(length),
        effect=effect,
    )


def classify_contour_layer(
    points: list[tuple[float, float]],
    length: float,
    darkness: float,
    rect: tuple[int, int, int, int],
    region: str,
    subject: str,
    settings: RenderSettings,
) -> str:
    x, y, bw, bh = rect
    area_ratio = (bw * bh) / max(1, settings.width * settings.height)
    compact = length / max(1.0, math.sqrt(max(1, bw * bw + bh * bh)))

    if darkness > 0.50 and length < 180:
        return "accent"
    if area_ratio > 0.08 or length > min(settings.width, settings.height) * 0.27:
        return "contour"
    if subject == "portrait" and region in {"left_eye", "right_eye", "nose", "mouth"}:
        return "key"
    if subject == "architecture" and region in {"entrance", "roof", "central_structure"}:
        return "key"
    if subject == "pet" and region in {"left_eye", "right_eye", "nose"}:
        return "key"
    if compact > 4.2 or length < 42:
        return "texture"
    return "secondary"


def region_from_point(x: float, y: float, subject: str, width: int, height: int) -> str:
    xn, yn = x / width, y / height
    if subject == "portrait":
        if yn < 0.25:
            return "hair_top"
        if 0.30 <= yn <= 0.48 and 0.25 <= xn < 0.48:
            return "left_eye"
        if 0.30 <= yn <= 0.48 and 0.52 <= xn <= 0.75:
            return "right_eye"
        if 0.42 <= yn <= 0.62 and 0.42 <= xn <= 0.58:
            return "nose"
        if 0.58 <= yn <= 0.74 and 0.35 <= xn <= 0.65:
            return "mouth"
        if yn < 0.68 and 0.24 <= xn <= 0.76:
            return "face_outline"
        if yn >= 0.68:
            return "neck_clothing"
        return "hair_side"
    if subject == "architecture":
        if yn < 0.28:
            return "roof"
        if 0.36 <= xn <= 0.64 and yn > 0.40:
            return "entrance"
        if yn > 0.75:
            return "ground"
        if 0.23 <= xn <= 0.77:
            return "central_structure"
        return "side_structure"
    if subject == "pet":
        if 0.24 <= yn <= 0.48 and 0.25 <= xn < 0.48:
            return "left_eye"
        if 0.24 <= yn <= 0.48 and 0.52 <= xn <= 0.75:
            return "right_eye"
        if 0.40 <= yn <= 0.62 and 0.38 <= xn <= 0.62:
            return "nose"
        if yn < 0.60:
            return "head"
        return "body_fur"
    if subject == "landscape":
        if yn < 0.32:
            return "sky_background"
        if yn < 0.62:
            return "horizon_midground"
        return "foreground"
    if subject == "logo":
        if 0.32 <= xn <= 0.68 and 0.30 <= yn <= 0.70:
            return "logo_core"
        return "logo_outer"
    if yn > 0.72:
        return "shadow_base"
    if 0.25 <= xn <= 0.75 and 0.2 <= yn <= 0.75:
        return "main_object"
    return "outer_details"


def subject_priority_adjustment(region: str, layer: str, subject: str) -> float:
    if subject == "portrait":
        priority = {
            "overall_subject": -14,
            "face_outline": -8,
            "left_eye": -18,
            "right_eye": -18,
            "nose": -10,
            "mouth": -7,
            "hair_top": 10,
            "hair_side": 12,
            "jaw_cheek": 8,
            "neck_clothing": 15,
        }.get(region, 0)
        if layer == "accent" and region in {"left_eye", "right_eye"}:
            priority += 22  # pupils/dark marks near the end
        return priority
    if subject == "architecture":
        priority = {
            "overall_subject": -18,
            "roof": -14,
            "central_structure": -9,
            "entrance": -8,
            "left_pillars": -4,
            "right_pillars": -4,
            "carvings": 10,
            "side_structure": 5,
            "ground": 14,
        }.get(region, 0)
        if layer in {"texture", "shading"} and region in {"roof", "central_structure"}:
            priority += 10
        return priority
    if subject == "pet":
        priority = {"overall_subject": -12, "head": -10, "left_eye": -16, "right_eye": -16, "nose": -12, "ears": 4, "body_fur": 10}.get(region, 0)
        if layer == "accent" and region in {"left_eye", "right_eye", "nose"}:
            priority += 18
        return priority
    if subject == "logo":
        return {"logo_core": -12, "logo_outer": 6, "overall_subject": -10}.get(region, 0)
    return {"overall_subject": -12, "main_object": -8, "detail_core": -3, "shadow_base": 15, "outer_details": 8}.get(region, 0)


def apply_artist_order(strokes: list[Stroke], subject: str, settings: RenderSettings, rng: random.Random) -> None:
    randomness = settings.human_randomness / 100
    for stroke in strokes:
        x1, y1, x2, y2 = stroke.bbox
        cx = (x1 + x2) / 2 / settings.width
        cy = (y1 + y2) / 2 / settings.height
        center_bias = (abs(cx - 0.5) + abs(cy - 0.48)) * 8
        size_bias = -min(10, stroke.length / 75) if stroke.layer == "contour" else min(8, stroke.length / 180)
        dark_bias = stroke.darkness * (14 if stroke.layer not in {"accent", "layout"} else 4)
        region_bias = subject_priority_adjustment(stroke.region, stroke.layer, subject)
        jitter = rng.uniform(-16, 16) * randomness
        revisit_bias = 0
        # A small subset of previous-looking lines get delayed as rework/strengthening.
        if stroke.layer in {"contour", "secondary"} and stroke.darkness > 0.32 and rng.random() < 0.12 * randomness:
            revisit_bias += rng.uniform(18, 38)
            stroke.layer = "accent" if settings.accent_pass else "secondary"
        stroke.order_score = LAYER_WEIGHT.get(stroke.layer, 50) + center_bias + size_bias + dark_bias + region_bias + revisit_bias + jitter
    strokes.sort(key=lambda s: (s.order_score, s.region, s.length))

    # Within the same pass, make short bursts around nearby regions so movement feels hand-driven.
    for layer in LAYER_WEIGHT:
        indices = [i for i, s in enumerate(strokes) if s.layer == layer]
        if len(indices) < 12:
            continue
        subset = [strokes[i] for i in indices]
        subset.sort(key=lambda s: (s.region, s.bbox[1] + rng.uniform(-settings.height * 0.05, settings.height * 0.05), s.bbox[0]))
        for pos, original_index in enumerate(indices):
            strokes[original_index] = subset[pos]


def assign_timing(strokes: list[Stroke], settings: RenderSettings, rng: random.Random) -> None:
    desired_total = settings.duration_seconds * 1000
    raw_units: list[float] = []
    randomness = settings.human_randomness / 100
    for stroke in strokes:
        base = 70 + stroke.length * stroke.speed
        if stroke.layer == "key":
            base *= 1.18
        if stroke.layer == "shading":
            base *= 0.55
        if stroke.layer == "texture":
            base *= 0.62
        if stroke.layer == "accent":
            base *= 0.92
        base *= rng.uniform(0.75, 1.25 + randomness * 0.3)
        raw_units.append(max(4, base))

    if not raw_units:
        return
    scale = desired_total / sum(raw_units)
    t = 0
    previous_layer = strokes[0].layer
    previous_region = strokes[0].region
    for stroke, units in zip(strokes, raw_units):
        pause = 0
        if stroke.layer != previous_layer:
            pause += int(rng.uniform(120, 460) * (0.35 + randomness))
        elif stroke.region != previous_region and rng.random() < 0.28 + randomness * 0.28:
            pause += int(rng.uniform(45, 180) * (0.3 + randomness))
        if stroke.layer == "key" and rng.random() < 0.16:
            pause += int(rng.uniform(80, 260))
        duration = max(3, int(units * scale))
        stroke.delay_ms = pause
        stroke.start_ms = t + pause
        stroke.duration_ms = duration
        stroke.end_ms = stroke.start_ms + duration
        t = stroke.end_ms
        previous_layer = stroke.layer
        previous_region = stroke.region

    # Rescale once more because pauses added time.
    actual_total = max(1, strokes[-1].end_ms)
    factor = desired_total / actual_total
    t2 = 0
    for stroke in strokes:
        pause = int(stroke.delay_ms * factor)
        duration = max(3, int(stroke.duration_ms * factor))
        stroke.delay_ms = pause
        stroke.start_ms = t2 + pause
        stroke.duration_ms = duration
        stroke.end_ms = stroke.start_ms + duration
        t2 = stroke.end_ms


def summarize_passes(strokes: list[Stroke]) -> list[dict[str, object]]:
    counts = Counter(s.layer for s in strokes)
    summary = []
    for layer in ["layout", "contour", "key", "secondary", "texture", "shading", "accent"]:
        if counts[layer]:
            layer_strokes = [s for s in strokes if s.layer == layer]
            summary.append({
                "id": layer,
                "name": PASS_NAMES[layer],
                "description": PASS_DESCRIPTIONS[layer],
                "stroke_count": counts[layer],
                "start_ms": min(s.start_ms for s in layer_strokes),
                "end_ms": max(s.end_ms for s in layer_strokes),
            })
    return summary


def limit_strokes(strokes: list[Stroke], max_strokes: int) -> list[Stroke]:
    if len(strokes) <= max_strokes:
        return strokes
    buckets: dict[str, list[Stroke]] = defaultdict(list)
    for stroke in strokes:
        buckets[stroke.layer].append(stroke)
    reserved = {"layout": 40, "contour": 380, "key": 250, "secondary": 360, "texture": 320, "shading": 360, "accent": 180}
    total_reserved = sum(reserved.values())
    scale = max_strokes / total_reserved
    kept: list[Stroke] = []
    for layer, bucket in buckets.items():
        bucket.sort(key=lambda s: (s.darkness + min(1, s.length / 280)), reverse=True)
        limit = max(10, int(reserved.get(layer, 150) * scale))
        kept.extend(bucket[:limit])
    return kept[:max_strokes]


def split_long_polyline(points: list[tuple[float, float]], max_segment: float) -> list[list[tuple[float, float]]]:
    if polyline_length(points) <= max_segment:
        return [points]
    parts: list[list[tuple[float, float]]] = []
    current = [points[0]]
    current_len = 0.0
    for a, b in zip(points, points[1:]):
        seg = math.dist(a, b)
        current.append(b)
        current_len += seg
        if current_len >= max_segment:
            parts.append(current)
            current = [b]
            current_len = 0.0
    if len(current) > 1:
        parts.append(current)
    return parts


def create_fallback_strokes(settings: RenderSettings, rng: random.Random) -> list[Stroke]:
    strokes = []
    cx, cy = settings.width / 2, settings.height / 2
    for i, radius in enumerate(np.linspace(70, min(settings.width, settings.height) * 0.36, 14)):
        pts = ellipse_points(cx, cy, radius * 0.75, radius, 90)
        strokes.append(build_stroke(f"fallback_{i}", pts, "contour", "main_object", 0.2, settings, rng))
    return strokes


def sample_darkness(darkness: np.ndarray, points: Iterable[tuple[float, float]]) -> float:
    h, w = darkness.shape
    vals = []
    for x, y in points:
        xi = max(0, min(w - 1, int(round(x))))
        yi = max(0, min(h - 1, int(round(y))))
        vals.append(float(darkness[yi, xi]))
    return float(np.mean(vals)) if vals else 0.1


def polyline_length(points: list[tuple[float, float]]) -> float:
    return float(sum(math.dist(a, b) for a, b in zip(points, points[1:])))


def bbox_from_points(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def clip_points(points: list[tuple[float, float]], width: int, height: int) -> list[tuple[float, float]]:
    return [(max(0.0, min(width - 1.0, x)), max(0.0, min(height - 1.0, y))) for x, y in points]


def ellipse_points(cx: float, cy: float, rx: float, ry: float, count: int) -> list[tuple[float, float]]:
    return [
        (cx + math.cos(i / (count - 1) * math.tau) * rx, cy + math.sin(i / (count - 1) * math.tau) * ry)
        for i in range(count)
    ]


def rect_points(x1: float, y1: float, x2: float, y2: float) -> list[tuple[float, float]]:
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]


def stroke_speed(layer: str, length: float, darkness: float) -> float:
    if layer == "layout":
        return 0.55
    if layer == "contour":
        return 0.95
    if layer == "key":
        return 1.15
    if layer == "texture":
        return 0.45
    if layer == "shading":
        return 0.36
    if layer == "accent":
        return 0.75 + darkness * 0.2
    return 0.72
