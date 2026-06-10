# M3PR Ride-Sharing Route Planning Reproduction

This repository is a clean, executable reproduction scaffold for the paper:

> **An Efficient Route Planning Framework for Large Scale Ride-Sharing**  
> Kai Jiang, Yue Cao, Huan Zhou, Man Jiang, Zhenning Wang, Ziyi Hu

The implementation focuses on the online route-planning component: dual-side vehicle pruning, order insertion, and the transformed price-aware M3PR objective.

## v3 highlights

Compared with v2, this version adds three correctness-oriented updates:

1. **Correct cumulative route-cost accounting.** Vehicles now track `completed_distance` and `completed_time`, so the final `P_sub` includes both executed distance and remaining planned-route distance.
2. **Indexed dual-side pruning.** `GridIndex` implements per-grid vehicle lists, temporal grid lists, spatial grid lists, and origin/destination-side candidate intersection.
3. **Stronger DP consistency tests.** Linear, quadratic, and cubic insertion now share deterministic tie-breaking and are tested against one another on random route states.

## What is implemented

| Paper component | Repository implementation |
| --- | --- |
| Road-network grid abstraction and spatiotemporal grid matrix | `GridMatrix` in `src/rideshare_m3pr/matrix.py` |
| Grid-indexed vehicle pruning | `GridIndex` in `src/rideshare_m3pr/grid_index.py` |
| Order / vehicle / route schedule model | `Order`, `Vehicle`, `Stop` in `src/rideshare_m3pr/models.py` |
| Algorithm 1: online solution framework | `OnlinePlanner` in `src/rideshare_m3pr/planner.py` |
| Algorithm 2: dual-side vehicle pruning | `dual_side_vehicle_pruning_indexed` in `src/rideshare_m3pr/pruning.py` |
| Algorithm 3: cubic insertion baseline | `cubic_insert` in `src/rideshare_m3pr/insertion.py` |
| Algorithm 4: DP-based quadratic insertion | `quadratic_dp_insert` in `src/rideshare_m3pr/insertion.py` |
| Algorithm 5: profit-bounded DP-based linear insertion | `linear_profit_bounded_insert` in `src/rideshare_m3pr/insertion.py` |
| Synthetic reproducibility demo | `scripts/run_demo.py`, `scripts/compare_algorithms.py` |
| Parameter sweep and plotting | `scripts/run_sweep.py`, `scripts/plot_results.py` |
| Matrix builder for small edge lists | `scripts/build_grid_matrix.py` |
| Real-data runner | `scripts/run_real_data.py` |
| GreedyDP-style input adapter | `scripts/run_gdp_inputs.py`, `load_gdp_taxi_file()`, `load_gdp_order_file()` |

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Quick start

Run the Algorithm-5-style linear insertion demo on synthetic grid data:

```bash
python scripts/run_demo.py --algorithm linear --orders 500 --vehicles 50
```

Compare the linear, quadratic, and cubic insertion variants:

```bash
python scripts/compare_algorithms.py
```

Run tests:

```bash
pytest -q
```

Run a small parameter sweep:

```bash
python scripts/run_sweep.py --orders 300 --algorithms linear,quadratic
python scripts/plot_results.py --csv results/raw/synthetic_sweep.csv --x pickup_delay --y response_rate
```

Run preprocessed CSV/NPZ data:

```bash
python scripts/run_real_data.py --matrix matrix.npz --orders orders.csv --vehicles vehicles.csv --algorithm linear
```

## Expected input format for real data

The original paper uses Manhattan and Chengdu trip records after road-network, map-matching, grid-partition, and anchor-node preprocessing. This repository does not include those datasets. To run real experiments, prepare three files.

### `orders.csv`

Required columns:

```text
order_id,origin,destination,release_time
```

Optional columns:

```text
demand,max_pickup_delay,detour_ratio
```

Here `origin` and `destination` are grid-anchor node ids after map matching.

### `vehicles.csv`

Required columns:

```text
vehicle_id,current_node
```

Optional columns:

```text
capacity,current_time
```

### `matrix.npz`

A NumPy archive with two arrays:

```text
distance: shape [n_nodes, n_nodes]
time:     shape [n_nodes, n_nodes]
```

They correspond to the paper's precomputed spatiotemporal grid matrix. For small custom graphs, `scripts/build_grid_matrix.py` can build this matrix from a CSV edge list with columns `u,v,weight`.

## GreedyDP reference relationship

This repository does not copy the GreedyDP/pruneGreedyDP C++ implementation. It uses a clean Python implementation of the same DP insertion principle, adapted to the M3PR paper's price-aware objective, pickup-delay constraint, detour-ratio constraint, compatibility check, and profit bound.

A useful mapping is:

| GreedyDP / URPSM | M3PR reproduction |
| --- | --- |
| worker `w` | vehicle `ν_i` |
| request `r` | order `o_q` |
| `UC(W,R)` | transformed objective `P_sub(O,N)` |
| `α` | `α_ν` |
| penalty `p_r` | `β_o * d(o_s,o_e)` |
| `arr/reach` | `arrival` |
| `slack` | downstream time slack `T(l_k)` |
| `picked` | load state `ρ(l_k)` |
| `Dio[j]` | pickup-side best detour `ζ(l_j)` |
| `Plc[j]` | best pickup location `η(l_j)` |

See `docs/GREEDYDP_REFERENCE_NOTES.md` and `docs/V3_CHANGELOG.md` for details.

## Reproduction scope

This is a GitHub-ready reproduction scaffold rather than an exact numerical replica of the full experimental section. Exact numerical reproduction requires the same cleaned Manhattan/Chengdu trip records, grid partition, anchor-node extraction, OSM/QGIS preprocessing, and shortest-path matrix generation used by the paper.

The current code provides faithful objective logic, executable Algorithms 1--5, indexed dual-side pruning, synthetic benchmarks, CSV/NPZ real-data hooks, GreedyDP-style input adapters, and unit tests.

## Repository structure

```text
m3pr_rideshare_reproduction/
├── README.md
├── requirements.txt
├── pyproject.toml
├── src/rideshare_m3pr/
│   ├── models.py
│   ├── matrix.py
│   ├── grid_index.py
│   ├── pruning.py
│   ├── insertion.py
│   ├── planner.py
│   ├── synthetic.py
│   ├── io.py
│   └── metrics.py
├── scripts/
│   ├── run_demo.py
│   ├── compare_algorithms.py
│   ├── run_sweep.py
│   ├── plot_results.py
│   ├── build_grid_matrix.py
│   ├── run_real_data.py
│   └── run_gdp_inputs.py
├── tests/
│   ├── test_insertion.py
│   └── test_v3_regressions.py
└── docs/
    ├── REPRODUCTION_GUIDE.md
    ├── GREEDYDP_REFERENCE_NOTES.md
    ├── GITHUB_REPRODUCTION_DOCUMENT.md
    ├── V3_CHANGELOG.md
    ├── THIRD_PARTY_NOTICES.md
    └── GITHUB_UPLOAD_CHECKLIST.md
```

## Citation

If you use or extend this code, cite the M3PR paper and clearly state whether your experiment uses synthetic data or the original preprocessed Manhattan/Chengdu data. If you discuss the DP insertion lineage, also cite Tong et al., PVLDB 2018.
