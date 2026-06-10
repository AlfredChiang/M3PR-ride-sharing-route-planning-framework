"""Synthetic data generator for quick reproduction sanity checks."""
from __future__ import annotations

from typing import List, Tuple

import numpy as np

from .matrix import GridMatrix
from .models import Order, Vehicle


def make_synthetic_problem(
    width: int = 12,
    height: int = 12,
    n_vehicles: int = 50,
    n_orders: int = 500,
    capacity: int = 4,
    horizon: float = 3600.0,
    pickup_delay: float = 600.0,
    detour_ratio: float = 0.8,
    time_per_edge: float = 60.0,
    seed: int = 7,
) -> Tuple[GridMatrix, List[Vehicle], List[Order]]:
    rng = np.random.default_rng(seed)
    matrix = GridMatrix.rectangular_grid(width, height, time_per_edge=time_per_edge)
    n_nodes = matrix.n_nodes

    vehicles = [
        Vehicle(vehicle_id=i, current_node=int(rng.integers(0, n_nodes)), capacity=capacity, current_time=0.0)
        for i in range(n_vehicles)
    ]

    orders: List[Order] = []
    release_times = np.sort(rng.uniform(0, horizon, size=n_orders))
    for q, t in enumerate(release_times):
        origin = int(rng.integers(0, n_nodes))
        destination = int(rng.integers(0, n_nodes - 1))
        if destination >= origin:
            destination += 1
        orders.append(
            Order(
                order_id=q,
                origin=origin,
                destination=destination,
                release_time=float(t),
                demand=1,
                max_pickup_delay=pickup_delay,
                detour_ratio=detour_ratio,
            )
        )
    return matrix, vehicles, orders
