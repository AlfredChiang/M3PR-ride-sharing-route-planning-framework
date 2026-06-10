# GitHub Reproduction Document

This document summarizes the current reproduction status for **An Efficient Route Planning Framework for Large Scale Ride-Sharing**.

## Implemented scope

The repository implements the paper's online route-planning component:

- M3PR transformed objective `P_sub`;
- cumulative vehicle-payment cost with executed and remaining distance;
- online order processing framework;
- indexed dual-side vehicle pruning;
- cubic insertion baseline;
- DP-based quadratic insertion;
- profit-bounded DP-based linear insertion;
- synthetic benchmark and tests;
- synthetic parameter sweep and plotting scripts;
- CSV/NPZ real-data input interface;
- GreedyDP-style `taxi.txt` / `order.txt` parser.

## Main algorithmic correspondence

| Paper item | Code location |
| --- | --- |
| Road/grid matrix `G` | `src/rideshare_m3pr/matrix.py` |
| Grid indexing structure | `src/rideshare_m3pr/grid_index.py` |
| Order/vehicle/route model | `src/rideshare_m3pr/models.py` |
| Algorithm 1 | `src/rideshare_m3pr/planner.py` |
| Algorithm 2 | `src/rideshare_m3pr/pruning.py` + `src/rideshare_m3pr/grid_index.py` |
| Algorithm 3 | `cubic_insert()` in `src/rideshare_m3pr/insertion.py` |
| Algorithm 4 | `quadratic_dp_insert()` in `src/rideshare_m3pr/insertion.py` |
| Algorithm 5 | `linear_profit_bounded_insert()` in `src/rideshare_m3pr/insertion.py` |

## V3 verification status

The current v3 release has the following local check result:

```bash
pytest -q
# 8 passed
```

The synthetic comparison script now reports matching order counts and objective values for the linear, quadratic, and cubic insertion operators under the default proportional distance/time setting:

```bash
python scripts/compare_algorithms.py
```

## How to run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python scripts/run_demo.py --algorithm linear --orders 500 --vehicles 50
python scripts/compare_algorithms.py
```

## How to run a synthetic parameter sweep

```bash
python scripts/run_sweep.py --orders 300 --algorithms linear,quadratic
python scripts/plot_results.py --csv results/raw/synthetic_sweep.csv --x pickup_delay --y response_rate
```

## How to run preprocessed real data

Prepare:

```text
matrix.npz   # arrays: distance, time
orders.csv   # order_id,origin,destination,release_time[,demand,max_pickup_delay,detour_ratio]
vehicles.csv # vehicle_id,current_node[,capacity,current_time]
```

Then run:

```bash
python scripts/run_real_data.py \
  --matrix matrix.npz \
  --orders orders.csv \
  --vehicles vehicles.csv \
  --algorithm linear
```

## How to run GreedyDP-style files

The uploaded reference code uses `taxi.txt` and `order.txt`. After preparing a compatible `matrix.npz`, run:

```bash
python scripts/run_gdp_inputs.py \
  --matrix matrix.npz \
  --taxi taxi.txt \
  --orders order.txt \
  --algorithm linear
```

## Current limitations

This is still a clean reproduction scaffold rather than an exact numerical replication of every table/figure. Exact experimental replication still requires:

- Manhattan TLC and Chengdu Didi Gaia raw/cleaned trip data;
- the same filtering and map-matching rules;
- 650m x 650m grid construction;
- anchor-node selection;
- shortest-path distance/time matrix precomputation;
- the same initial vehicle sampling distribution;
- figure/table reproduction scripts for all paper metrics.

## Suggested next milestones

1. Add OSMnx preprocessing for Manhattan and Chengdu.
2. Add trip-cleaning scripts for TLC and Didi Gaia formats.
3. Add figure scripts for response rate, insertion time, utility, and completion time.
4. Optionally add a C++ backend for Algorithm 5 after the Python logic is fully verified.
