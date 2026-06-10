from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from rideshare_m3pr.metrics import stats_to_frame
from rideshare_m3pr.planner import OnlinePlanner, PlannerConfig
from rideshare_m3pr.synthetic import make_synthetic_problem


def main() -> None:
    matrix, vehicles, orders = make_synthetic_problem(n_vehicles=60, n_orders=800, seed=42)
    frames = []
    for alg in ["linear", "quadratic", "cubic"]:
        planner = OnlinePlanner(matrix, copy.deepcopy(vehicles), PlannerConfig(algorithm=alg, use_pruning=True))
        stats = planner.run(orders)
        frames.append(stats_to_frame(alg, stats))
    print(pd.concat(frames, ignore_index=True).to_string(index=False))


if __name__ == "__main__":
    main()
