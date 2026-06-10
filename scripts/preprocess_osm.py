#!/usr/bin/env python
"""Build grid anchors from an OpenStreetMap road network.

Outputs under ``data/processed/<city>/`` by default:

- ``road.graphml``: projected drivable road network with length/travel_time
- ``anchors.csv``: 650m-grid anchors used as matrix/order node ids
- ``grids.geojson``: grid polygons in the projected CRS
- ``metadata.json``: preprocessing parameters and CRS information

The script intentionally keeps preprocessing explicit instead of hiding it in a
notebook so that a GitHub user can reproduce or modify each step.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from shapely.geometry import Point, box


def _require_geospatial() -> tuple[Any, Any]:
    try:
        import geopandas as gpd  # type: ignore
        import osmnx as ox  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise SystemExit(
            "Geospatial dependencies are missing. Install them with:\n"
            "    pip install -r requirements-geospatial.txt"
        ) from exc
    return gpd, ox


#def _call(obj: Any, dotted: str, *args: Any, **kwargs: Any) -> Any:
 #   """Call an OSMnx function across old/new namespace layouts."""
  #  cur = obj
 #   for part in dotted.split("."):
 #       cur = getattr(cur, part)
 #   return cur(*args, **kwargs)


def _get_ox_fn(ox: Any, name: str) -> Any:
    """Resolve OSMnx functions for both v1-style aliases and v2 modules."""
    candidates = {
        "graph_from_place": ["graph_from_place", "graph.graph_from_place"],
        "project_graph": ["project_graph", "projection.project_graph"],
        "graph_to_gdfs": ["graph_to_gdfs", "convert.graph_to_gdfs"],
        "nearest_nodes": ["distance.nearest_nodes", "nearest_nodes"],
        "save_graphml": ["save_graphml", "io.save_graphml"],
        "load_graphml": ["load_graphml", "io.load_graphml"],
        "add_edge_speeds": ["add_edge_speeds", "routing.add_edge_speeds"],
        "add_edge_travel_times": ["add_edge_travel_times", "routing.add_edge_travel_times"],
    }[name]
    for dotted in candidates:
        try:
            cur = ox
            for part in dotted.split("."):
                cur = getattr(cur, part)
            return cur
        except AttributeError:
            continue
    raise AttributeError(f"Cannot find OSMnx function {name}")


def _download_or_load_graph(ox: Any, args: argparse.Namespace) -> Any:
    load_graphml = _get_ox_fn(ox, "load_graphml")
    graph_from_place = _get_ox_fn(ox, "graph_from_place")
    project_graph = _get_ox_fn(ox, "project_graph")
    save_graphml = _get_ox_fn(ox, "save_graphml")
    add_edge_speeds = _get_ox_fn(ox, "add_edge_speeds")
    add_edge_travel_times = _get_ox_fn(ox, "add_edge_travel_times")

    if args.graphml and args.graphml.exists():
        print(f"[1/4] loading GraphML: {args.graphml}")
        graph = load_graphml(args.graphml)
    else:
        print(f"[1/4] downloading OSM graph for: {args.place}")
        graph = graph_from_place(
            args.place,
            network_type=args.network_type,
            simplify=True,
            retain_all=False,
            truncate_by_edge=True,
        )

    print("[2/4] projecting graph and adding travel-time attributes")
    graph = project_graph(graph)

    # Add length/speed/time attributes when possible. OSMnx needs speed_kph
    # before travel_time. A fallback speed keeps sparse OSM maxspeed tags usable.
    try:
        graph = add_edge_speeds(graph, fallback=args.fallback_speed_kph)
        graph = add_edge_travel_times(graph)
    except Exception as exc:  # pragma: no cover - depends on OSM tags
        print(f"warning: failed to infer speed/travel_time with OSMnx: {exc}")
        for _, _, _, data in graph.edges(keys=True, data=True):
            length = float(data.get("length", 0.0))
            data["travel_time"] = length / (args.fallback_speed_kph * 1000.0 / 3600.0)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    save_graphml(graph, args.out_dir / "road.graphml")
    return graph


def _make_grid(gpd: Any, graph: Any, grid_size_m: float, max_anchor_distance_m: float | None) -> tuple[Any, pd.DataFrame]:
    graph_to_gdfs = _get_ox_fn(__import__("osmnx"), "graph_to_gdfs")
    nearest_nodes = _get_ox_fn(__import__("osmnx"), "nearest_nodes")

    nodes, _ = graph_to_gdfs(graph, nodes=True, edges=True)
    crs = nodes.crs
    minx, miny, maxx, maxy = nodes.total_bounds

    xs = np.arange(minx, maxx + grid_size_m, grid_size_m)
    ys = np.arange(miny, maxy + grid_size_m, grid_size_m)

    rows: list[dict[str, Any]] = []
    geoms = []
    for row_idx, y0 in enumerate(ys[:-1]):
        for col_idx, x0 in enumerate(xs[:-1]):
            geom = box(x0, y0, x0 + grid_size_m, y0 + grid_size_m)
            centroid = geom.centroid
            anchor, dist = nearest_nodes(graph, X=[centroid.x], Y=[centroid.y], return_dist=True)
            anchor_node = anchor[0]
            anchor_dist = float(dist[0])
            if max_anchor_distance_m is not None and anchor_dist > max_anchor_distance_m:
                continue
            grid_id = len(rows)
            rows.append(
                {
                    "grid_id": grid_id,
                    "row": row_idx,
                    "col": col_idx,
                    "anchor_node": str(anchor_node),
                    "centroid_x": float(centroid.x),
                    "centroid_y": float(centroid.y),
                    "anchor_distance_m": anchor_dist,
                }
            )
            geoms.append(geom)

    grids = gpd.GeoDataFrame(rows, geometry=geoms, crs=crs)

    # Add geographic coordinates for readability/debugging.
    anchor_points = gpd.GeoDataFrame(
        grids[["grid_id"]].copy(),
        geometry=[Point(xy) for xy in zip(grids["centroid_x"], grids["centroid_y"])],
        crs=crs,
    ).to_crs(epsg=4326)
    grids["centroid_lon"] = anchor_points.geometry.x.values
    grids["centroid_lat"] = anchor_points.geometry.y.values

    anchors = grids.drop(columns="geometry").copy()
    return grids, anchors


def main() -> None:
    parser = argparse.ArgumentParser(description="Download/project an OSM road network and build 650m grid anchors.")
    parser.add_argument("--place", required=True, help='OSM place query, e.g. "Manhattan, New York City, USA"')
    parser.add_argument("--city", required=True, help="Output city key, e.g. manhattan or chengdu")
    parser.add_argument("--out-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--graphml", type=Path, default=None, help="Optional existing GraphML to reuse instead of downloading")
    parser.add_argument("--network-type", default="drive", help="OSMnx network_type")
    parser.add_argument("--grid-size-m", type=float, default=650.0)
    parser.add_argument("--fallback-speed-kph", type=float, default=30.0)
    parser.add_argument("--max-anchor-distance-m", type=float, default=None, help="Drop cells farther than this from any road node")
    args = parser.parse_args()

    gpd, ox = _require_geospatial()
    args.out_dir = args.out_root / args.city

    graph = _download_or_load_graph(ox, args)

    print(f"[3/4] building {args.grid_size_m:.0f}m grid and anchor nodes")
    grids, anchors = _make_grid(gpd, graph, args.grid_size_m, args.max_anchor_distance_m)
    grids.to_file(args.out_dir / "grids.geojson", driver="GeoJSON")
    anchors.to_csv(args.out_dir / "anchors.csv", index=False)

    metadata = {
        "place": args.place,
        "city": args.city,
        "network_type": args.network_type,
        "grid_size_m": args.grid_size_m,
        "fallback_speed_kph": args.fallback_speed_kph,
        "max_anchor_distance_m": args.max_anchor_distance_m,
        "projected_crs": str(grids.crs),
        "num_grids": int(len(anchors)),
        "num_graph_nodes": int(graph.number_of_nodes()),
        "num_graph_edges": int(graph.number_of_edges()),
    }
    (args.out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("[4/4] done")
    print(f"saved: {args.out_dir / 'road.graphml'}")
    print(f"saved: {args.out_dir / 'anchors.csv'} ({len(anchors)} anchors)")
    print(f"saved: {args.out_dir / 'grids.geojson'}")


if __name__ == "__main__":
    main()
