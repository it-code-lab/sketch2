from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import cv2
import numpy as np


@dataclass
class SemanticRegion:
    name: str
    role: str
    bbox: tuple[float, float, float, float]
    priority: float
    confidence: float
    preferred_layers: list[str]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["bbox"] = [round(v, 2) for v in self.bbox]
        payload["priority"] = round(self.priority, 3)
        payload["confidence"] = round(self.confidence, 3)
        return payload


def active_bbox(darkness: np.ndarray, threshold: float = 0.1) -> tuple[int, int, int, int]:
    ys, xs = np.where(darkness > threshold)
    h, w = darkness.shape
    if len(xs) < 10:
        return int(w * 0.18), int(h * 0.18), int(w * 0.82), int(h * 0.82)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def clamp_bbox(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> tuple[float, float, float, float]:
    x1 = max(0.0, min(width - 1.0, x1))
    y1 = max(0.0, min(height - 1.0, y1))
    x2 = max(0.0, min(width - 1.0, x2))
    y2 = max(0.0, min(height - 1.0, y2))
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return x1, y1, x2, y2


def density_profiles(darkness: np.ndarray, bbox: tuple[int, int, int, int]) -> tuple[np.ndarray, np.ndarray]:
    x1, y1, x2, y2 = bbox
    crop = darkness[max(0, y1): max(y1 + 1, y2), max(0, x1): max(x1 + 1, x2)]
    if crop.size == 0:
        return np.zeros((1,), dtype=np.float32), np.zeros((1,), dtype=np.float32)
    horizontal = crop.mean(axis=1)
    vertical = crop.mean(axis=0)
    if horizontal.max() > 0:
        horizontal = horizontal / horizontal.max()
    if vertical.max() > 0:
        vertical = vertical / vertical.max()
    return horizontal.astype(np.float32), vertical.astype(np.float32)


def _subbox(parent: tuple[float, float, float, float], rx1: float, ry1: float, rx2: float, ry2: float, width: int, height: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = parent
    bw, bh = (x2 - x1), (y2 - y1)
    return clamp_bbox(x1 + bw * rx1, y1 + bh * ry1, x1 + bw * rx2, y1 + bh * ry2, width, height)


def detect_semantic_regions(darkness: np.ndarray, subject: str, width: int, height: int) -> list[SemanticRegion]:
    h, w = darkness.shape
    x1, y1, x2, y2 = active_bbox(darkness)
    bw, bh = max(1, x2 - x1), max(1, y2 - y1)
    horizontal, vertical = density_profiles(darkness, (x1, y1, x2, y2))
    regions: list[SemanticRegion] = []

    def add(name: str, role: str, bbox: tuple[float, float, float, float], priority: float, confidence: float, preferred_layers: list[str], notes: str = ""):
        regions.append(SemanticRegion(name, role, bbox, priority, float(max(0.05, min(0.99, confidence))), preferred_layers, notes))

    # Shared regions
    add("overall_subject", "anchor", (x1, y1, x2, y2), -20, 0.98, ["layout", "contour"], "Primary subject envelope")

    if subject == "portrait":
        eye_band = 0.38
        mouth_band = 0.68
        if len(horizontal) > 8:
            eye_band = float(np.argmax(horizontal[: max(3, int(len(horizontal) * 0.55))]) / max(1, len(horizontal) - 1))
            eye_band = min(0.5, max(0.28, eye_band))
            lower = horizontal[int(len(horizontal) * 0.45):]
            if len(lower):
                mouth_band = 0.45 + float(np.argmax(lower) / max(1, len(lower) - 1)) * 0.45
                mouth_band = min(0.82, max(0.58, mouth_band))
        face_box = _subbox((x1, y1, x2, y2), 0.10, 0.05, 0.90, 0.86, width, height)
        add("hair_top", "mass", _subbox((x1, y1, x2, y2), 0.05, 0.0, 0.95, max(0.22, eye_band - 0.08), width, height), 14, 0.72, ["secondary", "texture", "shading"], "Hair mass and upper silhouette")
        add("face_outline", "focal", face_box, -12, 0.95, ["contour", "secondary"], "Main face/head boundary")
        add("left_eye", "focal", _subbox(face_box, 0.14, eye_band - 0.10, 0.42, eye_band + 0.06, width, height), -18, 0.86, ["key", "accent"], "Left eye focal area")
        add("right_eye", "focal", _subbox(face_box, 0.58, eye_band - 0.10, 0.86, eye_band + 0.06, width, height), -18, 0.86, ["key", "accent"], "Right eye focal area")
        add("nose", "focal", _subbox(face_box, 0.39, eye_band + 0.02, 0.61, 0.63, width, height), -10, 0.80, ["key", "secondary", "shading"], "Nose bridge and nostril structure")
        add("mouth", "focal", _subbox(face_box, 0.32, mouth_band - 0.06, 0.68, mouth_band + 0.08, width, height), -6, 0.78, ["key", "secondary", "accent"], "Mouth and lips")
        add("jaw_cheek", "form", _subbox(face_box, 0.08, 0.48, 0.92, 0.90, width, height), 6, 0.72, ["secondary", "shading"], "Cheek, jawline, and chin form")
        add("neck_clothing", "support", _subbox((x1, y1, x2, y2), 0.12, 0.78, 0.88, 1.0, width, height), 16, 0.65, ["secondary", "texture", "shading"], "Neck and clothing area")
    elif subject == "architecture":
        roof_y = 0.26
        if len(horizontal) > 8:
            roof_y = float(np.argmax(horizontal[: max(3, int(len(horizontal) * 0.4))]) / max(1, len(horizontal) - 1))
            roof_y = min(0.34, max(0.10, roof_y))
        add("roof", "anchor", _subbox((x1, y1, x2, y2), 0.02, 0.0, 0.98, max(0.24, roof_y + 0.16), width, height), -16, 0.90, ["contour", "secondary", "texture"], "Roofline, shikhara, or top silhouette")
        add("central_structure", "anchor", _subbox((x1, y1, x2, y2), 0.14, 0.18, 0.86, 0.82, width, height), -10, 0.95, ["contour", "secondary"], "Main front-facing structural mass")
        add("entrance", "focal", _subbox((x1, y1, x2, y2), 0.34, 0.50, 0.66, 0.92, width, height), -12, 0.84, ["key", "secondary", "accent"], "Doorway or main focal opening")
        add("left_pillars", "support", _subbox((x1, y1, x2, y2), 0.08, 0.28, 0.30, 0.90, width, height), -4, 0.75, ["secondary", "texture", "shading"], "Left pillars and wall segments")
        add("right_pillars", "support", _subbox((x1, y1, x2, y2), 0.70, 0.28, 0.92, 0.90, width, height), -4, 0.75, ["secondary", "texture", "shading"], "Right pillars and wall segments")
        add("carvings", "detail", _subbox((x1, y1, x2, y2), 0.18, 0.24, 0.82, 0.76, width, height), 10, 0.70, ["texture", "secondary", "accent"], "Repeating carvings and ornament details")
        add("ground", "base", _subbox((x1, y1, x2, y2), 0.0, 0.82, 1.0, 1.0, width, height), 18, 0.78, ["secondary", "texture", "shading"], "Ground plane and courtyard")
    elif subject == "pet":
        add("head", "anchor", _subbox((x1, y1, x2, y2), 0.12, 0.04, 0.88, 0.58, width, height), -12, 0.90, ["contour", "secondary"], "Head mass")
        add("left_eye", "focal", _subbox((x1, y1, x2, y2), 0.22, 0.20, 0.43, 0.38, width, height), -18, 0.80, ["key", "accent"], "Left eye")
        add("right_eye", "focal", _subbox((x1, y1, x2, y2), 0.57, 0.20, 0.78, 0.38, width, height), -18, 0.80, ["key", "accent"], "Right eye")
        add("nose", "focal", _subbox((x1, y1, x2, y2), 0.40, 0.34, 0.60, 0.52, width, height), -12, 0.82, ["key", "accent", "secondary"], "Nose and muzzle center")
        add("ears", "support", _subbox((x1, y1, x2, y2), 0.08, 0.0, 0.92, 0.25, width, height), 5, 0.72, ["secondary", "texture"], "Ear region")
        add("body_fur", "texture", _subbox((x1, y1, x2, y2), 0.08, 0.48, 0.92, 1.0, width, height), 12, 0.74, ["secondary", "texture", "shading"], "Body and fur texture")
    elif subject == "landscape":
        add("sky_background", "background", _subbox((x1, y1, x2, y2), 0.0, 0.0, 1.0, 0.32, width, height), 22, 0.84, ["layout", "texture"], "Sky and light background")
        add("horizon_midground", "anchor", _subbox((x1, y1, x2, y2), 0.0, 0.28, 1.0, 0.62, width, height), -4, 0.88, ["contour", "secondary", "texture"], "Horizon and middle distance")
        add("foreground", "base", _subbox((x1, y1, x2, y2), 0.0, 0.58, 1.0, 1.0, width, height), 16, 0.86, ["secondary", "texture", "shading"], "Foreground depth area")
    elif subject == "logo":
        add("logo_core", "focal", _subbox((x1, y1, x2, y2), 0.18, 0.18, 0.82, 0.82, width, height), -14, 0.95, ["contour", "key", "accent"], "Primary logo shape")
        add("logo_outer", "support", _subbox((x1, y1, x2, y2), 0.0, 0.0, 1.0, 1.0, width, height), 8, 0.80, ["secondary", "accent"], "Outer logo marks or frame")
    else:  # product or generic object
        add("main_object", "anchor", _subbox((x1, y1, x2, y2), 0.08, 0.08, 0.92, 0.82, width, height), -10, 0.93, ["contour", "secondary", "key"], "Primary object silhouette")
        add("detail_core", "detail", _subbox((x1, y1, x2, y2), 0.22, 0.22, 0.78, 0.68, width, height), -2, 0.78, ["key", "secondary", "accent"], "Primary detail cluster")
        add("shadow_base", "base", _subbox((x1, y1, x2, y2), 0.0, 0.72, 1.0, 1.0, width, height), 18, 0.72, ["shading", "texture"], "Base shadow or resting plane")
        add("outer_details", "support", _subbox((x1, y1, x2, y2), 0.0, 0.0, 1.0, 1.0, width, height), 6, 0.60, ["secondary", "texture"], "Secondary object details")

    return regions


def build_layer_plan(subject: str, regions: list[SemanticRegion]) -> list[dict[str, Any]]:
    by_layer: dict[str, list[SemanticRegion]] = {
        "layout": [], "contour": [], "key": [], "secondary": [], "texture": [], "shading": [], "accent": []
    }
    for region in regions:
        for layer in region.preferred_layers:
            by_layer.setdefault(layer, []).append(region)

    pass_text = {
        "layout": "Very light guide lines to establish balance and proportions.",
        "contour": "Large confident outlines and structural boundaries.",
        "key": "Focal details that define likeness or subject identity.",
        "secondary": "Supporting inner contours and structural details.",
        "texture": "Repeated small marks for surface texture and ornamentation.",
        "shading": "Soft hatching and tonal build-up to add volume.",
        "accent": "Final dark accents, strongest edges, and finishing touches.",
    }
    rows: list[dict[str, Any]] = []
    for layer in ["layout", "contour", "key", "secondary", "texture", "shading", "accent"]:
        names = [r.name for r in sorted(by_layer.get(layer, []), key=lambda r: r.priority)]
        rows.append({
            "id": layer,
            "subject": subject,
            "focus_regions": names,
            "description": pass_text[layer],
        })
    return rows


def point_in_bbox(x: float, y: float, bbox: tuple[float, float, float, float]) -> bool:
    x1, y1, x2, y2 = bbox
    return x1 <= x <= x2 and y1 <= y <= y2


def overlap_ratio(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area = max(1.0, (ax2 - ax1) * (ay2 - ay1))
    return inter / area


def select_region_for_stroke(stroke_bbox: tuple[float, float, float, float], stroke_center: tuple[float, float], semantic_regions: list[SemanticRegion]) -> SemanticRegion | None:
    if not semantic_regions:
        return None
    cx, cy = stroke_center
    best_region = None
    best_score = -1e9
    max_area = max((max(1.0, (r.bbox[2] - r.bbox[0]) * (r.bbox[3] - r.bbox[1])) for r in semantic_regions), default=1.0)
    for region in semantic_regions:
        region_area = max(1.0, (region.bbox[2] - region.bbox[0]) * (region.bbox[3] - region.bbox[1]))
        specialization = 1.0 - (region_area / max_area)
        score = overlap_ratio(stroke_bbox, region.bbox) * 2.0
        if point_in_bbox(cx, cy, region.bbox):
            score += 1.35
        score += specialization * 0.8
        if region.role == "focal":
            score += 0.35
        score += region.confidence * 0.35
        score += (-region.priority) * 0.015
        if score > best_score:
            best_score = score
            best_region = region
    return best_region


def decide_semantic_layer(current_layer: str, region: SemanticRegion | None, length: float, darkness: float, effect: str) -> str:
    if effect in {"smudge", "erase"}:
        return "shading" if effect == "smudge" else "accent"
    if current_layer == "layout" or region is None:
        return current_layer
    if "accent" in region.preferred_layers and darkness > 0.55 and length < 120:
        return "accent"
    if region.role == "focal":
        if current_layer in {"contour", "secondary"}:
            return "key"
        if current_layer == "texture":
            return "secondary"
    if region.role in {"texture", "detail"}:
        if current_layer == "contour":
            return "secondary"
        if darkness > 0.2:
            return "texture"
    if region.role in {"base", "background"} and current_layer == "contour":
        return "secondary"
    if region.role == "mass" and current_layer == "key":
        return "secondary"
    if current_layer == "shading" and region.role in {"focal", "anchor"} and darkness < 0.17:
        return "texture"
    return current_layer
