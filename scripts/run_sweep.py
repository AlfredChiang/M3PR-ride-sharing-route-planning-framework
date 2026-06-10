from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from rideshare_m3pr.metrics import stats_to_frame
from rideshare_m3pr.planner import OnlinePlanner, PlannerConfig
from rideshare_m3pr.synthetic import make_synthetic_problem


def parse_int_list(text: str) -> list[int]:
    return [int(x) for x in text.split(",") if x.strip()]


def parse_float_list(text: str) -> list[float]:
    return [float(x) for x in text.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run synthetic parameter sweeps for the M3PR reproduction.")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "raw" / "synthetic_sweep.csv")
    parser.add_argument("--algorithms", default="linear,quadratic")
    parser.add_argument("--vehicle-counts", default="50,100")
    parser.add_argument("--capacities", default="4,6")
    parser.add_argument("--pickup-delays", default="300,500,700")
    parser.add_argument("--detour-ratios", default="0.5,0.8,1.0")
    parser.add_argument("--orders", type=int, default=500)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rows = []
    algorithms = [x.strip() for x in args.algorithms.split(",") if x.strip()]
    for n_vehicles in parse_int_list(args.vehicle_counts):
        for capacity in parse_int_list(args.capacities):
            for pickup_delay in parse_float_list(args.pickup_delays):
                for detour_ratio in parse_float_list(args.detour_ratios):
                    matrix, vehicles, orders = make_synthetic_problem(
                        n_vehicles=n_vehicles,
                        n_orders=args.orders,
                        capacity=capacity,
                        pickup_delay=pickup_delay,
                        detour_ratio=detour_ratio,
                        seed=args.seed,
                    )
                    for alg in algorithms:
                        planner = OnlinePlanner(matrix, copy.deepcopy(vehicles), PlannerConfig(algorithm=alg))
                        stats = planner.run(orders)
                        frame = stats_to_frame(alg, stats)
                        row = frame.iloc[0].to_dict()
                        row.update(
                            {
                                "n_vehicles": n_vehicles,
                                "capacity": capacity,
                                "pickup_delay": pickup_delay,
                                "detour_ratio": detour_ratio,
                                "n_orders": args.orders,
                                "seed": args.seed,
                            }
                        )
                        rows.append(row)
    out = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"saved {len(out)} rows to {args.out}")


if __name__ == "__main__":
    main()
