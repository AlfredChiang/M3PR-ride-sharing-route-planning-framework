"""Dual-side vehicle pruning.

Two implementations are provided:

1. ``dual_side_vehicle_pruning``: direct reachability checks over a vehicle list;
2. ``dual_side_vehicle_pruning_indexed``: grid-indexed origin/destination-side
   filtering based on :class:`GridIndex`.

The indexed version is the closer reproduction of the paper's Section V, while
keeping the direct version useful as a small-scale oracle.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .grid_index import GridIndex
from .matrix import GridMatrix
from .models import Order, Vehicle

EPS = 1e-9


def dual_side_vehicle_pruning(
    order: Order,
    vehicles: Iterable[Vehicle],
    matrix: GridMatrix,
    max_candidates: Optional[int] = None,
) -> List[Vehicle]:
    """Return vehicles satisfying direct origin- and destination-side tests.

    Origin side: ``t(current, origin) <= max_pickup_delay``.
    Destination side: ``t(current, destination) <= max_pickup_delay +
    t(origin,destination)*(1+detour_ratio)``.
    """
    direct_time = matrix.travel_time(order.origin, order.destination)
    pickup_limit = order.max_pickup_delay
    destination_limit = order.max_pickup_delay + direct_time * (1.0 + order.detour_ratio)

    candidates = []
    for v in vehicles:
        t_to_origin = matrix.travel_time(v.current_node, order.origin)
        t_to_dest = matrix.travel_time(v.current_node, order.destination)
        if t_to_origin <= pickup_limit + EPS and t_to_dest <= destination_limit + EPS:
            candidates.append(v)

    candidates.sort(key=lambda v: (matrix.dist(v.current_node, order.origin), len(v.route), v.vehicle_id))
    if max_candidates is not None:
        return candidates[:max_candidates]
    return candidates


def dual_side_vehicle_pruning_indexed(
    order: Order,
    vehicles: Iterable[Vehicle],
    matrix: GridMatrix,
    grid_index: GridIndex,
    max_candidates: Optional[int] = None,
) -> List[Vehicle]:
    """Grid-indexed dual-side pruning.

    The grid index first retrieves reachable origin-side and destination-side
    vehicle id sets from temporal grid lists, then intersects them.  A final
    direct check is retained to handle non-symmetric or user-supplied matrices.
    """
    vehicles_list = list(vehicles)
    vehicles_by_id: Dict[int, Vehicle] = {v.vehicle_id: v for v in vehicles_list}
    grid_index.rebuild_vehicle_lists(vehicles_list)
    candidates = grid_index.query(order, vehicles_by_id, max_candidates=None)
    # Safety refinement for arbitrary matrices; also makes tests exactly match
    # the direct oracle when each node is one grid.
    refined = dual_side_vehicle_pruning(order, candidates, matrix, max_candidates=max_candidates)
    return refined
