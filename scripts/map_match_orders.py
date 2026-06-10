#!/usr/bin/env python
"""Map raw trip records to grid-anchor ids used by the M3PR simulator.

Input is a CSV with pickup/dropoff coordinates. The script assigns each pickup
and dropoff point to a 650m grid cell produced by ``preprocess_osm.py`` and
writes the normalized ``orders.csv`` consumed by ``scripts/run_real_data.py``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _require_geospatial() -> Any:
    try:
        import geopandas as gpd  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise SystemExit(
            "GeoPandas is required for map matching. Install optional dependencies with:\n"
            "    pip install -r requirements-geospatial.txt"
        ) from exc
    return gpd


def _load_city_assets(city_dir: Path) -> tuple[Any, pd.DataFrame, str]:
    gpd = _require_geospatial()
    grids_path = city_dir / "grids.geojson"
    anchors_path = city_dir / "anchors.csv"
    metadata_path = city_dir / "metadata.json"
    if not grids_path.exists() or not anchors_path.exists():
        raise FileNotFoundError("Expected grids.geojson and anchors.csv in the city directory")
    grids = gpd.read_file(grids_path)
    anchors = pd.read_csv(anchors_path)
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        projected_crs = metadata.get("projected_crs", str(grids.crs))
    else:
        projected_crs = str(grids.crs)
    return grids, anchors, projected_crs


def _seconds_from_column(df: pd.DataFrame, col: str, mode: str, day_start: str | None) -> np.ndarray:
    if mode == "seconds":
        return pd.to_numeric(df[col], errors="coerce").astype(float).to_numpy()
    ts = pd.to_datetime(df[col], errors="coerce")
    if ts.isna().any():
        raise ValueError(f"Failed to parse some timestamps in column {col}")
    if day_start:
        base = pd.Timestamp(day_start)
        if base.tz is None and getattr(ts.dt, "tz", None) is not None:
            base = base.tz_localize(ts.dt.tz)
    else:
        base = ts.min().floor("D")
    return (ts - base).dt.total_seconds().astype(float).to_numpy()


def _nearest_anchor_grid(points_xy: np.ndarray, anchors: pd.DataFrame, chunk_size: int = 50000) -> np.ndarray:
    anchor_xy = anchors[["centroid_x", "centroid_y"]].to_numpy(dtype=float)
    anchor_grid = anchors["grid_id"].to_numpy(dtype=int)
    out = np.empty(points_xy.shape[0], dtype=int)
    for start in range(0, points_xy.shape[0], chunk_size):
        stop = min(start + chunk_size, points_xy.shape[0])
        diff = points_xy[start:stop, None, :] - anchor_xy[None, :, :]
        nearest = np.argmin(np.sum(diff * diff, axis=2), axis=1)
        out[start:stop] = anchor_grid[nearest]
    return out


def _assign_grid_ids(lon: pd.Series, lat: pd.Series, grids: Any, anchors: pd.DataFrame) -> np.ndarray:
    gpd = _require_geospatial()
    pts = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(pd.to_numeric(lon), pd.to_numeric(lat)),
        crs="EPSG:4326",
    ).to_crs(grids.crs)

    joined = gpd.sjoin(pts, grids[["grid_id", "geometry"]], how="left", predicate="within")
    grid_ids = joined["grid_id"].to_numpy()

    missing = pd.isna(grid_ids)
    if missing.any():
        xy = np.column_stack([pts.geometry.x.to_numpy(), pts.geometry.y.to_numpy()])
        fallback = _nearest_anchor_grid(xy[missing], anchors)
        grid_ids[missing] = fallback
    return grid_ids.astype(int)


def main() -> None:
    parser = argparse.ArgumentParser(description="Map raw order coordinates to M3PR grid-anchor ids.")
    parser.add_argument("--city-dir", type=Path, required=True, help="Directory containing anchors.csv and grids.geojson")
    parser.add_argument("--orders-raw", type=Path, required=True, help="Raw trip/order CSV")
    parser.add_argument("--out", type=Path, default=None, help="Output normalized orders.csv")
    parser.add_argument("--pickup-lon-col", default="pickup_longitude")
    parser.add_argument("--pickup-lat-col", default="pickup_latitude")
    parser.add_argument("--dropoff-lon-col", default="dropoff_longitude")
    parser.add_argument("--dropoff-lat-col", default="dropoff_latitude")
    parser.add_argument("--time-col", default="release_time")
    parser.add_argument("--time-mode", choices=["seconds", "timestamp"], default="seconds")
    parser.add_argument("--day-start", default=None, help="Timestamp base for release_time when --time-mode timestamp")
    parser.add_argument("--demand-col", default=None)
    parser.add_argument("--default-demand", type=int, default=1)
    parser.add_argument("--max-pickup-delay", type=float, default=500.0)
    parser.add_argument("--detour-ratio", type=float, default=0.8)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    grids, anchors, _ = _load_city_assets(args.city_dir)
    df = pd.read_csv(args.orders_raw)
    if args.limit is not None:
        df = df.head(args.limit).copy()

    needed = {args.pickup_lon_col, args.pickup_lat_col, args.dropoff_lon_col, args.dropoff_lat_col, args.time_col}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Raw orders CSV is missing columns: {sorted(missing)}")

    print("[1/3] assigning pickup grids")
    origin = _assign_grid_ids(df[args.pickup_lon_col], df[args.pickup_lat_col], grids, anchors)
    print("[2/3] assigning dropoff grids")
    destination = _assign_grid_ids(df[args.dropoff_lon_col], df[args.dropoff_lat_col], grids, anchors)
    release_time = _seconds_from_column(df, args.time_col, args.time_mode, args.day_start)

    if args.demand_col and args.demand_col in df.columns:
        demand = pd.to_numeric(df[args.demand_col], errors="coerce").fillna(args.default_demand).astype(int)
    else:
        demand = pd.Series(args.default_demand, index=df.index, dtype=int)

    out = pd.DataFrame(
        {
            "order_id": np.arange(len(df), dtype=int),
            "origin": origin,
            "destination": destination,
            "release_time": release_time,
            "demand": demand.to_numpy(),
            "max_pickup_delay": args.max_pickup_delay,
            "detour_ratio": args.detour_ratio,
        }
    )
    out = out.replace([np.inf, -np.inf], np.nan).dropna().sort_values("release_time")
    out["order_id"] = np.arange(len(out), dtype=int)

    out_path = args.out or (args.city_dir / "orders.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print("[3/3] done")
    print(f"saved: {out_path} ({len(out)} orders)")


if __name__ == "__main__":
    main()
