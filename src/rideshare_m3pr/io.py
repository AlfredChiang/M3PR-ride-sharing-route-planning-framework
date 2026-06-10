"""CSV input helpers for real-data reproduction."""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from .matrix import GridMatrix
from .models import Order, Vehicle


def load_orders_csv(path: str | Path) -> List[Order]:
    df = pd.read_csv(path)
    required = {"order_id", "origin", "destination", "release_time"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Orders CSV is missing required columns: {sorted(missing)}")
    orders: List[Order] = []
    for row in df.to_dict("records"):
        orders.append(
            Order(
                order_id=int(row["order_id"]),
                origin=int(row["origin"]),
                destination=int(row["destination"]),
                release_time=float(row["release_time"]),
                demand=int(row.get("demand", 1)),
                max_pickup_delay=float(row.get("max_pickup_delay", 500.0)),
                detour_ratio=float(row.get("detour_ratio", 0.8)),
            )
        )
    return orders


def load_vehicles_csv(path: str | Path, default_capacity: int = 4) -> List[Vehicle]:
    df = pd.read_csv(path)
    required = {"vehicle_id", "current_node"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Vehicles CSV is missing required columns: {sorted(missing)}")
    vehicles: List[Vehicle] = []
    for row in df.to_dict("records"):
        vehicles.append(
            Vehicle(
                vehicle_id=int(row["vehicle_id"]),
                current_node=int(row["current_node"]),
                capacity=int(row.get("capacity", default_capacity)),
                current_time=float(row.get("current_time", 0.0)),
            )
        )
    return vehicles


def load_matrix_npz(path: str | Path) -> GridMatrix:
    data = np.load(path)
    if "distance" not in data or "time" not in data:
        raise ValueError("Matrix npz must contain arrays named 'distance' and 'time'")
    return GridMatrix(distance=data["distance"], time=data["time"])


def load_gdp_taxi_file(path: str | Path) -> tuple[List[Vehicle], dict]:
    """Load the taxi parameter file used by the uploaded GreedyDP code.

    Expected format, matching ``taxi.txt`` in the reference repository::

        m capacity gridL alpha
        start_node_0 capacity_0
        ...
        start_node_{m-1} capacity_{m-1}
        ddl pr

    Returns ``(vehicles, params)`` where ``params`` contains ``m``, ``capacity``,
    ``gridL``, ``alpha``, ``ddl`` and ``pr``.  The function is useful for
    comparing this reproduction with GreedyDP-style datasets after a compatible
    matrix has been prepared.
    """
    tokens = Path(path).read_text().split()
    if len(tokens) < 4:
        raise ValueError("GDP taxi file is too short")
    idx = 0
    m = int(tokens[idx]); idx += 1
    capacity = int(tokens[idx]); idx += 1
    grid_l = float(tokens[idx]); idx += 1
    alpha = float(tokens[idx]); idx += 1
    vehicles: List[Vehicle] = []
    for vehicle_id in range(m):
        if idx + 1 >= len(tokens):
            raise ValueError("GDP taxi file ended before all vehicles were read")
        current_node = int(tokens[idx]); idx += 1
        cap = int(tokens[idx]); idx += 1
        vehicles.append(Vehicle(vehicle_id=vehicle_id, current_node=current_node, capacity=cap, current_time=0.0))
    if idx + 1 >= len(tokens):
        raise ValueError("GDP taxi file is missing ddl/pr parameters")
    ddl = float(tokens[idx]); idx += 1
    pr = float(tokens[idx]); idx += 1
    params = {"m": m, "capacity": capacity, "gridL": grid_l, "alpha": alpha, "ddl": ddl, "pr": pr}
    return vehicles, params


def load_gdp_order_file(
    path: str | Path,
    matrix: GridMatrix,
    default_ddl: float,
    detour_ratio: float = 0.0,
    start_order_id: int = 0,
) -> List[Order]:
    """Load the order file used by the uploaded GreedyDP code.

    Expected format, matching ``order.txt`` in the reference repository::

        n
        release_time origin destination demand
        ...

    The original GreedyDP code stores a single completion deadline
    ``ddl_abs = release_time + shortest_time(origin,destination) + default_ddl``.
    The M3PR paper model has separate pickup delay and detour-ratio constraints.
    Setting ``max_pickup_delay=default_ddl`` and ``detour_ratio=0`` yields the
    same dropoff deadline while adding a natural pickup deadline.
    """
    tokens = Path(path).read_text().split()
    if not tokens:
        raise ValueError("GDP order file is empty")
    idx = 0
    n = int(tokens[idx]); idx += 1
    orders: List[Order] = []
    for local_id in range(n):
        if idx + 3 >= len(tokens):
            raise ValueError(f"GDP order file ended early at order {local_id}")
        release_time = float(tokens[idx]); idx += 1
        origin = int(tokens[idx]); idx += 1
        destination = int(tokens[idx]); idx += 1
        demand = int(tokens[idx]); idx += 1
        # Trigger matrix validation early; the original code skips disconnected
        # requests by checking whether R[pos].len is finite.
        if not np.isfinite(matrix.travel_time(origin, destination)):
            continue
        orders.append(
            Order(
                order_id=start_order_id + local_id,
                origin=origin,
                destination=destination,
                release_time=release_time,
                demand=demand,
                max_pickup_delay=default_ddl,
                detour_ratio=detour_ratio,
            )
        )
    return orders
