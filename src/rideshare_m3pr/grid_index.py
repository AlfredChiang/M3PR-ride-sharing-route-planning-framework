"""Grid-indexed dual-side vehicle pruning for M3PR.

This module implements the scalable-pruning layer that v2 only sketched.  It is
still intentionally lightweight, but it mirrors the paper's Section-V data
structure at the level needed for reproducible experiments:

- each road-network grid/anchor maintains a vehicle list;
- each grid has a temporal grid list sorted by travel time;
- each grid has a spatial grid list sorted by travel distance;
- an incoming order is filtered at both origin and destination sides and the two
  candidate sets are intersected.

For synthetic data each anchor node can be treated as one grid.  For real data,
pass a ``node_to_grid`` map that collapses multiple road nodes to the same grid
anchor.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .matrix import GridMatrix
from .models import Order, Vehicle

EPS = 1e-9


@dataclass
class GridIndex:
    matrix: GridMatrix
    node_to_grid: Optional[Dict[int, int]] = None
    grid_anchor: Optional[Dict[int, int]] = None
    vehicle_lists: Dict[int, List[Vehicle]] = field(default_factory=dict)
    temporal_grid_lists: Dict[int, List[int]] = field(default_factory=dict)
    spatial_grid_lists: Dict[int, List[int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.node_to_grid is None:
            self.node_to_grid = {node: node for node in range(self.matrix.n_nodes)}
        if self.grid_anchor is None:
            # Use the first node seen in each grid as its anchor.
            anchor: Dict[int, int] = {}
            for node, grid in self.node_to_grid.items():
                anchor.setdefault(grid, node)
            self.grid_anchor = anchor
        self._build_grid_lists()

    @property
    def grid_ids(self) -> List[int]:
        return list(self.grid_anchor.keys())

    def node_grid(self, node: int) -> int:
        return self.node_to_grid.get(node, node)  # type: ignore[union-attr]

    def anchor_node(self, grid_id: int) -> int:
        return self.grid_anchor[grid_id]  # type: ignore[index]

    def _build_grid_lists(self) -> None:
        grids = self.grid_ids
        for g in grids:
            anchor_g = self.anchor_node(g)
            self.temporal_grid_lists[g] = sorted(
                grids, key=lambda h: (self.matrix.travel_time(anchor_g, self.anchor_node(h)), h)
            )
            self.spatial_grid_lists[g] = sorted(
                grids, key=lambda h: (self.matrix.dist(anchor_g, self.anchor_node(h)), h)
            )

    def rebuild_vehicle_lists(self, vehicles: Iterable[Vehicle]) -> None:
        grouped: Dict[int, List[Vehicle]] = defaultdict(list)
        for v in vehicles:
            grouped[self.node_grid(v.current_node)].append(v)
        for grid, vs in grouped.items():
            # Stable order: current time, route length, id.  Query functions apply
            # order-specific distance/time keys after retrieving a coarse set.
            vs.sort(key=lambda v: (v.current_time, len(v.route), v.vehicle_id))
        self.vehicle_lists = dict(grouped)

    def grids_reachable_by_time(self, target_node: int, time_limit: float) -> List[int]:
        """Return grids whose anchor can reach ``target_node`` within limit."""
        target_grid = self.node_grid(target_node)
        target_anchor = self.anchor_node(target_grid)
        ret: List[int] = []
        # The temporal list is ordered by distance from the target grid to other
        # grids.  The matrix is symmetric in the paper's undirected road-network
        # abstraction; using target -> grid keeps this list directly reusable.
        for grid in self.temporal_grid_lists[target_grid]:
            anchor = self.anchor_node(grid)
            if self.matrix.travel_time(anchor, target_anchor) <= time_limit + EPS:
                ret.append(grid)
            else:
                # Because the list is sorted by travel time from target grid,
                # remaining grids are not reachable under symmetric metrics.
                break
        return ret

    def query_origin_side(self, order: Order) -> Set[int]:
        pickup_limit = order.max_pickup_delay
        grids = self.grids_reachable_by_time(order.origin, pickup_limit)
        return {v.vehicle_id for g in grids for v in self.vehicle_lists.get(g, [])}

    def query_destination_side(self, order: Order) -> Set[int]:
        direct_time = self.matrix.travel_time(order.origin, order.destination)
        destination_limit = order.max_pickup_delay + direct_time * (1.0 + order.detour_ratio)
        grids = self.grids_reachable_by_time(order.destination, destination_limit)
        return {v.vehicle_id for g in grids for v in self.vehicle_lists.get(g, [])}

    def query(
        self,
        order: Order,
        vehicles_by_id: Dict[int, Vehicle],
        max_candidates: Optional[int] = None,
    ) -> List[Vehicle]:
        """Dual-side query: origin-side candidates ∩ destination-side candidates."""
        origin_ids = self.query_origin_side(order)
        dest_ids = self.query_destination_side(order)
        ids = origin_ids & dest_ids
        candidates = [vehicles_by_id[i] for i in ids]
        candidates.sort(key=lambda v: (self.matrix.dist(v.current_node, order.origin), len(v.route), v.vehicle_id))
        if max_candidates is not None:
            return candidates[:max_candidates]
        return candidates


def build_identity_grid_index(matrix: GridMatrix, vehicles: Iterable[Vehicle]) -> GridIndex:
    """Treat each anchor node as one grid and initialize vehicle lists."""
    idx = GridIndex(matrix=matrix)
    idx.rebuild_vehicle_lists(vehicles)
    return idx
