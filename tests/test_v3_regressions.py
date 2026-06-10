from __future__ import annotations

import copy

from rideshare_m3pr.grid_index import build_identity_grid_index
from rideshare_m3pr.insertion import cubic_insert, linear_profit_bounded_insert, quadratic_dp_insert
from rideshare_m3pr.matrix import GridMatrix
from rideshare_m3pr.models import Order, Stop, Vehicle
from rideshare_m3pr.planner import OnlinePlanner, PlannerConfig, advance_vehicle_to, total_vehicle_distance
from rideshare_m3pr.pruning import dual_side_vehicle_pruning, dual_side_vehicle_pruning_indexed
from rideshare_m3pr.synthetic import make_synthetic_problem


def test_completed_distance_is_accumulated() -> None:
    matrix = GridMatrix.rectangular_grid(3, 1, time_per_edge=10.0)
    order = Order(order_id=1, origin=1, destination=2, release_time=0, max_pickup_delay=100, detour_ratio=1.0)
    vehicle = Vehicle(
        vehicle_id=0,
        current_node=0,
        current_time=0.0,
        route=[Stop(node=1, order_id=1, kind="pickup"), Stop(node=2, order_id=1, kind="dropoff")],
        assigned_orders={1: order},
    )
    advance_vehicle_to(vehicle, 10.0, matrix)
    assert vehicle.current_node == 1
    assert vehicle.completed_distance == 1.0
    assert total_vehicle_distance(vehicle, matrix) == 2.0


def test_indexed_pruning_matches_direct_identity_grid() -> None:
    matrix, vehicles, orders = make_synthetic_problem(n_vehicles=20, n_orders=5, seed=2)
    idx = build_identity_grid_index(matrix, vehicles)
    order = orders[0]
    direct = dual_side_vehicle_pruning(order, vehicles, matrix)
    indexed = dual_side_vehicle_pruning_indexed(order, vehicles, matrix, idx)
    assert [v.vehicle_id for v in indexed] == [v.vehicle_id for v in direct]


def test_linear_quadratic_cubic_single_insertion_agree_on_random_states() -> None:
    matrix, vehicles, orders = make_synthetic_problem(n_vehicles=12, n_orders=80, seed=13, horizon=1000)
    # Build a few realistic route states by running the cubic oracle first.
    planner = OnlinePlanner(matrix, copy.deepcopy(vehicles), PlannerConfig(algorithm="cubic", use_pruning=True))
    planner.run(orders[:40])
    probe_orders = orders[40:55]
    for order in probe_orders:
        for vehicle in planner.vehicles[:6]:
            lin = linear_profit_bounded_insert(vehicle, order, matrix)
            quad = quadratic_dp_insert(vehicle, order, matrix)
            cub = cubic_insert(vehicle, order, matrix)
            assert lin.feasible == quad.feasible == cub.feasible
            if cub.feasible:
                assert abs(lin.delta_distance - cub.delta_distance) < 1e-9
                assert abs(quad.delta_distance - cub.delta_distance) < 1e-9
                assert lin.pair == cub.pair
                assert quad.pair == cub.pair


def test_online_algorithms_match_on_synthetic_default() -> None:
    matrix, vehicles, orders = make_synthetic_problem(n_vehicles=30, n_orders=200, seed=42)
    summaries = []
    for alg in ["linear", "quadratic", "cubic"]:
        planner = OnlinePlanner(matrix, copy.deepcopy(vehicles), PlannerConfig(algorithm=alg, use_pruning=True))
        stats = planner.run(orders)
        summaries.append((stats.served_orders, stats.rejected_orders, round(stats.p_sub, 9)))
    assert summaries[0] == summaries[1] == summaries[2]
