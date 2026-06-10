from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rideshare_m3pr.metrics import stats_to_frame
from rideshare_m3pr.planner import OnlinePlanner, PlannerConfig
from rideshare_m3pr.synthetic import make_synthetic_problem


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a synthetic M3PR ride-sharing reproduction demo.")
    parser.add_argument("--algorithm", choices=["linear", "quadratic", "cubic"], default="linear")
    parser.add_argument("--orders", type=int, default=500)
    parser.add_argument("--vehicles", type=int, default=50)
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--no-pruning", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=None)
    args = parser.parse_args()

    matrix, vehicles, orders = make_synthetic_problem(
        n_vehicles=args.vehicles,
        n_orders=args.orders,
        capacity=args.capacity,
        seed=args.seed,
    )
    config = PlannerConfig(
        algorithm=args.algorithm,
        use_pruning=not args.no_pruning,
        max_candidates=args.max_candidates,
    )
    planner = OnlinePlanner(matrix, copy.deepcopy(vehicles), config)
    stats = planner.run(orders)
    print(stats_to_frame(args.algorithm, stats).to_string(index=False))


if __name__ == "__main__":
    main()
