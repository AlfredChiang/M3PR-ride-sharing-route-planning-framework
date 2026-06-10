#!/usr/bin/env python
"""Convenience wrapper for the real-data preprocessing workflow.

The wrapper prints and optionally runs the standard sequence:
1. OSM network + 650m grid anchors
2. raw order map matching to grid ids
3. vehicle initialization
4. grid-anchor shortest-path matrix construction

For large cities, matrix construction may take a long time. Use ``--dry-run``
first to inspect the commands.
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], dry_run: bool) -> None:
    print("\n$ " + " ".join(shlex.quote(x) for x in cmd))
    if not dry_run:
        subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the M3PR real-data preprocessing pipeline.")
    parser.add_argument("--city", required=True)
    parser.add_argument("--place", required=True)
    parser.add_argument("--raw-orders", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--vehicles", type=int, default=1500)
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--grid-size-m", type=float, default=650.0)
    parser.add_argument("--time-col", default="release_time")
    parser.add_argument("--time-mode", choices=["seconds", "timestamp"], default="seconds")
    parser.add_argument("--pickup-lon-col", default="pickup_longitude")
    parser.add_argument("--pickup-lat-col", default="pickup_latitude")
    parser.add_argument("--dropoff-lon-col", default="dropoff_longitude")
    parser.add_argument("--dropoff-lat-col", default="dropoff_latitude")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    py = sys.executable
    city_dir = args.out_root / args.city

    _run(
        [
            py,
            "scripts/preprocess_osm.py",
            "--city",
            args.city,
            "--place",
            args.place,
            "--out-root",
            str(args.out_root),
            "--grid-size-m",
            str(args.grid_size_m),
        ],
        args.dry_run,
    )
    _run(
        [
            py,
            "scripts/map_match_orders.py",
            "--city-dir",
            str(city_dir),
            "--orders-raw",
            str(args.raw_orders),
            "--time-col",
            args.time_col,
            "--time-mode",
            args.time_mode,
            "--pickup-lon-col",
            args.pickup_lon_col,
            "--pickup-lat-col",
            args.pickup_lat_col,
            "--dropoff-lon-col",
            args.dropoff_lon_col,
            "--dropoff-lat-col",
            args.dropoff_lat_col,
        ],
        args.dry_run,
    )
    _run(
        [
            py,
            "scripts/generate_vehicles.py",
            "--city-dir",
            str(city_dir),
            "--orders",
            str(city_dir / "orders.csv"),
            "--vehicles",
            str(args.vehicles),
            "--capacity",
            str(args.capacity),
            "--sample-from",
            "order_origins",
        ],
        args.dry_run,
    )
    _run(
        [py, "scripts/build_shortest_path_matrix.py", "--city-dir", str(city_dir)],
        args.dry_run,
    )


if __name__ == "__main__":
    main()
