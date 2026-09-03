"""Deterministic 3D force-directed layout (numpy only)."""

from __future__ import annotations

import hashlib
import math
from typing import Any

from grapher.registry import CANONICAL_STAGE_ORDER

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore


def _require_numpy() -> None:
    if np is None:
        raise ImportError(
            "dashboard requires numpy; install with: pip install 'grapher[dash]'"
        )


def _stable_unit_vector(node_id: str) -> tuple[float, float, float]:
    digest = hashlib.sha256(node_id.encode("utf-8")).digest()
    # map 12 bytes → two angles
    u = int.from_bytes(digest[0:4], "big") / 2**32
    v = int.from_bytes(digest[4:8], "big") / 2**32
    theta = 2 * math.pi * u
    phi = math.acos(2 * v - 1)
    x = math.sin(phi) * math.cos(theta)
    y = math.sin(phi) * math.sin(theta)
    z = math.cos(phi)
    return x, y, z


def compute_layout(
    graph: dict[str, Any],
    *,
    steps: int = 80,
    seed_radius: float = 4.0,
    view_mode: str = "knowledge",
) -> dict[str, tuple[float, float, float]]:
    """Return {node_id: (x, y, z)} with a short force simulation."""
    _require_numpy()
    assert np is not None

    nodes = list(graph.get("nodes") or {})
    n = len(nodes)
    if n == 0:
        return {}
    if n == 1:
        return {nodes[0]: (0.0, 0.0, 0.0)}

    index = {nid: i for i, nid in enumerate(nodes)}
    if view_mode in ("lifecycle", "roadmap"):
        positions = {}
        for i, nid in enumerate(nodes):
            node = (graph.get("nodes") or {})[nid]
            raw = node.get("stage")
            stages = raw if isinstance(raw, list) else ([raw] if raw else [])
            stage = stages[0] if stages else None
            x = float(CANONICAL_STAGE_ORDER.index(stage) * 2) if stage in CANONICAL_STAGE_ORDER else -2.0
            _, y, z = _stable_unit_vector(nid)
            positions[nid] = (x, y * 4.0, z * 4.0)
        return positions
    if view_mode == "provenance":
        generations = sorted({(node.get("scope") or {}).get("generation_id")
                              for node in (graph.get("nodes") or {}).values()
                              if (node.get("scope") or {}).get("generation_id")})
        generation_index = {generation: i for i, generation in enumerate(generations)}
        positions = {}
        for nid in nodes:
            generation = ((graph.get("nodes") or {})[nid].get("scope") or {}).get("generation_id")
            x = float(generation_index.get(generation, -1) * 2)
            _, y, z = _stable_unit_vector(nid)
            positions[nid] = (x, y * 4.0, z * 4.0)
        return positions
    pos = np.zeros((n, 3), dtype=float)
    for i, nid in enumerate(nodes):
        x, y, z = _stable_unit_vector(nid)
        pos[i] = (x * seed_radius, y * seed_radius, z * seed_radius)

    edges: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for e in graph.get("edges") or []:
        a, b = e.get("from"), e.get("to")
        if a not in index or b not in index or a == b:
            continue
        i, j = index[a], index[b]
        key = (i, j) if i < j else (j, i)
        if key in seen:
            continue
        seen.add(key)
        edges.append(key)

    # Force params tuned for small/medium agent graphs
    repulsion = 2.5
    spring = 0.08
    spring_length = 1.8
    centering = 0.02
    damping = 0.85
    vel = np.zeros_like(pos)

    for _ in range(steps):
        force = np.zeros_like(pos)

        # pairwise repulsion (O(n^2) — fine for hundreds of nodes)
        for i in range(n):
            delta = pos[i] - pos
            dist2 = np.sum(delta * delta, axis=1) + 1e-4
            dist = np.sqrt(dist2)
            # skip self
            mask = np.ones(n, dtype=bool)
            mask[i] = False
            inv = repulsion / dist2
            force[i] += np.sum((delta * inv[:, None])[mask], axis=0)

        # spring attraction along edges
        for i, j in edges:
            delta = pos[j] - pos[i]
            dist = float(np.linalg.norm(delta)) + 1e-6
            mag = spring * (dist - spring_length)
            push = (delta / dist) * mag
            force[i] += push
            force[j] -= push

        # weak centering
        force -= pos * centering

        vel = damping * vel + force * 0.05
        # cap velocity
        speeds = np.linalg.norm(vel, axis=1, keepdims=True) + 1e-9
        vel = np.where(speeds > 1.5, vel * (1.5 / speeds), vel)
        pos = pos + vel

    # normalize scale
    center = pos.mean(axis=0)
    pos = pos - center
    scale = float(np.max(np.linalg.norm(pos, axis=1))) or 1.0
    pos = pos / scale * 5.0

    return {nid: (float(pos[i, 0]), float(pos[i, 1]), float(pos[i, 2])) for i, nid in enumerate(nodes)}
