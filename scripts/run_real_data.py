from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rideshare_m3pr.io import load_matrix_npz, load_orders_csv, load_vehicles_csv
from rideshare_m3pr.metrics import stats_to_frame
from rideshare_m3pr.planner import OnlinePlanner, PlannerConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M3PR reproduction on CSV/NPZ preprocessed data.")
    parser.add_argument("--matrix", required=True, help="NPZ file with distance and time arrays")
    parser.add_argument("--orders", required=True, help="CSV file with order_id, origin, destination, release_time")
    parser.add_argument("--vehicles", required=True, help="CSV file with vehicle_id, current_node")
    parser.add_argument("--algorithm", choices=["linear", "quadratic", "cubic"], default="linear")
    parser.add_argument("--alpha", type=float, default=1.7)
    parser.add_argument("--beta", type=float, default=6.5)
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--no-pruning", action="store_true")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    matrix = load_matrix_npz(args.matrix)
    orders = load_orders_csv(args.orders)
    vehicles = load_vehicles_csv(args.vehicles)

    planner = OnlinePlanner(
        matrix,
        copy.deepcopy(vehicles),
        PlannerConfig(
            algorithm=args.algorithm,
            alpha=args.alpha,
            beta=args.beta,
            use_pruning=not args.no_pruning,
            max_candidates=args.max_candidates,
        ),
    )
    stats = planner.run(orders)
    frame = stats_to_frame(args.algorithm, stats)
    print(frame.to_string(index=False))

    if args.json_out:
        payload = frame.iloc[0].to_dict()
        Path(args.json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
