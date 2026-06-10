#!/usr/bin/env python
"""Generate initial vehicle states from grid anchors or observed order origins."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate vehicles.csv for preprocessed M3PR data.")
    parser.add_argument("--city-dir", type=Path, required=True, help="Directory containing anchors.csv")
    parser.add_argument("--orders", type=Path, default=None, help="Optional orders.csv to sample initial nodes from observed origins")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--vehicles", type=int, default=1500)
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample-from", choices=["anchors", "order_origins"], default="anchors")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    anchors = pd.read_csv(args.city_dir / "anchors.csv")
    if args.sample_from == "order_origins" and args.orders:
        orders = pd.read_csv(args.orders)
        candidates = orders["origin"].to_numpy(dtype=int)
    else:
        candidates = anchors["grid_id"].to_numpy(dtype=int)
    if len(candidates) == 0:
        raise ValueError("No candidate nodes available for vehicle generation")

    current_nodes = rng.choice(candidates, size=args.vehicles, replace=True)
    vehicles = pd.DataFrame(
        {
            "vehicle_id": np.arange(args.vehicles, dtype=int),
            "current_node": current_nodes.astype(int),
            "capacity": args.capacity,
            "current_time": 0.0,
        }
    )
    out = args.out or (args.city_dir / "vehicles.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    vehicles.to_csv(out, index=False)
    print(f"saved: {out} ({len(vehicles)} vehicles)")


if __name__ == "__main__":
    main()
