import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rideshare_m3pr.insertion import (
    _check_full_route_feasible,
    cubic_insert,
    linear_profit_bounded_insert,
    quadratic_dp_insert,
)
from rideshare_m3pr.matrix import GridMatrix
from rideshare_m3pr.models import Order, Stop, Vehicle


def test_empty_route_insert_is_feasible():
    matrix = GridMatrix.rectangular_grid(4, 4, time_per_edge=60)
    v = Vehicle(vehicle_id=0, current_node=0, capacity=4, current_time=0)
    o = Order(order_id=0, origin=1, destination=5, release_time=0, max_pickup_delay=500, detour_ratio=1.0)
    res = linear_profit_bounded_insert(v, o, matrix)
    assert res.feasible
    assert res.pair == (0, 0)
    assert len(res.route) == 2
    assert _check_full_route_feasible(v, o, res.route, matrix)


def test_linear_not_worse_than_cubic_on_simple_empty_route():
    matrix = GridMatrix.rectangular_grid(4, 4, time_per_edge=60)
    v = Vehicle(vehicle_id=0, current_node=0, capacity=4, current_time=0)
    o = Order(order_id=0, origin=1, destination=15, release_time=0, max_pickup_delay=500, detour_ratio=1.0)
    linear = linear_profit_bounded_insert(v, o, matrix)
    cubic = cubic_insert(v, o, matrix)
    assert linear.feasible == cubic.feasible
    assert abs(linear.delta_distance - cubic.delta_distance) < 1e-9


def test_linear_quadratic_cubic_agree_on_existing_route_under_proportional_metric():
    """Algorithm 5 should match exhaustive search in the paper's metric setting.

    The paper uses a constant-speed abstraction where travel distance and travel
    time are interchangeable up to a scale factor.  On the synthetic grid, the
    linear zeta/eta recurrence should therefore select the same minimum-distance
    insertion as the quadratic and cubic methods.
    """
    matrix = GridMatrix.rectangular_grid(5, 5, time_per_edge=10)
    existing = {
        10: Order(10, origin=1, destination=7, release_time=0, demand=1, max_pickup_delay=10_000, detour_ratio=100),
        11: Order(11, origin=2, destination=12, release_time=0, demand=1, max_pickup_delay=10_000, detour_ratio=100),
    }
    v = Vehicle(vehicle_id=0, current_node=0, capacity=4, current_time=0)
    v.assigned_orders = dict(existing)
    v.route = [
        Stop(existing[10].origin, 10, "pickup"),
        Stop(existing[11].origin, 11, "pickup"),
        Stop(existing[10].destination, 10, "dropoff"),
        Stop(existing[11].destination, 11, "dropoff"),
    ]
    new_order = Order(99, origin=6, destination=18, release_time=0, demand=1, max_pickup_delay=10_000, detour_ratio=100)

    cubic = cubic_insert(v, new_order, matrix, alpha=1, beta=100)
    quadratic = quadratic_dp_insert(v, new_order, matrix, alpha=1, beta=100)
    linear = linear_profit_bounded_insert(v, new_order, matrix, alpha=1, beta=100)

    assert cubic.feasible and quadratic.feasible and linear.feasible
    assert abs(cubic.delta_distance - quadratic.delta_distance) < 1e-9
    assert abs(cubic.delta_distance - linear.delta_distance) < 1e-9
    assert _check_full_route_feasible(v, new_order, linear.route, matrix)


def test_linear_matches_cubic_on_random_liberal_deadline_routes():
    matrix = GridMatrix.rectangular_grid(5, 5, time_per_edge=10)
    rng = random.Random(1234)
    for trial in range(40):
        # Two existing orders in a valid pickup-pickup-dropoff-dropoff order.
        nodes = rng.sample(range(matrix.n_nodes), 6)
        o0 = Order(10, nodes[0], nodes[1], 0, 1, 10_000, 100)
        o1 = Order(11, nodes[2], nodes[3], 0, 1, 10_000, 100)
        q = Order(99, nodes[4], nodes[5], 0, 1, 10_000, 100)
        v = Vehicle(vehicle_id=trial, current_node=rng.randrange(matrix.n_nodes), capacity=4, current_time=0)
        v.assigned_orders = {10: o0, 11: o1}
        v.route = [
            Stop(o0.origin, 10, "pickup"),
            Stop(o1.origin, 11, "pickup"),
            Stop(o0.destination, 10, "dropoff"),
            Stop(o1.destination, 11, "dropoff"),
        ]
        cubic = cubic_insert(v, q, matrix, alpha=1, beta=100)
        linear = linear_profit_bounded_insert(v, q, matrix, alpha=1, beta=100)
        assert cubic.feasible == linear.feasible
        if cubic.feasible:
            assert abs(cubic.delta_distance - linear.delta_distance) < 1e-9
            assert _check_full_route_feasible(v, q, linear.route, matrix)
