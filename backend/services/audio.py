from __future__ import annotations

import math
import random
import wave
from pathlib import Path
from typing import Any


SAMPLE_RATE = 44100


def _clamp16(value: float) -> int:
    return max(-32767, min(32767, int(round(value))))


def _write_wav(output_path: Path, samples: list[int], sample_rate: int = SAMPLE_RATE) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            frames.extend(int(sample).to_bytes(2, byteorder="little", signed=True))
        wav.writeframes(bytes(frames))
    return output_path


def _mix_in(dest: list[float], src: list[float], start: int = 0, gain: float = 1.0) -> None:
    if gain <= 0:
        return
    max_len = min(len(dest) - start, len(src))
    for i in range(max_len):
        dest[start + i] += src[i] * gain


def _style_drawing_layer(duration_seconds: float, seed: int, style_type: str, sample_rate: int = SAMPLE_RATE) -> list[float]:
    rng = random.Random(seed)
    total_samples = max(1, int(duration_seconds * sample_rate))
    out = [0.0] * total_samples
    burst_phase = 0.0
    next_burst = 0
    envelope = 0.0
    style = (style_type or "pencil").lower()
    for i in range(total_samples):
        if i >= next_burst:
            if style == "charcoal":
                burst_freq = rng.uniform(35, 120)
                envelope = rng.uniform(0.22, 0.72)
                next_burst = i + int(rng.uniform(0.040, 0.22) * sample_rate)
            elif style == "ink":
                burst_freq = rng.uniform(160, 420)
                envelope = rng.uniform(0.10, 0.34)
                next_burst = i + int(rng.uniform(0.030, 0.16) * sample_rate)
            elif style == "marker":
                burst_freq = rng.uniform(90, 240)
                envelope = rng.uniform(0.14, 0.42)
                next_burst = i + int(rng.uniform(0.050, 0.24) * sample_rate)
            else:
                burst_freq = rng.uniform(80, 260)
                envelope = rng.uniform(0.18, 0.62)
                next_burst = i + int(rng.uniform(0.025, 0.18) * sample_rate)
        envelope *= 0.99958 if style == "charcoal" else 0.99968
        noise = rng.uniform(-1.0, 1.0)
        grit = math.sin(burst_phase)
        burst_phase += (2 * math.pi * burst_freq) / sample_rate
        if style == "charcoal":
            val = (noise * 0.78 + grit * 0.22) * envelope * 2100
        elif style == "ink":
            tick = 0.25 if math.sin(i * 0.09) > 0.92 else 0.0
            val = (noise * 0.18 + grit * 0.82 + tick) * envelope * 1250
        elif style == "marker":
            squeak = math.sin(i * 0.014) * 0.18 + math.sin(i * 0.004) * 0.10
            val = (noise * 0.30 + grit * 0.45 + squeak) * envelope * 1500
        else:  # pencil
            val = (noise * 0.50 + grit * 0.50) * envelope * 1800
        out[i] = val
    return out


def _ambient_layer(duration_seconds: float, seed: int, ambient_track: str, sample_rate: int = SAMPLE_RATE) -> list[float]:
    ambient = (ambient_track or "none").lower()
    total_samples = max(1, int(duration_seconds * sample_rate))
    if ambient in {"", "none", "off"}:
        return [0.0] * total_samples
    rng = random.Random(seed + 111)
    out = [0.0] * total_samples
    phase1 = phase2 = phase3 = 0.0
    f1 = rng.uniform(40, 80)
    f2 = rng.uniform(90, 180)
    f3 = rng.uniform(220, 420)
    rustle_until = 0
    for i in range(total_samples):
        base_noise = rng.uniform(-1.0, 1.0)
        if ambient == "studio_room":
            val = math.sin(phase1) * 120 + math.sin(phase2) * 60 + base_noise * 55
        elif ambient == "paper_rustle":
            if i >= rustle_until and rng.random() < 0.00035:
                rustle_until = i + int(rng.uniform(0.03, 0.14) * sample_rate)
            rustle = 1.0 if i < rustle_until else 0.0
            val = (base_noise * (80 + 260 * rustle)) + math.sin(phase1) * 20
        elif ambient == "street_busker":
            traffic = math.sin(phase1) * 140 + math.sin(phase2) * 65 + math.sin(phase3) * 35
            chatter = base_noise * 90 + math.sin(i * 0.0008) * 45
            val = traffic + chatter
        else:
            val = base_noise * 60 + math.sin(phase1) * 40
        out[i] = val
        phase1 += (2 * math.pi * f1) / sample_rate
        phase2 += (2 * math.pi * f2) / sample_rate
        phase3 += (2 * math.pi * f3) / sample_rate
    return out


def _transition_sfx_layer(duration_seconds: float, seed: int, events: list[dict[str, Any]], sample_rate: int = SAMPLE_RATE) -> list[float]:
    total_samples = max(1, int(duration_seconds * sample_rate))
    out = [0.0] * total_samples
    rng = random.Random(seed + 222)
    for idx, event in enumerate(events):
        at = float(event.get("time", 0.0))
        transition = str(event.get("transition") or "fade").lower()
        start = max(0, int((at - 0.10) * sample_rate))
        length = int((0.18 if transition == "cut" else 0.55 if transition in {"fade", "zoomfade"} else 0.42) * sample_rate)
        base_freq = 160 if transition == "dipblack" else 260 if transition.startswith("wipe") else 360 if transition == "cut" else 220
        for n in range(length):
            pos = start + n
            if pos >= total_samples:
                break
            t = n / sample_rate
            env = math.exp(-5.5 * t)
            noise = rng.uniform(-1.0, 1.0)
            if transition == "cut":
                val = (math.sin(2 * math.pi * (base_freq + 120) * t) * 0.55 + noise * 0.45) * env * 1400
            elif transition == "dipblack":
                val = (math.sin(2 * math.pi * base_freq * t) * 0.85 + noise * 0.15) * env * 1700
            elif transition.startswith("wipe"):
                val = (math.sin(2 * math.pi * (base_freq + t * 320) * t) * 0.35 + noise * 0.65) * env * 1350
            else:  # fade / zoomfade
                val = (math.sin(2 * math.pi * (base_freq + t * 440) * t) * 0.40 + noise * 0.60) * env * (1550 if transition == "zoomfade" else 1200)
            out[pos] += val
    return out


def build_layered_audio_samples(
    duration_seconds: float,
    seed: int = 12345,
    style_type: str = "pencil",
    ambient_track: str = "none",
    ambient_level: int = 18,
    drawing_level: int = 70,
    transition_sfx: bool = False,
    transition_sfx_level: int = 30,
    transition_events: list[dict[str, Any]] | None = None,
    scene_mix: list[dict[str, Any]] | None = None,
    sample_rate: int = SAMPLE_RATE,
) -> list[int]:
    total_samples = max(1, int(duration_seconds * sample_rate))
    mix = [0.0] * total_samples
    if scene_mix:
        for idx, scene in enumerate(scene_mix):
            start_s = max(0.0, float(scene.get("start_time", 0.0)))
            end_s = min(duration_seconds, float(scene.get("end_time", duration_seconds)))
            if end_s <= start_s:
                continue
            seg_dur = end_s - start_s
            seg_style = str(scene.get("style_type") or style_type)
            seg_ambient = str(scene.get("ambient_track") or ambient_track)
            seg_ambient_level = int(scene.get("ambient_level", ambient_level))
            seg_drawing_level = int(scene.get("drawing_level", drawing_level))
            drawing = _style_drawing_layer(seg_dur, seed + idx * 101, seg_style, sample_rate)
            ambient = _ambient_layer(seg_dur, seed + idx * 101, seg_ambient, sample_rate)
            _mix_in(mix, drawing, int(start_s * sample_rate), max(0.0, min(100.0, seg_drawing_level)) / 100.0)
            _mix_in(mix, ambient, int(start_s * sample_rate), max(0.0, min(100.0, seg_ambient_level)) / 400.0)
    else:
        drawing = _style_drawing_layer(duration_seconds, seed, style_type, sample_rate)
        ambient = _ambient_layer(duration_seconds, seed, ambient_track, sample_rate)
        _mix_in(mix, drawing, 0, max(0.0, min(100.0, drawing_level)) / 100.0)
        _mix_in(mix, ambient, 0, max(0.0, min(100.0, ambient_level)) / 400.0)
    if transition_sfx and transition_events:
        sfx = _transition_sfx_layer(duration_seconds, seed, transition_events, sample_rate)
        _mix_in(mix, sfx, 0, max(0.0, min(100.0, transition_sfx_level)) / 100.0)
    return [_clamp16(v) for v in mix]


def generate_layered_audio(
    output_path: Path,
    duration_seconds: float,
    seed: int = 12345,
    style_type: str = "pencil",
    ambient_track: str = "none",
    ambient_level: int = 18,
    drawing_level: int = 70,
    transition_sfx: bool = False,
    transition_sfx_level: int = 30,
    transition_events: list[dict[str, Any]] | None = None,
    scene_mix: list[dict[str, Any]] | None = None,
    sample_rate: int = SAMPLE_RATE,
) -> Path:
    samples = build_layered_audio_samples(
        duration_seconds=duration_seconds,
        seed=seed,
        style_type=style_type,
        ambient_track=ambient_track,
        ambient_level=ambient_level,
        drawing_level=drawing_level,
        transition_sfx=transition_sfx,
        transition_sfx_level=transition_sfx_level,
        transition_events=transition_events,
        scene_mix=scene_mix,
        sample_rate=sample_rate,
    )
    return _write_wav(output_path, samples, sample_rate=sample_rate)


def generate_pencil_audio(output_path: Path, duration_seconds: float, seed: int = 12345, sample_rate: int = SAMPLE_RATE) -> Path:
    """Backward-compatible wrapper for older batches."""
    return generate_layered_audio(output_path, duration_seconds, seed=seed, style_type="pencil", ambient_track="none", drawing_level=70, sample_rate=sample_rate)
