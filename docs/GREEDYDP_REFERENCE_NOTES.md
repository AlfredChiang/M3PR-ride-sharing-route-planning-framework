# Notes on the Uploaded GreedyDP Reference Code

The uploaded code is the GreedyDP/pruneGreedyDP implementation for shared-mobility route planning.  It is not copied into this reproduction, but its route-planning core is used as an implementation reference for the Python M3PR reproduction.

## 1. Useful files in the reference code

| Reference file | Role | How it informed this repo |
| --- | --- | --- |
| `util.h` | Defines `Worker`, `Request`, grid and route fields | Mapped to `Vehicle`, `Order`, `Stop` in `models.py` |
| `util.cpp` | Implements feasibility, route-state update, GreedyDP insertion, assignment | Re-implemented as `RouteDPState`, `quadratic_dp_insert`, `linear_profit_bounded_insert` |
| `GDP.cpp` | Main loop for GreedyDP: update vehicles, candidate search, assign order | Mapped to `OnlinePlanner.run()` |
| `pruneGDP.cpp` | Adds a pre-evaluation stage before assignment | Related to candidate pruning / early screening in this repo |
| `metric.h/.cpp` | Hub-label shortest path interface with LRU caches | Replaced by `GridMatrix`; real deployment can plug in OSMnx or hub labels |
| `taxi.txt`, `order.txt` | Sample GreedyDP-style input files | Parsed by `load_gdp_taxi_file()` and `load_gdp_order_file()` |

## 2. Core mapping

The reference code encodes a route as a sequence of integers:

```text
rid << 1      pickup of request rid
rid << 1 | 1  dropoff of request rid
```

This reproduction uses explicit stops:

```python
Stop(node=order.origin, order_id=rid, kind="pickup")
Stop(node=order.destination, order_id=rid, kind="dropoff")
```

The reference `Worker` fields map as follows:

| GreedyDP field | Meaning | This repo |
| --- | --- | --- |
| `pid` | current node | `Vehicle.current_node` |
| `tim` | current time | `Vehicle.current_time` |
| `cap` | vehicle capacity | `Vehicle.capacity` |
| `num` | current onboard load | `sum(Vehicle.onboard.values())` |
| `S` | remaining route sequence | `Vehicle.route` |
| `reach` | arrival time at each planned stop | `RouteDPState.arrival` |
| `picked` | onboard load after each stop | `RouteDPState.load` |
| `slack` | minimum downstream deadline slack | `RouteDPState.slack` |

## 3. How the insertion method was improved

The reference `try_insertion()` performs the same two-stage linear scan that appears in our paper's Algorithm 5:

1. It first checks the special case where pickup and dropoff are inserted consecutively.
2. It then maintains a DP array `Det`, which stores the best pickup-side detour before each delivery position.
3. For every possible delivery position, it combines the stored pickup-side detour with the delivery-side detour.

In this repo, `Det` is renamed to the paper notation:

```text
zeta(l_j): best pickup-side detour before delivery position l_j
eta(l_j):  pickup position that achieves zeta(l_j)
```

Compared with the initial scaffold, the updated implementation now:

- separates **distance increments** for the M3PR objective from **time increments** for service-quality constraints;
- mirrors the GreedyDP `reach/picked/slack` arrays through a `RouteDPState` dataclass;
- keeps the Algorithm-5 profit bound `tau_q = beta_o * d(origin, destination) / alpha_v`;
- adds a final route verification option for safety when non-proportional distance/time matrices are used;
- adds tests showing that linear, quadratic, and cubic insertion agree under the paper's proportional distance/time setting.

## 4. Difference from the uploaded reference code

The uploaded GreedyDP code mainly uses one completion deadline per request:

```text
ddl_abs = release_time + direct_travel_time + ddl
```

The M3PR paper uses two service-quality constraints:

```text
pickup_time <= release_time + max_pickup_delay
arrival_dropoff <= release_time + max_pickup_delay
                   + direct_time * (1 + detour_ratio)
```

Therefore, this repo is not a direct copy of the uploaded code.  It is an M3PR adaptation that keeps the same dynamic-programming route-insertion idea while aligning the acceptance decision with the paper's profit-aware objective.

## 5. GreedyDP-style input compatibility

For comparison experiments, this repo adds two input helpers:

```python
from rideshare_m3pr.io import load_gdp_taxi_file, load_gdp_order_file
```

They parse the uploaded `taxi.txt` and `order.txt` style files.  A compatible `matrix.npz` is still required because the uploaded road files and hub-label files are not included here.

## 6. V3-specific notes

v3 keeps the GreedyDP-style insertion-state mapping but adds two M3PR-specific safeguards:

1. **Objective accounting:** GreedyDP reports route distance for active worker schedules under its unified cost. In our online simulator, already-finished route segments are removed from `Vehicle.route`; therefore v3 explicitly accumulates `Vehicle.completed_distance` and adds it back when calculating `P_sub`.
2. **Candidate filtering:** GreedyDP/pruneGreedyDP uses grid search and lower-bound pruning before insertion. M3PR's candidate filtering is different, so v3 implements `GridIndex` with origin-side and destination-side temporal grid queries. This reproduces the dual-side pruning idea without copying the GreedyDP C++ data structures.

The conceptual mapping is now:

| GreedyDP / pruneGreedyDP | M3PR v3 reproduction |
| --- | --- |
| grid candidate search | `GridIndex.query_origin_side()` and `query_destination_side()` |
| `single_search()` | `dual_side_vehicle_pruning_indexed()` |
| `try_insertion()` | `linear_profit_bounded_insert()` |
| `Det` / `Dio` | `zeta_dist` / `zeta_time` |
| `Plc` | `eta` |
| `ans` / total unified cost | `PlanningStats.p_sub` |
