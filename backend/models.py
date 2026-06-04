from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

SubjectType = Literal["auto", "portrait", "architecture", "pet", "product", "landscape", "logo"]
SketchStyle = Literal["pencil", "charcoal", "ink", "marker"]
Ratio = Literal["9:16", "1:1", "16:9"]
RenderQuality = Literal["preview", "standard", "final", "ultra"]
TraceMode = Literal["opencv", "potrace", "vtracer", "auto"]
StrokeExtractionMode = Literal["hybrid", "centerline", "contour"]
PlanningMode = Literal["rule", "art_director_json"]
HandMode = Literal["procedural", "uploaded", "video", "none"]


@dataclass
class RenderSettings:
    input_type: Literal["photo", "sketch"] = "photo"
    subject_type: SubjectType = "auto"
    style_type: SketchStyle = "pencil"
    ratio: Ratio = "9:16"
    render_quality: RenderQuality = "standard"
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
    camera_move_preset: str = "static"
    camera_zoom_start: int = 100
    camera_zoom_end: int = 100
    camera_pan_start_x: int = 0
    camera_pan_start_y: int = 0
    camera_pan_end_x: int = 0
    camera_pan_end_y: int = 0
    smudge_pass: bool = True
    eraser_pass: bool = False
    title_card_text: str = ""
    watermark_text: str = ""

    # Real hand overlay support. The path is set server-side after upload.
    hand_mode: HandMode = "procedural"
    hand_preset: str = ""
    hand_side: str = "right"
    hand_asset_filename: str = ""
    hand_asset_path: str = ""
    hand_scale: int = 32
    hand_opacity: int = 95
    hand_rotation: int = -18
    hand_tip_x: int = 18
    hand_tip_y: int = 78
    hand_video_loop: bool = True
    hand_video_playback_rate: int = 100
    hand_video_frame_offset: int = 0
    hand_video_chroma_key: bool = False
    hand_lift_px: int = 14
    hand_shadow_strength: int = 70
    contact_correction_strength: int = 72
    contact_position_smoothing: int = 58
    reposition_arc_strength: int = 55

    # Batch 9 render-quality and advanced brush simulation controls.
    graphite_grain: int = 65
    charcoal_dust: int = 55
    ink_bleed: int = 28
    marker_overlap: int = 42
    stroke_taper: int = 58
    motion_blur_strength: int = 14

    # Batch 12 audio design controls.
    ambient_track: str = "none"
    ambient_level: int = 18
    drawing_audio_level: int = 70
    transition_sfx: bool = True
    transition_sfx_level: int = 30

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
            render_quality=s("render_quality", "standard"),
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
            camera_move_preset=s("camera_move_preset", "static"),
            camera_zoom_start=i("camera_zoom_start", 100, 50, 200),
            camera_zoom_end=i("camera_zoom_end", 100, 50, 200),
            camera_pan_start_x=i("camera_pan_start_x", 0, -100, 100),
            camera_pan_start_y=i("camera_pan_start_y", 0, -100, 100),
            camera_pan_end_x=i("camera_pan_end_x", 0, -100, 100),
            camera_pan_end_y=i("camera_pan_end_y", 0, -100, 100),
            smudge_pass=b("smudge_pass", True),
            eraser_pass=b("eraser_pass", False),
            title_card_text=s("title_card_text", "")[:140],
            watermark_text=s("watermark_text", "")[:80],
            hand_mode=s("hand_mode", "procedural"),
            hand_preset=s("hand_preset", ""),
            hand_side=s("hand_side", "right"),
            hand_asset_filename=s("hand_asset_filename", ""),
            hand_asset_path=s("hand_asset_path", ""),
            hand_scale=i("hand_scale", 32, 8, 120),
            hand_opacity=i("hand_opacity", 95, 5, 100),
            hand_rotation=i("hand_rotation", -18, -180, 180),
            hand_tip_x=i("hand_tip_x", 18, 0, 100),
            hand_tip_y=i("hand_tip_y", 78, 0, 100),
            hand_video_loop=b("hand_video_loop", True),
            hand_video_playback_rate=i("hand_video_playback_rate", 100, 25, 400),
            hand_video_frame_offset=i("hand_video_frame_offset", 0, -2000, 2000),
            hand_video_chroma_key=b("hand_video_chroma_key", False),
            hand_lift_px=i("hand_lift_px", 14, 0, 80),
            hand_shadow_strength=i("hand_shadow_strength", 70, 0, 100),
            contact_correction_strength=i("contact_correction_strength", 72, 0, 100),
            contact_position_smoothing=i("contact_position_smoothing", 58, 0, 100),
            reposition_arc_strength=i("reposition_arc_strength", 55, 0, 100),
            graphite_grain=i("graphite_grain", 65, 0, 100),
            charcoal_dust=i("charcoal_dust", 55, 0, 100),
            ink_bleed=i("ink_bleed", 28, 0, 100),
            marker_overlap=i("marker_overlap", 42, 0, 100),
            stroke_taper=i("stroke_taper", 58, 0, 100),
            motion_blur_strength=i("motion_blur_strength", 14, 0, 100),
            ambient_track=s("ambient_track", "none"),
            ambient_level=i("ambient_level", 18, 0, 100),
            drawing_audio_level=i("drawing_audio_level", 70, 0, 100),
            transition_sfx=b("transition_sfx", True),
            transition_sfx_level=i("transition_sfx_level", 30, 0, 100),
        )
        settings.width, settings.height = ratio_to_size(settings.ratio, settings.render_quality)
        return settings

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Avoid leaking absolute local paths into exported plans.
        if payload.get("hand_asset_path"):
            payload["hand_asset_path"] = Path(str(payload["hand_asset_path"])).name
        return payload


def ratio_to_size(ratio: str, render_quality: str = "standard") -> tuple[int, int]:
    quality_map = {
        "preview": {"9:16": (540, 960), "1:1": (720, 720), "16:9": (960, 540)},
        "standard": {"9:16": (720, 1280), "1:1": (900, 900), "16:9": (1280, 720)},
        "final": {"9:16": (1080, 1920), "1:1": (1440, 1440), "16:9": (1920, 1080)},
        "ultra": {"9:16": (1440, 2560), "1:1": (2048, 2048), "16:9": (2560, 1440)},
    }
    return quality_map.get(render_quality, quality_map["standard"]).get(ratio, quality_map["standard"]["9:16"])


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
