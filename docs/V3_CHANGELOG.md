# V3 changelog

This document summarizes the changes made after comparing v2 with the M3PR paper and the GreedyDP/pruneGreedyDP reference implementation.

## 1. Corrected transformed-objective accounting

v2 computed the routing-cost term using only the remaining planned routes at the end of the simulation. This can underestimate the transformed objective because route segments already executed during the online process are removed from the vehicle route.

v3 adds the following fields to `Vehicle`:

```python
completed_distance: float
completed_time: float
```

`advance_vehicle_to()` now accumulates completed distance/time whenever a vehicle reaches a planned stop. The final objective is computed as:

```python
routing_cost = alpha * sum(v.completed_distance + route_distance(v) for v in vehicles)
p_sub = unserved_loss + routing_cost
```

## 2. Added grid-indexed dual-side vehicle pruning

v2 used direct all-vehicle reachability checks. v3 adds `src/rideshare_m3pr/grid_index.py`, which implements:

- `vehicle_lists`: vehicles grouped by current grid;
- `temporal_grid_lists`: per-grid candidate grids sorted by travel time;
- `spatial_grid_lists`: per-grid candidate grids sorted by distance;
- `query_origin_side()`;
- `query_destination_side()`;
- `query()`: origin-side and destination-side intersection.

The planner uses indexed pruning by default and falls back to direct pruning when `PlannerConfig(use_grid_index=False)` is set.

## 3. Stabilized DP insertion tie-breaking

The linear DP operator scans delivery positions, while cubic/quadratic operators enumerate insertion pairs. On grid matrices, many insertion pairs can have exactly the same increased distance. Without a shared tie rule, the algorithms can choose different but equally good routes, causing later online decisions to diverge.

v3 adds deterministic lexicographic tie-breaking through `_is_better_pair()` so cubic, quadratic, and linear operators agree on synthetic tests under proportional distance/time settings.

## 4. Added regression tests

New tests in `tests/test_v3_regressions.py` cover:

- completed-distance accumulation;
- indexed pruning matching direct pruning on an identity grid;
- linear/quadratic/cubic single-insertion consistency;
- online algorithm consistency on a synthetic benchmark.

Current test command:

```bash
pytest -q
```

Expected result at the time of this release:

```text
8 passed
```

## 5. Added experiment helper scripts

v3 adds:

- `scripts/run_sweep.py`: synthetic parameter sweeps;
- `scripts/plot_results.py`: simple plotting for sweep CSV files;
- `scripts/build_grid_matrix.py`: small all-pairs matrix builder from edge-list CSV.

These scripts make the repository closer to a paper-reproduction workflow while keeping real Manhattan/Chengdu preprocessing as a user-provided data step.
