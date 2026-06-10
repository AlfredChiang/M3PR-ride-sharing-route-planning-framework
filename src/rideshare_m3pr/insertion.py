"""Order insertion operators for the M3PR reproduction.

The uploaded GreedyDP/pruneGreedyDP implementation encodes a vehicle route as a
sequence of request ids, maintains three arrays for every vehicle route, and then
uses those arrays to test an insertion in constant time:

``reach[k]``  arrival time at the k-th planned point;
``picked[k]`` number of passengers onboard after visiting that point;
``slack[k]``  minimum downstream deadline slack after that point.

This module re-implements the same dynamic-programming idea in a clean Python
form and adapts it to the paper's price-aware M3PR model.  In particular, the
linear operator below mirrors the GreedyDP ``Det`` array with the paper's
``zeta(l_j)`` / ``eta(l_j)`` states and additionally applies the M3PR profit
bound ``tau_q``.

Implemented operators
---------------------
- ``cubic_insert``: direct baseline; enumerate every pair, simulate full route.
- ``quadratic_dp_insert``: enumerate every pair, check most constraints in O(1).
- ``linear_profit_bounded_insert``: Algorithm-5-style profit-bounded linear scan.

Notation
--------
The paper writes a route schedule as ``S_i = <l_0, l_1, ..., l_n>``, where
``l_0`` is the current vehicle position.  An insertion pair ``(i, j)`` means:
insert the pickup after ``l_i`` and insert the dropoff after ``l_j``.  Thus
``0 <= i <= j <= n``.

Important unit note
-------------------
Route objective/profit uses *distance* increments, while service quality uses
*travel-time* increments.  The paper assumes a speed model that allows distance
and time to be used interchangeably in its theoretical exposition; this code
keeps the two matrices separate and uses time detours for deadline/slack checks.
For exact linear optimality, distance and time should be proportional, as in the
synthetic grid and in the paper's constant-speed abstraction.  If you use a
strongly time-dependent matrix, use ``quadratic_dp_insert`` as a safer checker.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import inf, isfinite
from typing import List, Optional, Tuple

import numpy as np

from .matrix import GridMatrix
from .models import Order, Stop, Vehicle

EPS = 1e-9


def _is_better_pair(delta: float, pair: Tuple[int, int], best_delta: float, best_pair: Optional[Tuple[int, int]]) -> bool:
    """Deterministic tie-breaking shared by all insertion operators.

    The cubic baseline scans pairs in lexicographic order.  The linear operator
    scans by delivery position, so equal-distance insertions can otherwise lead
    to different routes and diverging online simulations.  This helper makes all
    operators prefer the lexicographically smallest pair among equal objective
    values.
    """
    if delta < best_delta - EPS:
        return True
    if abs(delta - best_delta) <= EPS and (best_pair is None or pair < best_pair):
        return True
    return False


@dataclass
class InsertionResult:
    route: List[Stop]
    delta_distance: float
    pair: Optional[Tuple[int, int]]
    feasible: bool


@dataclass(frozen=True)
class RouteDPState:
    """Dynamic-programming states for a vehicle route.

    positions[k] is l_k in the paper.  The remaining arrays are indexed by the
    same k.  ``slack[k]`` is T(l_k), i.e. the minimum remaining time slack of all
    downstream stops after l_k.  ``load[k]`` is rho(l_k), the onboard passenger
    count after visiting l_k.  The current vehicle position is l_0.
    """

    positions: List[int]
    arrival: np.ndarray
    latest: np.ndarray
    slack: np.ndarray
    load: np.ndarray


# ---------------------------------------------------------------------------
# Basic route utilities
# ---------------------------------------------------------------------------


def route_positions(vehicle: Vehicle) -> List[int]:
    return [vehicle.current_node] + [s.node for s in vehicle.route]


def route_distance(vehicle: Vehicle, matrix: GridMatrix, route: Optional[List[Stop]] = None) -> float:
    stops = vehicle.route if route is None else route
    if not stops:
        return 0.0
    total = 0.0
    prev = vehicle.current_node
    for stop in stops:
        total += matrix.dist(prev, stop.node)
        prev = stop.node
    return total


def route_travel_time(vehicle: Vehicle, matrix: GridMatrix, route: Optional[List[Stop]] = None) -> float:
    stops = vehicle.route if route is None else route
    if not stops:
        return 0.0
    total = 0.0
    prev = vehicle.current_node
    for stop in stops:
        total += matrix.travel_time(prev, stop.node)
        prev = stop.node
    return total


def _detour_value(value_fn, left: int, inserted: int, right: int | None) -> float:
    """Generic det(l_i, x, l_{i+1}) for either distance or time."""
    if right is None:
        return float(value_fn(left, inserted))
    return float(value_fn(left, inserted) + value_fn(inserted, right) - value_fn(left, right))


def distance_detour(matrix: GridMatrix, left: int, inserted: int, right: int | None) -> float:
    return _detour_value(matrix.dist, left, inserted, right)


def time_detour(matrix: GridMatrix, left: int, inserted: int, right: int | None) -> float:
    return _detour_value(matrix.travel_time, left, inserted, right)


# Backward-compatible public name used by earlier versions of the scaffold.
def detour(matrix: GridMatrix, left: int, inserted: int, right: int | None) -> float:
    return distance_detour(matrix, left, inserted, right)


def _copy_and_insert(route: List[Stop], order: Order, i: int, j: int) -> List[Stop]:
    """Create a route by inserting pickup/dropoff at paper indices (i, j)."""
    new_route = list(route)
    pickup = Stop(node=order.origin, order_id=order.order_id, kind="pickup")
    dropoff = Stop(node=order.destination, order_id=order.order_id, kind="dropoff")
    # route excludes l_0.  Inserting after l_i means list index i.
    if i < j:
        new_route.insert(i, pickup)
        new_route.insert(j + 1, dropoff)
    else:
        new_route.insert(i, pickup)
        new_route.insert(i + 1, dropoff)
    return new_route


def _latest_time_for_stop(stop: Stop, order: Order, matrix: GridMatrix) -> float:
    if stop.kind == "pickup":
        return order.release_time + order.max_pickup_delay
    direct_time = matrix.travel_time(order.origin, order.destination)
    return order.release_time + order.max_pickup_delay + direct_time * (1.0 + order.detour_ratio)


def _route_state_arrays(vehicle: Vehicle, matrix: GridMatrix) -> RouteDPState:
    """Return positions, arrival times, latest-arrival deadlines, slack, load.

    This is the Python equivalent of the uploaded C++ ``updateDriverArr``:
    ``reach`` -> arrival, ``picked`` -> load, ``slack`` -> downstream slack.
    """
    positions = route_positions(vehicle)
    n = len(positions) - 1
    arrival = np.zeros(n + 1, dtype=float)
    latest = np.full(n + 1, inf, dtype=float)
    load = np.zeros(n + 1, dtype=int)

    arrival[0] = vehicle.current_time
    current_load = sum(vehicle.onboard.values())
    load[0] = current_load

    prev_node = vehicle.current_node
    for idx, stop in enumerate(vehicle.route, start=1):
        arrival[idx] = arrival[idx - 1] + matrix.travel_time(prev_node, stop.node)
        order = vehicle.assigned_orders[stop.order_id]
        latest[idx] = _latest_time_for_stop(stop, order, matrix)
        if stop.kind == "pickup":
            current_load += order.demand
        else:
            current_load -= order.demand
        load[idx] = current_load
        prev_node = stop.node

    slack = np.full(n + 1, inf, dtype=float)
    for k in range(n - 1, -1, -1):
        slack[k] = min(slack[k + 1], latest[k + 1] - arrival[k + 1])
    return RouteDPState(positions=positions, arrival=arrival, latest=latest, slack=slack, load=load)


def _delta_for_pair(positions: List[int], order: Order, i: int, j: int, matrix: GridMatrix) -> float:
    """Distance increment Delta_{l_i,l_j} in Eq. (13)/(25)."""
    return _delta_for_pair_with(matrix.dist, positions, order.origin, order.destination, i, j)


def _time_delta_for_pair(positions: List[int], order: Order, i: int, j: int, matrix: GridMatrix) -> float:
    """Travel-time increment corresponding to the same insertion pair."""
    return _delta_for_pair_with(matrix.travel_time, positions, order.origin, order.destination, i, j)


def _delta_for_pair_with(value_fn, positions: List[int], origin: int, destination: int, i: int, j: int) -> float:
    n = len(positions) - 1
    direct = value_fn(origin, destination)
    if i < j:
        right_i = positions[i + 1]
        right_j = positions[j + 1] if j < n else None
        return _detour_value(value_fn, positions[i], origin, right_i) + _detour_value(
            value_fn, positions[j], destination, right_j
        )
    if i == n:  # i=j=n: append pickup and dropoff at the tail.
        return value_fn(positions[i], origin) + direct
    # i=j<n: pickup and dropoff are consecutive between l_i and l_{i+1}.
    return value_fn(positions[i], origin) + direct + value_fn(destination, positions[i + 1]) - value_fn(
        positions[i], positions[i + 1]
    )


def _check_full_route_feasible(vehicle: Vehicle, order: Order, route: List[Stop], matrix: GridMatrix) -> bool:
    """Explicit route feasibility check used by the cubic baseline and tests."""
    all_orders = dict(vehicle.assigned_orders)
    all_orders[order.order_id] = order
    t = vehicle.current_time
    load = sum(vehicle.onboard.values())
    prev = vehicle.current_node
    picked = set(vehicle.onboard.keys())

    for stop in route:
        if stop.order_id not in all_orders:
            return False
        o = all_orders[stop.order_id]
        t += matrix.travel_time(prev, stop.node)
        if stop.kind == "pickup":
            if stop.order_id in picked:
                return False
            if t > o.release_time + o.max_pickup_delay + EPS:
                return False
            load += o.demand
            picked.add(stop.order_id)
            if load > vehicle.capacity:
                return False
        else:
            if stop.order_id not in picked:
                return False
            latest_drop = o.release_time + o.max_pickup_delay + matrix.travel_time(o.origin, o.destination) * (
                1.0 + o.detour_ratio
            )
            if t > latest_drop + EPS:
                return False
            load -= o.demand
            picked.remove(stop.order_id)
            if load < 0:
                return False
        prev = stop.node
    return True


# ---------------------------------------------------------------------------
# Algorithm 3: cubic baseline
# ---------------------------------------------------------------------------


def cubic_insert(
    vehicle: Vehicle,
    order: Order,
    matrix: GridMatrix,
    alpha: float = 1.7,
    beta: float = 6.5,
    use_profit_bound: bool = True,
) -> InsertionResult:
    """General insertion baseline.

    Enumerates all insertion pairs, generates a route, checks feasibility by a
    full simulation, and computes the increased route distance from scratch.
    """
    n = len(vehicle.route)
    old_distance = route_distance(vehicle, matrix)
    best_delta = inf
    best_pair = None
    best_route = list(vehicle.route)
    tau = beta * matrix.dist(order.origin, order.destination) / alpha if alpha > 0 else inf

    for i in range(n + 1):
        for j in range(i, n + 1):
            new_route = _copy_and_insert(vehicle.route, order, i, j)
            if not _check_full_route_feasible(vehicle, order, new_route, matrix):
                continue
            delta = route_distance(vehicle, matrix, new_route) - old_distance
            if use_profit_bound and delta > tau + EPS:
                continue
            pair = (i, j)
            if _is_better_pair(delta, pair, best_delta, best_pair):
                best_delta = delta
                best_pair = pair
                best_route = new_route

    return InsertionResult(best_route, best_delta, best_pair, isfinite(best_delta))


# ---------------------------------------------------------------------------
# Algorithm 4: DP-based quadratic insertion
# ---------------------------------------------------------------------------


def quadratic_dp_insert(
    vehicle: Vehicle,
    order: Order,
    matrix: GridMatrix,
    alpha: float = 1.7,
    beta: float = 6.5,
    use_profit_bound: bool = True,
) -> InsertionResult:
    """DP-based quadratic insertion.

    This follows Algorithm 4: all insertion pairs are still enumerated, but
    arrival/slack/load arrays allow feasibility checks and distance increments to
    be evaluated without rebuilding the route each time.
    """
    state = _route_state_arrays(vehicle, matrix)
    if state.slack[0] < -EPS:
        return InsertionResult(list(vehicle.route), inf, None, False)
    positions, arrival, slack, load = state.positions, state.arrival, state.slack, state.load
    n = len(positions) - 1
    best_delta = inf
    best_pair = None
    best_route = list(vehicle.route)
    direct_time = matrix.travel_time(order.origin, order.destination)
    direct_dist = matrix.dist(order.origin, order.destination)
    pickup_deadline = order.release_time + order.max_pickup_delay
    drop_deadline = pickup_deadline + direct_time * (1.0 + order.detour_ratio)
    tau = beta * direct_dist / alpha if alpha > 0 else inf

    for i in range(n + 1):
        pickup_arrival = arrival[i] + matrix.travel_time(positions[i], order.origin)
        if pickup_arrival > pickup_deadline + EPS:
            # The paper pseudocode uses ``break`` under its monotonic route
            # assumptions.  We use ``continue`` to remain robust when users plug
            # in arbitrary matrices or non-monotone synthetic routes.
            continue
        if load[i] > vehicle.capacity - order.demand:
            continue
        pickup_det_time = time_detour(matrix, positions[i], order.origin, positions[i + 1] if i < n else None)
        if pickup_det_time > slack[i] + EPS:
            continue
        for j in range(i, n + 1):
            if i < j:
                # The new order is onboard from positions i+1 through j.
                if np.any(load[i + 1 : j + 1] > vehicle.capacity - order.demand):
                    continue
            delta_dist = _delta_for_pair(positions, order, i, j, matrix)
            if use_profit_bound and delta_dist > tau + EPS:
                continue
            delta_time = _time_delta_for_pair(positions, order, i, j, matrix)
            if i == j:
                drop_arrival = pickup_arrival + direct_time
            else:
                drop_arrival = arrival[j] + pickup_det_time + matrix.travel_time(positions[j], order.destination)
            if drop_arrival > drop_deadline + EPS:
                continue
            if delta_time > slack[j] + EPS:
                continue
            pair = (i, j)
            if _is_better_pair(delta_dist, pair, best_delta, best_pair):
                best_delta = delta_dist
                best_pair = pair

    if best_pair is not None:
        best_route = _copy_and_insert(vehicle.route, order, best_pair[0], best_pair[1])
    return InsertionResult(best_route, best_delta, best_pair, isfinite(best_delta))


# ---------------------------------------------------------------------------
# Algorithm 5: profit-bounded DP-based linear insertion
# ---------------------------------------------------------------------------


def linear_profit_bounded_insert(
    vehicle: Vehicle,
    order: Order,
    matrix: GridMatrix,
    alpha: float = 1.7,
    beta: float = 6.5,
    verify: bool = True,
) -> InsertionResult:
    """Profit-bounded DP-based linear-time insertion.

    This is the main Algorithm-5 reproduction.  It keeps a GreedyDP-style best
    pickup-side state before each delivery position and evaluates every delivery
    position once.

    ``verify=True`` performs a final full-route check of the selected insertion.
    This preserves safety when users plug in matrices where distance and time are
    not perfectly proportional.  The verification is only done once for the final
    route, so the scan itself remains linear.
    """
    state = _route_state_arrays(vehicle, matrix)
    if state.slack[0] < -EPS:
        return InsertionResult(list(vehicle.route), inf, None, False)
    positions, arrival, slack, load = state.positions, state.arrival, state.slack, state.load
    n = len(positions) - 1
    direct_dist = matrix.dist(order.origin, order.destination)
    direct_time = matrix.travel_time(order.origin, order.destination)
    pickup_deadline = order.release_time + order.max_pickup_delay
    drop_deadline = pickup_deadline + direct_time * (1.0 + order.detour_ratio)
    tau = beta * direct_dist / alpha if alpha > 0 else inf

    best_delta_dist = inf
    best_pair: Optional[Tuple[int, int]] = None

    # zeta/eta for the general case i < j.  We track both the objective-side
    # distance detour and the constraint-side time detour for the same eta.
    zeta_dist = inf
    zeta_time = inf
    eta: Optional[int] = None

    for j in range(n + 1):
        # Special case: i == j, i.e., pickup/dropoff are consecutive.
        delta_special_dist = _delta_for_pair(positions, order, j, j, matrix)
        delta_special_time = _time_delta_for_pair(positions, order, j, j, matrix)
        pickup_arrival = arrival[j] + matrix.travel_time(positions[j], order.origin)
        drop_arrival = pickup_arrival + direct_time
        special_feasible = (
            load[j] <= vehicle.capacity - order.demand
            and pickup_arrival <= pickup_deadline + EPS
            and drop_arrival <= drop_deadline + EPS
            and delta_special_time <= slack[j] + EPS
            and delta_special_dist <= tau + EPS
        )
        if special_feasible and _is_better_pair(delta_special_dist, (j, j), best_delta_dist, best_pair):
            best_delta_dist = delta_special_dist
            best_pair = (j, j)

        # General case i < j.  Update zeta(l_j), eta(l_j) using candidate i=j-1.
        if j > 0:
            prev = j - 1
            if load[prev] > vehicle.capacity - order.demand:
                # Same reset as the uploaded C++ GreedyDP: every earlier pickup
                # candidate would carry the new passenger through an overloaded
                # segment ending at l_j.
                zeta_dist = inf
                zeta_time = inf
                eta = None
            else:
                cand_pickup_time = arrival[prev] + matrix.travel_time(positions[prev], order.origin)
                cand_det_time = time_detour(matrix, positions[prev], order.origin, positions[j])
                cand_det_dist = distance_detour(matrix, positions[prev], order.origin, positions[j])
                # The paper recurrence only shows the capacity and slack terms.
                # We also screen the pickup deadline here; otherwise eta could
                # point to a minimum-detour pickup position that cannot reach the
                # new origin in time, while an earlier position could.
                if cand_pickup_time <= pickup_deadline + EPS and cand_det_time <= slack[prev] + EPS:
                    if cand_det_dist < zeta_dist:
                        zeta_dist = cand_det_dist
                        zeta_time = cand_det_time
                        eta = prev
                # Otherwise, keep the previously maintained candidate.

            if eta is not None and isfinite(zeta_dist):
                delivery_det_dist = distance_detour(
                    matrix, positions[j], order.destination, positions[j + 1] if j < n else None
                )
                delivery_det_time = time_detour(matrix, positions[j], order.destination, positions[j + 1] if j < n else None)
                delta_general_dist = zeta_dist + delivery_det_dist
                delta_general_time = zeta_time + delivery_det_time
                corollary_ok = (
                    load[j] <= vehicle.capacity - order.demand
                    and arrival[j] + zeta_time + matrix.travel_time(positions[j], order.destination) <= drop_deadline + EPS
                    and delta_general_time <= slack[j] + EPS
                )
                if corollary_ok and delta_general_dist <= tau + EPS and _is_better_pair(
                    delta_general_dist, (eta, j), best_delta_dist, best_pair
                ):
                    best_delta_dist = delta_general_dist
                    best_pair = (eta, j)

    if best_pair is None:
        return InsertionResult(list(vehicle.route), inf, None, False)

    best_route = _copy_and_insert(vehicle.route, order, best_pair[0], best_pair[1])
    if verify and not _check_full_route_feasible(vehicle, order, best_route, matrix):
        # Safety fallback: this should not happen under the paper's metric
        # assumptions.  If it does, return infeasible rather than silently
        # accepting a bad route.  Users can run the quadratic operator to debug.
        return InsertionResult(list(vehicle.route), inf, None, False)
    return InsertionResult(best_route, best_delta_dist, best_pair, True)
