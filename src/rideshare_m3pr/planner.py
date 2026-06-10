"""Online planner for the transformed M3PR objective."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Dict, Iterable, List, Literal, Optional

from .grid_index import GridIndex, build_identity_grid_index
from .insertion import cubic_insert, linear_profit_bounded_insert, quadratic_dp_insert, route_distance
from .matrix import GridMatrix
from .models import Order, Vehicle
from .pruning import dual_side_vehicle_pruning, dual_side_vehicle_pruning_indexed

AlgorithmName = Literal["linear", "quadratic", "cubic"]


@dataclass
class PlannerConfig:
    alpha: float = 1.7
    beta: float = 6.5
    algorithm: AlgorithmName = "linear"
    use_pruning: bool = True
    max_candidates: int | None = None
    use_grid_index: bool = True


@dataclass
class PlanningStats:
    served_orders: int = 0
    rejected_orders: int = 0
    p_sub: float = 0.0
    unserved_loss: float = 0.0
    routing_cost: float = 0.0
    completed_distance: float = 0.0
    remaining_distance: float = 0.0
    insertion_times: List[float] = field(default_factory=list)
    candidate_counts: List[int] = field(default_factory=list)

    @property
    def total_orders(self) -> int:
        return self.served_orders + self.rejected_orders

    @property
    def response_rate(self) -> float:
        return self.served_orders / self.total_orders if self.total_orders else 0.0

    @property
    def avg_insertion_time_ms(self) -> float:
        if not self.insertion_times:
            return 0.0
        return 1000.0 * sum(self.insertion_times) / len(self.insertion_times)

    @property
    def avg_candidate_count(self) -> float:
        if not self.candidate_counts:
            return 0.0
        return sum(self.candidate_counts) / len(self.candidate_counts)


def advance_vehicle_to(vehicle: Vehicle, target_time: float, matrix: GridMatrix) -> None:
    """Advance a vehicle and accumulate completed distance/time.

    If the vehicle would be mid-edge at ``target_time``, this scaffold keeps the
    vehicle at the last visited anchor, matching the discrete anchor-based route
    abstraction used by the reproduction.  Completed legs are accumulated so the
    final transformed objective does not ignore already executed route cost.
    """
    if target_time < vehicle.current_time:
        return
    while vehicle.route:
        next_stop = vehicle.route[0]
        travel = matrix.travel_time(vehicle.current_node, next_stop.node)
        if vehicle.current_time + travel > target_time + 1e-9:
            break
        vehicle.completed_distance += matrix.dist(vehicle.current_node, next_stop.node)
        vehicle.completed_time += travel
        vehicle.current_time += travel
        vehicle.current_node = next_stop.node
        vehicle.route.pop(0)
        order = vehicle.assigned_orders[next_stop.order_id]
        if next_stop.kind == "pickup":
            vehicle.onboard[next_stop.order_id] = order.demand
        else:
            vehicle.onboard.pop(next_stop.order_id, None)
    vehicle.current_time = target_time


def total_vehicle_distance(vehicle: Vehicle, matrix: GridMatrix) -> float:
    """Executed distance plus remaining planned-route distance."""
    return vehicle.completed_distance + route_distance(vehicle, matrix)


class OnlinePlanner:
    def __init__(
        self,
        matrix: GridMatrix,
        vehicles: Iterable[Vehicle],
        config: PlannerConfig | None = None,
        grid_index: Optional[GridIndex] = None,
    ):
        self.matrix = matrix
        self.vehicles: List[Vehicle] = list(vehicles)
        self.config = config or PlannerConfig()
        self.unserved: List[Order] = []
        self.served: Dict[int, int] = {}  # order_id -> vehicle_id
        self.grid_index = grid_index
        if self.grid_index is None and self.config.use_pruning and self.config.use_grid_index:
            self.grid_index = build_identity_grid_index(self.matrix, self.vehicles)

    def _insert(self, vehicle: Vehicle, order: Order):
        if self.config.algorithm == "linear":
            return linear_profit_bounded_insert(vehicle, order, self.matrix, self.config.alpha, self.config.beta)
        if self.config.algorithm == "quadratic":
            return quadratic_dp_insert(vehicle, order, self.matrix, self.config.alpha, self.config.beta)
        if self.config.algorithm == "cubic":
            return cubic_insert(vehicle, order, self.matrix, self.config.alpha, self.config.beta, use_profit_bound=True)
        raise ValueError(f"Unknown algorithm: {self.config.algorithm}")

    def _candidates_for(self, order: Order) -> List[Vehicle]:
        if not self.config.use_pruning:
            return list(self.vehicles)
        if self.config.use_grid_index and self.grid_index is not None:
            return dual_side_vehicle_pruning_indexed(
                order, self.vehicles, self.matrix, self.grid_index, self.config.max_candidates
            )
        return dual_side_vehicle_pruning(order, self.vehicles, self.matrix, self.config.max_candidates)

    def run(self, orders: Iterable[Order]) -> PlanningStats:
        stats = PlanningStats()
        for order in sorted(orders, key=lambda x: (x.release_time, x.order_id)):
            for v in self.vehicles:
                advance_vehicle_to(v, order.release_time, self.matrix)

            candidates = self._candidates_for(order)
            stats.candidate_counts.append(len(candidates))

            best_vehicle = None
            best_result = None
            start = perf_counter()
            for vehicle in candidates:
                result = self._insert(vehicle, order)
                if not result.feasible:
                    continue
                # Deterministic vehicle-level tie-breaking.  Equal-distance
                # insertions can occur frequently on grids; stable tie-breaking
                # keeps linear/quadratic/cubic experiments comparable.
                if best_result is None or (result.delta_distance, vehicle.vehicle_id) < (
                    best_result.delta_distance,
                    best_vehicle.vehicle_id,  # type: ignore[union-attr]
                ):
                    best_result = result
                    best_vehicle = vehicle
            stats.insertion_times.append(perf_counter() - start)

            if best_vehicle is not None and best_result is not None:
                best_vehicle.route = best_result.route
                best_vehicle.assigned_orders[order.order_id] = order
                self.served[order.order_id] = best_vehicle.vehicle_id
                stats.served_orders += 1
            else:
                self.unserved.append(order)
                stats.rejected_orders += 1

        # Transformed objective P_sub = beta * unserved revenue loss + alpha *
        # total vehicle-payment cost.  v2 only counted remaining routes; v3
        # includes completed_distance accumulated by advance_vehicle_to().
        stats.unserved_loss = self.config.beta * sum(self.matrix.dist(o.origin, o.destination) for o in self.unserved)
        stats.completed_distance = sum(v.completed_distance for v in self.vehicles)
        stats.remaining_distance = sum(route_distance(v, self.matrix) for v in self.vehicles)
        stats.routing_cost = self.config.alpha * (stats.completed_distance + stats.remaining_distance)
        stats.p_sub = stats.unserved_loss + stats.routing_cost
        return stats
