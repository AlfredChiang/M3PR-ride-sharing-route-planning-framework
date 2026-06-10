from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def floyd_warshall(n: int, edges: pd.DataFrame) -> np.ndarray:
    dist = np.full((n, n), np.inf, dtype=float)
    np.fill_diagonal(dist, 0.0)
    for row in edges.itertuples(index=False):
        u, v, w = int(row.u), int(row.v), float(row.weight)
        dist[u, v] = min(dist[u, v], w)
        dist[v, u] = min(dist[v, u], w)
    for k in range(n):
        dist = np.minimum(dist, dist[:, [k]] + dist[[k], :])
    return dist


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a small all-pairs grid matrix from an edge-list CSV.")
    parser.add_argument("--edges", type=Path, required=True, help="CSV columns: u,v,weight")
    parser.add_argument("--nodes", type=int, required=True)
    parser.add_argument("--time-per-distance", type=float, default=1.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    edges = pd.read_csv(args.edges)
    required = {"u", "v", "weight"}
    if not required.issubset(edges.columns):
        raise ValueError("edge CSV must contain columns: u,v,weight")
    distance = floyd_warshall(args.nodes, edges)
    time = distance * args.time_per_distance
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, distance=distance, time=time)
    print(f"saved matrix to {args.out}")


if __name__ == "__main__":
    main()
