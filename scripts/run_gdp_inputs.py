from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rideshare_m3pr.io import load_gdp_order_file, load_gdp_taxi_file, load_matrix_npz
from rideshare_m3pr.metrics import stats_to_frame
from rideshare_m3pr.planner import OnlinePlanner, PlannerConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M3PR reproduction on GreedyDP-style taxi/order files.")
    parser.add_argument("--matrix", required=True, help="NPZ file with distance and time arrays")
    parser.add_argument("--taxi", required=True, help="GreedyDP-style taxi.txt")
    parser.add_argument("--orders", required=True, help="GreedyDP-style order.txt")
    parser.add_argument("--algorithm", choices=["linear", "quadratic", "cubic"], default="linear")
    parser.add_argument("--beta", type=float, default=6.5, help="M3PR fare rate beta_o")
    parser.add_argument("--detour-ratio", type=float, default=0.0, help="Use 0 to mimic GreedyDP completion deadline")
    parser.add_argument("--max-orders", type=int, default=None)
    args = parser.parse_args()

    matrix = load_matrix_npz(args.matrix)
    vehicles, params = load_gdp_taxi_file(args.taxi)
    orders = load_gdp_order_file(args.orders, matrix, default_ddl=params["ddl"], detour_ratio=args.detour_ratio)
    if args.max_orders is not None:
        orders = orders[: args.max_orders]

    planner = OnlinePlanner(
        matrix,
        copy.deepcopy(vehicles),
        PlannerConfig(algorithm=args.algorithm, alpha=float(params["alpha"]), beta=args.beta, use_pruning=True),
    )
    stats = planner.run(orders)
    print(stats_to_frame(args.algorithm, stats).to_string(index=False))
    print(f"Loaded {len(vehicles)} vehicles and {len(orders)} orders from GreedyDP-style files.")
    print(f"GreedyDP params: {params}")


if __name__ == "__main__":
    main()
