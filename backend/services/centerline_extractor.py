from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import cv2
import numpy as np


@dataclass
class CenterlinePath:
    points: list[tuple[float, float]]
    length: float
    darkness: float
    bbox: tuple[int, int, int, int]


def make_centerline_paths(
    sketch: np.ndarray,
    darkness: np.ndarray,
    sketch_strength: int,
    max_paths: int = 1800,
    min_length: float = 10.0,
) -> list[CenterlinePath]:
    """Extract drawable centerline paths from a sketch image.

    This is intentionally separate from SVG/vector tracing. Potrace-style contours
    describe the outside of dark blobs. A human sketch stroke is closer to the
    centerline of those blobs, so we thin the line-art into a 1-pixel skeleton and
    then trace connected skeleton branches into polylines.
    """
    if sketch.ndim != 2:
        raise ValueError("make_centerline_paths expects a grayscale sketch array")

    threshold = int(238 - sketch_strength * 1.05)
    binary = (sketch < threshold).astype(np.uint8)
    binary = cleanup_binary(binary)
    skeleton = thin_binary(binary)
    skeleton = prune_short_spurs(skeleton, iterations=2)

    paths = trace_skeleton_paths(skeleton, darkness, min_length=min_length)
    paths.sort(key=lambda p: (p.darkness * 2 + min(1.0, p.length / 260)), reverse=True)
    return paths[:max_paths]


def cleanup_binary(binary: np.ndarray) -> np.ndarray:
    kernel = np.ones((2, 2), np.uint8)
    out = cv2.morphologyEx(binary * 255, cv2.MORPH_CLOSE, kernel, iterations=1)
    out = cv2.morphologyEx(out, cv2.MORPH_OPEN, kernel, iterations=1)
    return (out > 0).astype(np.uint8)


def thin_binary(binary: np.ndarray) -> np.ndarray:
    """Return a 1-pixel skeleton using OpenCV ximgproc when available, otherwise Zhang-Suen."""
    try:
        thinning = cv2.ximgproc.thinning  # type: ignore[attr-defined]
        return (thinning((binary > 0).astype(np.uint8) * 255) > 0).astype(np.uint8)
    except Exception:
        return zhang_suen_thinning(binary)


def zhang_suen_thinning(binary: np.ndarray, max_iterations: int = 120) -> np.ndarray:
    img = (binary > 0).astype(np.uint8).copy()
    img[0, :] = img[-1, :] = img[:, 0] = img[:, -1] = 0

    for _ in range(max_iterations):
        changed = False
        for step in (0, 1):
            p2 = np.roll(img, -1, axis=0)
            p3 = np.roll(np.roll(img, -1, axis=0), 1, axis=1)
            p4 = np.roll(img, 1, axis=1)
            p5 = np.roll(np.roll(img, 1, axis=0), 1, axis=1)
            p6 = np.roll(img, 1, axis=0)
            p7 = np.roll(np.roll(img, 1, axis=0), -1, axis=1)
            p8 = np.roll(img, -1, axis=1)
            p9 = np.roll(np.roll(img, -1, axis=0), -1, axis=1)
            neighbors = [p2, p3, p4, p5, p6, p7, p8, p9]
            b = sum(neighbors)
            a = sum((neighbors[i] == 0) & (neighbors[(i + 1) % 8] == 1) for i in range(8))
            if step == 0:
                m = (img == 1) & (b >= 2) & (b <= 6) & (a == 1) & ((p2 * p4 * p6) == 0) & ((p4 * p6 * p8) == 0)
            else:
                m = (img == 1) & (b >= 2) & (b <= 6) & (a == 1) & ((p2 * p4 * p8) == 0) & ((p2 * p6 * p8) == 0)
            m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = False
            if np.any(m):
                img[m] = 0
                changed = True
        if not changed:
            break
    return img.astype(np.uint8)


def prune_short_spurs(skeleton: np.ndarray, iterations: int = 1) -> np.ndarray:
    out = skeleton.copy().astype(np.uint8)
    for _ in range(iterations):
        deg = neighbor_count(out)
        endpoints = (out > 0) & (deg <= 1)
        # Remove isolated dots and single-pixel burrs. Longer meaningful endpoints survive.
        remove = endpoints & (neighbor_count(out * (deg > 0)) <= 1)
        out[remove] = 0
    return out


def neighbor_count(img: np.ndarray) -> np.ndarray:
    total = np.zeros_like(img, dtype=np.uint8)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            total += np.roll(np.roll(img, dy, axis=0), dx, axis=1)
    total[0, :] = total[-1, :] = total[:, 0] = total[:, -1] = 0
    return total


def trace_skeleton_paths(skeleton: np.ndarray, darkness: np.ndarray, min_length: float) -> list[CenterlinePath]:
    skel = (skeleton > 0).astype(np.uint8)
    h, w = skel.shape
    deg = neighbor_count(skel)
    nodes = set(map(tuple, np.argwhere((skel > 0) & ((deg != 2)))))  # (y, x)
    visited_edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    paths: list[list[tuple[int, int]]] = []

    def neighbors(y: int, x: int) -> list[tuple[int, int]]:
        vals: list[tuple[int, int]] = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and skel[ny, nx]:
                    vals.append((ny, nx))
        return vals

    def edge(a: tuple[int, int], b: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
        return (a, b) if a <= b else (b, a)

    def walk(start: tuple[int, int], nxt: tuple[int, int]) -> list[tuple[int, int]]:
        out = [start, nxt]
        visited_edges.add(edge(start, nxt))
        prev, cur = start, nxt
        safety = 0
        while safety < h * w:
            safety += 1
            if cur in nodes and cur != start:
                break
            options = [p for p in neighbors(*cur) if p != prev]
            unvisited = [p for p in options if edge(cur, p) not in visited_edges]
            if not unvisited:
                break
            # Continue as straight as possible so a human-like stroke does not zigzag around junction pixels.
            if len(unvisited) > 1:
                py, px = prev
                cy, cx = cur
                vx, vy = cx - px, cy - py
                def score(p: tuple[int, int]) -> float:
                    ny, nx = p
                    wx, wy = nx - cx, ny - cy
                    denom = max(1e-6, math.hypot(vx, vy) * math.hypot(wx, wy))
                    return (vx * wx + vy * wy) / denom
                nxt2 = max(unvisited, key=score)
            else:
                nxt2 = unvisited[0]
            visited_edges.add(edge(cur, nxt2))
            out.append(nxt2)
            prev, cur = cur, nxt2
        return out

    # Trace branches from endpoints and junctions first.
    for node in sorted(nodes):
        for nb in neighbors(*node):
            if edge(node, nb) not in visited_edges:
                path = walk(node, nb)
                if len(path) >= 2:
                    paths.append(path)

    # Trace closed loops that have no endpoint/junction.
    remaining = list(map(tuple, np.argwhere(skel > 0)))
    for pix in remaining:
        nbs = neighbors(*pix)
        for nb in nbs:
            if edge(pix, nb) in visited_edges:
                continue
            path = walk(pix, nb)
            if len(path) >= 2:
                paths.append(path)

    result: list[CenterlinePath] = []
    for raw in paths:
        pts_xy = [(float(x), float(y)) for y, x in raw]
        length = polyline_length(pts_xy)
        if length < min_length:
            continue
        simplified = simplify_polyline(pts_xy, epsilon=max(0.65, min(3.0, length * 0.008)))
        if len(simplified) < 2:
            continue
        length = polyline_length(simplified)
        if length < min_length:
            continue
        avg = sample_darkness(darkness, simplified)
        bbox = bbox_int(simplified)
        result.append(CenterlinePath(simplified, length, avg, bbox))
    return result


def simplify_polyline(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    arr = np.array(points, dtype=np.float32).reshape((-1, 1, 2))
    approx = cv2.approxPolyDP(arr, epsilon, False)
    return [(float(p[0][0]), float(p[0][1])) for p in approx]


def sample_darkness(darkness: np.ndarray, points: Iterable[tuple[float, float]]) -> float:
    h, w = darkness.shape
    vals: list[float] = []
    for x, y in points:
        xi = max(0, min(w - 1, int(round(x))))
        yi = max(0, min(h - 1, int(round(y))))
        vals.append(float(darkness[yi, xi]))
    return float(np.mean(vals)) if vals else 0.15


def polyline_length(points: list[tuple[float, float]]) -> float:
    return float(sum(math.dist(a, b) for a, b in zip(points, points[1:])))


def bbox_int(points: list[tuple[float, float]]) -> tuple[int, int, int, int]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))
