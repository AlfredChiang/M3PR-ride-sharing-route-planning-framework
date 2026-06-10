"""Core data structures for the M3PR ride-sharing reproduction."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal

StopKind = Literal["pickup", "dropoff"]


@dataclass(frozen=True)
class Order:
    """Passenger order.

    node ids are grid-anchor ids. release_time and delays use the same time unit
    as GridMatrix.time.
    """

    order_id: int
    origin: int
    destination: int
    release_time: float
    demand: int = 1
    max_pickup_delay: float = 500.0
    detour_ratio: float = 0.8


@dataclass(frozen=True)
class Stop:
    """A pickup or dropoff point already planned in a vehicle route."""

    node: int
    order_id: int
    kind: StopKind


@dataclass
class Vehicle:
    """Vehicle state.

    route contains only remaining pickup/dropoff stops. current_node is the first
    position l_0 in the paper notation.
    """

    vehicle_id: int
    current_node: int
    capacity: int = 4
    current_time: float = 0.0
    route: List[Stop] = field(default_factory=list)
    assigned_orders: Dict[int, Order] = field(default_factory=dict)
    onboard: Dict[int, int] = field(default_factory=dict)
    completed_distance: float = 0.0
    completed_time: float = 0.0

    def clone_with_route(self, route: List[Stop]) -> "Vehicle":
        return Vehicle(
            vehicle_id=self.vehicle_id,
            current_node=self.current_node,
            capacity=self.capacity,
            current_time=self.current_time,
            route=list(route),
            assigned_orders=dict(self.assigned_orders),
            onboard=dict(self.onboard),
            completed_distance=self.completed_distance,
            completed_time=self.completed_time,
        )
