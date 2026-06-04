from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

SubjectType = Literal["auto", "portrait", "architecture", "pet", "product", "landscape", "logo"]
SketchStyle = Literal["pencil", "charcoal", "ink", "marker"]
Ratio = Literal["9:16", "1:1", "16:9"]
TraceMode = Literal["opencv", "potrace", "vtracer", "auto"]
StrokeExtractionMode = Literal["hybrid", "centerline", "contour"]
PlanningMode = Literal["rule", "art_director_json"]
HandMode = Literal["procedural", "uploaded", "none"]


@dataclass
class RenderSettings:
    input_type: Literal["photo", "sketch"] = "photo"
    subject_type: SubjectType = "auto"
    style_type: SketchStyle = "pencil"
    ratio: Ratio = "9:16"
    sketch_strength: int = 70
    stroke_density: int = 60
    human_randomness: int = 35
    duration_seconds: int = 18
    fps: int = 24
    max_strokes: int = 1800
    paper_texture: bool = True
    construction_pass: bool = True
    accent_pass: bool = True
    hand_overlay: bool = True
    pencil_audio: bool = True
    width: int = 720
    height: int = 1280
    seed: int = 12345

    # Batch 3 premium controls.
    trace_mode: TraceMode = "opencv"
    stroke_extraction_mode: StrokeExtractionMode = "hybrid"
    planning_mode: PlanningMode = "rule"
    art_director_json: str = ""
    camera_motion: bool = True
    smudge_pass: bool = True
    eraser_pass: bool = False
    title_card_text: str = ""
    watermark_text: str = ""

    # Real hand overlay support. The path is set server-side after upload.
    hand_mode: HandMode = "procedural"
    hand_asset_path: str = ""
    hand_scale: int = 32
    hand_opacity: int = 95
    hand_rotation: int = -18
    hand_tip_x: int = 18
    hand_tip_y: int = 78

    @classmethod
    def from_form(cls, form: dict[str, Any]) -> "RenderSettings":
        def b(name: str, default: bool) -> bool:
            value = form.get(name, default)
            if isinstance(value, bool):
                return value
            return str(value).lower() in {"1", "true", "yes", "on"}

        def i(name: str, default: int, lo: int, hi: int) -> int:
            try:
                value = int(form.get(name, default))
            except (TypeError, ValueError):
                value = default
            return max(lo, min(hi, value))

        def s(name: str, default: str = "") -> str:
            value = form.get(name, default)
            return "" if value is None else str(value)

        settings = cls(
            input_type=s("input_type", "photo"),
            subject_type=s("subject_type", "auto"),
            style_type=s("style_type", "pencil"),
            ratio=s("ratio", "9:16"),
            sketch_strength=i("sketch_strength", 70, 20, 100),
            stroke_density=i("stroke_density", 60, 10, 100),
            human_randomness=i("human_randomness", 35, 0, 100),
            duration_seconds=i("duration_seconds", 18, 5, 240),
            fps=i("fps", 24, 12, 60),
            max_strokes=i("max_strokes", 1800, 250, 12000),
            paper_texture=b("paper_texture", True),
            construction_pass=b("construction_pass", True),
            accent_pass=b("accent_pass", True),
            hand_overlay=b("hand_overlay", True),
            pencil_audio=b("pencil_audio", True),
            seed=i("seed", 12345, 1, 2_000_000_000),
            trace_mode=s("trace_mode", "opencv"),
            stroke_extraction_mode=s("stroke_extraction_mode", "hybrid"),
            planning_mode=s("planning_mode", "rule"),
            art_director_json=s("art_director_json", ""),
            camera_motion=b("camera_motion", True),
            smudge_pass=b("smudge_pass", True),
            eraser_pass=b("eraser_pass", False),
            title_card_text=s("title_card_text", "")[:140],
            watermark_text=s("watermark_text", "")[:80],
            hand_mode=s("hand_mode", "procedural"),
            hand_asset_path=s("hand_asset_path", ""),
            hand_scale=i("hand_scale", 32, 8, 120),
            hand_opacity=i("hand_opacity", 95, 5, 100),
            hand_rotation=i("hand_rotation", -18, -180, 180),
            hand_tip_x=i("hand_tip_x", 18, 0, 100),
            hand_tip_y=i("hand_tip_y", 78, 0, 100),
        )
        settings.width, settings.height = ratio_to_size(settings.ratio)
        return settings

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Avoid leaking absolute local paths into exported plans.
        if payload.get("hand_asset_path"):
            payload["hand_asset_path"] = Path(str(payload["hand_asset_path"])).name
        return payload


def ratio_to_size(ratio: str) -> tuple[int, int]:
    # Batch 3 defaults are optimized for local rendering speed. Increase these
    # values later for final 1080p/4K exports after the queue and renderer are stable.
    if ratio == "1:1":
        return 720, 720
    if ratio == "16:9":
        return 960, 540
    return 540, 960


@dataclass
class Stroke:
    id: str
    points: list[tuple[float, float]]
    layer: str
    region: str
    order_score: float
    darkness: float
    thickness: float
    speed: float
    opacity: float
    jitter: float
    bbox: tuple[float, float, float, float]
    length: float
    delay_ms: int = 0
    duration_ms: int = 100
    start_ms: int = 0
    end_ms: int = 100
    effect: str = "draw"  # draw, smudge, erase, title

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["points"] = [[round(x, 2), round(y, 2)] for x, y in self.points]
        payload["bbox"] = [round(v, 2) for v in self.bbox]
        payload["order_score"] = round(self.order_score, 3)
        payload["darkness"] = round(self.darkness, 3)
        payload["thickness"] = round(self.thickness, 3)
        payload["speed"] = round(self.speed, 3)
        payload["opacity"] = round(self.opacity, 3)
        payload["jitter"] = round(self.jitter, 3)
        payload["length"] = round(self.length, 2)
        return payload


@dataclass
class StrokePlan:
    subject_type: str
    settings: dict[str, Any]
    strokes: list[Stroke]
    pass_summary: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    art_director: dict[str, Any] = field(default_factory=dict)
    semantic_regions: list[dict[str, Any]] = field(default_factory=list)
    layer_plan: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, include_strokes: bool = True) -> dict[str, Any]:
        payload = {
            "subject_type": self.subject_type,
            "settings": self.settings,
            "stroke_count": len(self.strokes),
            "pass_summary": self.pass_summary,
            "warnings": self.warnings,
            "art_director": self.art_director,
            "semantic_regions": self.semantic_regions,
            "layer_plan": self.layer_plan,
        }
        if include_strokes:
            payload["strokes"] = [stroke.to_dict() for stroke in self.strokes]
        return payload
