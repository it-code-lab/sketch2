from __future__ import annotations

import math
import random
import wave
from pathlib import Path


def generate_pencil_audio(output_path: Path, duration_seconds: float, seed: int = 12345, sample_rate: int = 44100) -> Path:
    """Create a subtle scratch-like mono WAV track using only the standard library."""
    rng = random.Random(seed)
    total_samples = max(1, int(duration_seconds * sample_rate))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        burst_phase = 0.0
        burst_freq = rng.uniform(90, 180)
        next_burst = 0
        envelope = 0.0
        for i in range(total_samples):
            if i >= next_burst:
                burst_freq = rng.uniform(80, 260)
                envelope = rng.uniform(0.18, 0.62)
                next_burst = i + int(rng.uniform(0.025, 0.18) * sample_rate)
            envelope *= 0.99965
            noise = rng.uniform(-1.0, 1.0)
            grit = math.sin(burst_phase) * rng.uniform(0.1, 0.8)
            burst_phase += (2 * math.pi * burst_freq) / sample_rate
            # Low amplitude to avoid annoying harsh output.
            val = (noise * 0.50 + grit * 0.50) * envelope * 1800
            packed = int(max(-32767, min(32767, val))).to_bytes(2, byteorder="little", signed=True)
            frames.extend(packed)
        wav.writeframes(bytes(frames))
    return output_path
