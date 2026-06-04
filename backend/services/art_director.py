from __future__ import annotations

import io
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps


SUBJECT_LABELS = {
    "portrait": "Portrait / face-focused sketch",
    "architecture": "Temple / architecture / structural sketch",
    "pet": "Pet / animal sketch",
    "product": "Product / object sketch",
    "landscape": "Landscape / environment sketch",
    "logo": "Logo / icon sketch",
}


def _image_from_bytes(data: bytes) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")


def _safe_stem(name: str) -> str:
    stem = Path(name or "scene").stem.replace("_", " ").replace("-", " ").strip()
    stem = re.sub(r"\s+", " ", stem)
    return stem[:60] or "Sketch scene"


def _to_gray(image: Image.Image, max_side: int = 900) -> np.ndarray:
    copy = image.copy()
    copy.thumbnail((max_side, max_side), Image.LANCZOS)
    arr = np.array(copy.convert("RGB"))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)


def _detect_face_count(gray: np.ndarray) -> int:
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            return 0
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(35, 35))
        return int(len(faces))
    except Exception:
        return 0


def _edge_stats(gray: np.ndarray) -> dict[str, float]:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blur, 80, 180)
    edge_density = float(np.mean(edges > 0))
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = float(lap.var())
    contrast = float(gray.std())
    brightness = float(gray.mean())
    # Hough-line proxy for architecture/structure.
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=45, minLineLength=max(24, gray.shape[1] // 10), maxLineGap=8)
    line_count = 0 if lines is None else int(len(lines))
    # Component density proxy for logos/icons or sparse subjects.
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA] if num_labels > 1 else np.array([])
    significant_components = int(np.sum((areas > 12) & (areas < gray.size * 0.35))) if areas.size else 0
    return {
        "edge_density": edge_density,
        "sharpness": sharpness,
        "contrast": contrast,
        "brightness": brightness,
        "line_count": line_count,
        "significant_components": significant_components,
    }


def _rule_subject(gray: np.ndarray, filename: str = "") -> tuple[str, dict[str, float]]:
    stats = _edge_stats(gray)
    face_count = _detect_face_count(gray)
    lower_name = filename.lower()
    scores = {
        "portrait": 0.0,
        "architecture": 0.0,
        "pet": 0.0,
        "product": 0.0,
        "landscape": 0.0,
        "logo": 0.0,
    }
    if face_count:
        scores["portrait"] += 4.0 + min(face_count, 3) * 0.75
    if any(word in lower_name for word in ["portrait", "face", "person", "girl", "boy", "man", "woman", "kid", "child"]):
        scores["portrait"] += 2.0
    if any(word in lower_name for word in ["temple", "mandir", "church", "building", "architecture", "house", "palace", "street"]):
        scores["architecture"] += 2.8
    if any(word in lower_name for word in ["dog", "cat", "pet", "animal", "puppy", "kitten", "bird"]):
        scores["pet"] += 2.5
    if any(word in lower_name for word in ["logo", "icon", "badge", "mark"]):
        scores["logo"] += 3.0
    if any(word in lower_name for word in ["landscape", "mountain", "river", "forest", "lake", "beach", "sky"]):
        scores["landscape"] += 2.2

    line_density_score = min(3.0, stats["line_count"] / 16.0)
    edge_density = stats["edge_density"]
    comp = stats["significant_components"]
    scores["architecture"] += line_density_score + max(0.0, (edge_density - 0.08) * 8)
    scores["logo"] += 1.4 if comp <= 8 and edge_density < 0.12 else 0.0
    scores["landscape"] += 1.0 if stats["line_count"] < 10 and 0.04 < edge_density < 0.18 else 0.0
    scores["product"] += 1.2 if max(scores.values()) < 2.0 else 0.0
    if edge_density > 0.22 and face_count == 0:
        scores["architecture"] += 0.7
    subject = max(scores, key=scores.get)
    if scores[subject] < 1.2:
        subject = "product"
    return subject, scores


def _quality_score(stats: dict[str, float], width: int, height: int) -> tuple[int, list[str], list[str]]:
    warnings: list[str] = []
    fixes: list[str] = []
    score = 100
    if width < 600 or height < 600:
        score -= 18
        warnings.append("Input resolution is low for final-quality rendering.")
        fixes.append("Use a larger source image or render in Preview/Standard first.")
    sharpness = stats["sharpness"]
    if sharpness < 45:
        score -= 20
        warnings.append("Image appears soft or blurry.")
        fixes.append("Increase sketch strength, use Hybrid extraction, or choose a sharper source.")
    elif sharpness < 95:
        score -= 9
        warnings.append("Image sharpness is moderate; fine strokes may be weaker.")
        fixes.append("Use stronger sketch settings or a cleaner source crop.")
    if stats["brightness"] < 45 or stats["brightness"] > 220:
        score -= 12
        warnings.append("Image brightness is extreme, which can reduce stroke extraction quality.")
        fixes.append("Adjust exposure/contrast before rendering.")
    if stats["contrast"] < 28:
        score -= 16
        warnings.append("Image contrast is low; extracted strokes may look flat.")
        fixes.append("Increase contrast or sketch strength.")
    if stats["edge_density"] < 0.015:
        score -= 18
        warnings.append("Very few edges detected; final video may have too few strokes.")
        fixes.append("Use a more detailed image or increase sketch strength/stroke density.")
    elif stats["edge_density"] > 0.34:
        score -= 10
        warnings.append("Very dense edges detected; the render may look noisy or crowded.")
        fixes.append("Lower stroke density or use Contour/Hybrid extraction with fewer max strokes.")
    return max(0, min(100, int(round(score)))), warnings, fixes


def _recommended_style(subject: str, stats: dict[str, float]) -> str:
    if subject == "architecture":
        return "ink" if stats["line_count"] > 18 else "pencil"
    if subject == "portrait":
        return "pencil"
    if subject == "logo":
        return "ink"
    if subject == "landscape":
        return "charcoal"
    if subject == "pet":
        return "pencil"
    return "marker" if stats["edge_density"] < 0.08 else "pencil"


def _settings_suggestions(subject: str, style: str, quality: int, stats: dict[str, float]) -> dict[str, Any]:
    settings = {
        "subject_type": subject,
        "style_type": style,
        "stroke_extraction_mode": "hybrid",
        "planning_mode": "art_director_json",
        "render_quality": "standard" if quality < 75 else "final",
        "sketch_strength": 72,
        "stroke_density": 62,
        "human_randomness": 35,
        "max_strokes": 1800,
        "camera_move_preset": "zoom_in",
        "ambient_track": "studio_room",
    }
    if subject == "portrait":
        settings.update({"stroke_density": 58, "max_strokes": 1800, "camera_move_preset": "ken_burns", "graphite_grain": 70})
    elif subject == "architecture":
        settings.update({"stroke_density": 70, "max_strokes": 2600, "camera_move_preset": "push_in_left", "ink_bleed": 16})
    elif subject == "pet":
        settings.update({"stroke_density": 64, "max_strokes": 2200, "camera_move_preset": "zoom_in", "graphite_grain": 68})
    elif subject == "landscape":
        settings.update({"stroke_density": 68, "max_strokes": 2600, "camera_move_preset": "pan_left_to_right", "charcoal_dust": 72})
    elif subject == "logo":
        settings.update({"stroke_density": 42, "max_strokes": 1000, "camera_move_preset": "static", "ink_bleed": 8})
    if stats["edge_density"] > 0.24:
        settings["stroke_density"] = max(35, int(settings["stroke_density"] * 0.84))
        settings["max_strokes"] = min(int(settings["max_strokes"]), 2200)
    if stats["edge_density"] < 0.04:
        settings["sketch_strength"] = 82
        settings["stroke_density"] = min(85, int(settings["stroke_density"] * 1.16))
    return settings


def _art_director_json(subject: str, stats: dict[str, float]) -> dict[str, Any]:
    if subject == "portrait":
        return {
            "subject_type": "portrait",
            "region_priority": {"left_eye": -24, "right_eye": -24, "nose": -12, "mouth": -8, "face_outline": -8, "hair_top": 12, "neck_clothing": 18},
            "region_layer_overrides": {"left_eye": "key", "right_eye": "key", "nose": "key", "mouth": "key", "hair_top": "texture"},
            "artist_notes": ["Establish likeness through eyes early.", "Keep hair and clothing texture later.", "Save strongest dark accents for the final pass."],
        }
    if subject == "architecture":
        return {
            "subject_type": "architecture",
            "region_priority": {"roof": -18, "central_structure": -14, "entrance": -16, "left_pillars": -8, "right_pillars": -8, "carvings": 14, "ground": 18},
            "region_layer_overrides": {"roof": "contour", "entrance": "key", "carvings": "texture", "ground": "secondary"},
            "artist_notes": ["Draw silhouette and perspective structure first.", "Add entrance and pillars before ornaments.", "Reserve stone texture and shadow accents for later passes."],
        }
    if subject == "pet":
        return {
            "subject_type": "pet",
            "region_priority": {"left_eye": -22, "right_eye": -22, "nose": -18, "head": -10, "ears": 8, "body_fur": 18},
            "region_layer_overrides": {"left_eye": "key", "right_eye": "key", "nose": "key", "body_fur": "texture"},
            "artist_notes": ["Eyes and nose should appear early to establish character.", "Use fur texture as late repeated strokes."],
        }
    if subject == "landscape":
        return {
            "subject_type": "landscape",
            "region_priority": {"horizon_midground": -10, "foreground": 8, "sky_background": 20},
            "region_layer_overrides": {"horizon_midground": "contour", "foreground": "texture", "sky_background": "layout"},
            "artist_notes": ["Set horizon first, then foreground depth.", "Keep sky/background light and sparse."],
        }
    if subject == "logo":
        return {
            "subject_type": "logo",
            "region_priority": {"logo_core": -18, "logo_outer": 8},
            "region_layer_overrides": {"logo_core": "key", "logo_outer": "accent"},
            "artist_notes": ["Keep the logo clean and precise.", "Avoid excessive shading."],
        }
    return {
        "subject_type": "product",
        "region_priority": {"main_object": -14, "detail_core": -6, "outer_details": 8, "shadow_base": 18},
        "region_layer_overrides": {"main_object": "contour", "detail_core": "key", "shadow_base": "shading"},
        "artist_notes": ["Draw the main silhouette first.", "Add product details before base shadow."],
    }


def _caption_suggestions(filename: str, subject: str, style: str) -> dict[str, Any]:
    name = _safe_stem(filename)
    readable_subject = SUBJECT_LABELS.get(subject, "Sketch scene")
    title = name if name.lower() not in {"scene", "image", "photo"} else readable_subject
    return {
        "title": title.title(),
        "caption": f"Watch this {style} sketch come alive stroke by stroke.",
        "short_caption": f"{title.title()} sketch reveal",
        "hashtags": ["#SketchVideo", "#ArtProcess", "#StreetArtist", "#AIVideo"],
    }


def analyze_image_bytes(data: bytes, filename: str = "image.png") -> dict[str, Any]:
    image = _image_from_bytes(data)
    gray = _to_gray(image)
    stats = _edge_stats(gray)
    subject, subject_scores = _rule_subject(gray, filename)
    quality, warnings, fixes = _quality_score(stats, image.width, image.height)
    style = _recommended_style(subject, stats)
    suggestions = _settings_suggestions(subject, style, quality, stats)
    director_json = _art_director_json(subject, stats)
    captions = _caption_suggestions(filename, subject, style)
    return {
        "filename": filename,
        "width": image.width,
        "height": image.height,
        "quality_score": quality,
        "quality_label": "excellent" if quality >= 85 else "good" if quality >= 70 else "needs_attention" if quality >= 50 else "poor",
        "warnings": warnings,
        "suggested_fixes": fixes,
        "detected_subject": subject,
        "subject_label": SUBJECT_LABELS.get(subject, subject),
        "subject_scores": {k: round(float(v), 3) for k, v in subject_scores.items()},
        "image_stats": {k: round(float(v), 4) for k, v in stats.items()},
        "recommended_style": style,
        "recommended_settings": suggestions,
        "art_director_json": director_json,
        "captions": captions,
    }


def analyze_timeline_images(files: list[tuple[str, bytes]]) -> dict[str, Any]:
    scenes: list[dict[str, Any]] = []
    total_score = 0
    for idx, (filename, data) in enumerate(files, start=1):
        analysis = analyze_image_bytes(data, filename)
        total_score += int(analysis["quality_score"])
        transition = "cut" if idx == 1 else "zoomfade" if analysis["detected_subject"] in {"portrait", "product"} else "fade"
        duration = 6 if analysis["quality_score"] >= 65 else 7
        scene = {
            "scene_id": f"scene_{idx:02d}",
            "source": filename,
            "title": analysis["captions"]["title"],
            "duration_seconds": duration,
            "transition": transition,
            "transition_duration": 0.0 if idx == 1 else 0.7,
            "camera_move_preset": analysis["recommended_settings"].get("camera_move_preset", "zoom_in"),
            "ambient_track": analysis["recommended_settings"].get("ambient_track", "studio_room"),
            "subject_type": analysis["detected_subject"],
            "style_type": analysis["recommended_style"],
            "notes": f"Quality {analysis['quality_score']}/100 · {analysis['subject_label']}",
        }
        scenes.append({"scene": scene, "analysis": analysis})
    avg_score = round(total_score / max(1, len(files)), 1)
    return {
        "scene_count": len(files),
        "average_quality_score": avg_score,
        "timeline_json": [row["scene"] for row in scenes],
        "scenes": scenes,
        "global_recommendations": {
            "render_quality": "final" if avg_score >= 78 else "standard",
            "stroke_extraction_mode": "hybrid",
            "planning_mode": "art_director_json",
            "transition_sfx": True,
        },
    }
