from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


class TraceResult:
    def __init__(self, mode: str, svg_path: str = "", warnings: list[str] | None = None):
        self.mode = mode
        self.svg_path = svg_path
        self.warnings = warnings or []

    def to_dict(self) -> dict[str, str | list[str]]:
        return {"mode": self.mode, "svg_path": self.svg_path, "warnings": self.warnings}


def tracer_status() -> dict[str, bool | str]:
    return {
        "potrace_found": shutil.which("potrace") is not None,
        "vtracer_found": shutil.which("vtracer") is not None,
        "note": "OpenCV tracing is always available. Potrace/VTracer are optional command-line tools.",
    }


def maybe_trace_to_svg(sketch: np.ndarray, mode: str, output_dir: Path, job_stem: str) -> TraceResult:
    """Optional vector tracing hook.

    The app still uses the OpenCV stroke extractor for animation. This hook exports an SVG when
    Potrace/VTracer is installed, so future batches can use true SVG paths and users can inspect
    the vector result today.
    """
    mode = (mode or "opencv").lower()
    if mode == "opencv":
        return TraceResult("opencv")

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"{job_stem}_trace_input.png"
    svg_path = output_dir / f"{job_stem}_trace.svg"
    Image.fromarray(sketch).save(png_path)

    if mode in {"auto", "potrace"} and shutil.which("potrace"):
        # Potrace prefers PBM/BMP-like binary input. Convert the grayscale sketch to PBM first.
        pbm_path = output_dir / f"{job_stem}_trace_input.pbm"
        Image.fromarray((sketch < 210).astype("uint8") * 255).convert("1").save(pbm_path)
        cmd = [shutil.which("potrace") or "potrace", str(pbm_path), "--svg", "-o", str(svg_path)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0 and svg_path.exists():
            return TraceResult("potrace", str(svg_path))
        return TraceResult("potrace", warnings=["Potrace was found but failed to create SVG.", proc.stderr[-600:]])

    if mode in {"auto", "vtracer"} and shutil.which("vtracer"):
        cmd = [shutil.which("vtracer") or "vtracer", "--input", str(png_path), "--output", str(svg_path)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0 and svg_path.exists():
            return TraceResult("vtracer", str(svg_path))
        return TraceResult("vtracer", warnings=["VTracer was found but failed to create SVG.", proc.stderr[-600:]])

    return TraceResult(mode, warnings=[f"{mode} tracing requested, but the matching command-line tool was not found. Falling back to OpenCV stroke extraction."])
