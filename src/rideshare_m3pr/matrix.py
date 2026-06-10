"""Spatiotemporal grid matrix utilities.

The paper precomputes shortest-path distance/time between grid anchors. This
module provides an in-memory matrix version and a rectangular-grid helper for
synthetic tests.  ``coords`` is optional metadata used by the indexed pruning
module; algorithms only require ``distance`` and ``time``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class GridMatrix:
    distance: np.ndarray
    time: np.ndarray
    coords: Optional[np.ndarray] = None  # shape: (n_nodes, 2), arbitrary planar units

    def __post_init__(self) -> None:
        if self.distance.shape != self.time.shape:
            raise ValueError("distance and time matrices must have the same shape")
        if self.distance.shape[0] != self.distance.shape[1]:
            raise ValueError("matrices must be square")
        if self.coords is not None:
            if self.coords.shape != (self.distance.shape[0], 2):
                raise ValueError("coords must have shape (n_nodes, 2)")

    @property
    def n_nodes(self) -> int:
        return int(self.distance.shape[0])

    def dist(self, a: int, b: int | None) -> float:
        if b is None:
            return 0.0
        return float(self.distance[a, b])

    def travel_time(self, a: int, b: int | None) -> float:
        if b is None:
            return 0.0
        return float(self.time[a, b])

    @classmethod
    def rectangular_grid(cls, width: int, height: int, time_per_edge: float = 60.0) -> "GridMatrix":
        """Build all-pairs Manhattan shortest-path matrices on a rectangular grid."""
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")
        n = width * height
        dist = np.zeros((n, n), dtype=float)
        coords = np.zeros((n, 2), dtype=float)
        for u in range(n):
            ux, uy = u % width, u // width
            coords[u] = [ux, uy]
            for v in range(n):
                vx, vy = v % width, v // width
                dist[u, v] = abs(ux - vx) + abs(uy - vy)
        time = dist * time_per_edge
        return cls(distance=dist, time=time, coords=coords)

    def node_xy(self, node: int, width: int | None = None) -> Tuple[float, float]:
        if self.coords is not None:
            x, y = self.coords[node]
            return float(x), float(y)
        if width is None:
            raise ValueError("width is required when coords metadata is not available")
        return float(node % width), float(node // width)
