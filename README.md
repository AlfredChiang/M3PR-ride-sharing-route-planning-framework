# M3PR Ride-Sharing Route Planning Framework

The current implementation includes:

* online order-by-order route planning;
* price-aware M3PR decision logic;
* dual-side grid-indexed vehicle pruning;
* cubic insertion baseline;
* quadratic DP-based insertion;
* profit-bounded linear DP-based insertion;
* route feasibility checking under:

  * vehicle capacity constraints;
  * pickup-delay constraints;
  * detour-ratio constraints;
  * compatibility constraints for existing onboard orders;
* cumulative route-cost accounting;
* synthetic data generation for quick verification;
* experiment scripts for comparing insertion algorithms and running parameter sweeps.

## Repository Structure

```text
.
├── README.md
├── requirements.txt
├── pyproject.toml
├── src/
│   └── rideshare_m3pr/
│       ├── models.py
│       ├── matrix.py
│       ├── grid_index.py
│       ├── pruning.py
│       ├── insertion.py
│       ├── planner.py
│       ├── synthetic.py
│       ├── io.py
│       └── metrics.py
├── scripts/
│   ├── run_demo.py
│   ├── compare_algorithms.py
│   ├── run_sweep.py
│   ├── plot_results.py
│   ├── build_grid_matrix.py
│   └── run_gdp_inputs.py
├── tests/
└── docs/
```

## Installation

The implementation is written in Python.

```bash
pip install -r requirements.txt
pip install -e .
```

Recommended environment:

```text
Python >= 3.9
numpy
pandas
pytest
matplotlib
```

## Quick Start

Run a small synthetic experiment with the linear DP insertion method:

```bash
python scripts/run_demo.py --algorithm linear --orders 100 --vehicles 20
```

Compare different insertion methods:

```bash
python scripts/compare_algorithms.py
```

Run the test suite:

```bash
pytest -q
```

## Implemented Algorithms

### Cubic Insertion

The cubic insertion baseline enumerates all possible pickup and delivery insertion positions and checks route feasibility from scratch.

### Quadratic DP Insertion

The quadratic DP-based method uses auxiliary route states to reduce feasibility checking and insertion-cost calculation to constant time for each candidate pair.

### Profit-Bounded Linear DP Insertion

The linear DP-based method scans delivery positions once and maintains the best feasible pickup-side state dynamically. It further applies a price-aware profit bound to avoid insertions that are dominated by rejecting the order.

## M3PR Objective

The implementation follows the transformed price-aware M3PR objective:

```text
P_sub = revenue loss of unserved orders + vehicle routing cost
```

For each incoming order, the planner evaluates whether accepting the order is profitable under the current route context. A feasible insertion is accepted only when the resulting additional vehicle cost does not exceed the revenue loss caused by rejecting the order.

Passenger-side service quality is handled by hard constraints instead of being mixed directly into the economic objective.

## Data

The repository currently provides synthetic data generation for quick testing and debugging.

For full-scale experiments on real-world datasets, the expected processed input format is:

```text
data/processed/{city}/grid_matrix.npz
data/processed/{city}/orders.csv
data/processed/{city}/vehicles.csv
```

Preprocessing pipeline includes:

1. extracting the road network;
2. partitioning the city into grids;
3. selecting anchor nodes for grids;
4. mapping order origins and destinations to anchor nodes;
5. precomputing shortest-path distance and travel-time matrices;
6. generating initial vehicle states.

The raw Manhattan and Chengdu datasets are not included in this repository because of data availability and licensing restrictions.

## Example Commands

Run a synthetic demo:

```bash
python scripts/run_demo.py --algorithm linear --orders 100 --vehicles 20
```

Compare insertion methods:

```bash
python scripts/compare_algorithms.py
```

Run a parameter sweep:

```bash
python scripts/run_sweep.py
```

Plot results:

```bash
python scripts/plot_results.py
```

## Relation to Prior Work

The route-insertion module is inspired by the dynamic-programming insertion principle used in prior shared-mobility route-planning studies, especially GreedyDP / pruneGreedyDP.

This repository adapts the DP insertion idea to the M3PR setting by incorporating:

* the transformed price-aware objective;
* order-specific pickup-delay constraints;
* detour-ratio constraints;
* compatibility checks for existing assigned orders;
* profit-bound filtering;
* dual-side vehicle pruning.

The current implementation is suitable for:

* verifying algorithm logic;
* testing insertion methods;
* running synthetic experiments;
* extending the framework to real-world ride-sharing data.

Full numerical reproduction of the paper's real-world experimental results requires access to the corresponding ride-sharing datasets, road networks, grid construction, and shortest-path preprocessing.

## Citation

If you use this repository in your research, please cite the paper:

```bibtex
@article{jiang2025m3pr,
  title   = {An Efficient Route Planning Framework for Large-Scale Ride-Sharing},
  author  = {Jiang, Kai and Cao, Yue and Zhou, Huan and Jiang, Man and Wang, Zhenning and Hu, Ziyi},
  journal = {IEEE Transactions on Mobile Computing},
  year    = {Under Revision}
}
```

## License

Please check the license file before using or redistributing this repository.
