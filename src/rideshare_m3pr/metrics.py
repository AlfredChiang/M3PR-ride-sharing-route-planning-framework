"""Lightweight reporting utilities."""
from __future__ import annotations

import pandas as pd

from .planner import PlanningStats


def stats_to_frame(name: str, stats: PlanningStats) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "name": name,
                "served_orders": stats.served_orders,
                "rejected_orders": stats.rejected_orders,
                "response_rate": stats.response_rate,
                "p_sub": stats.p_sub,
                "unserved_loss": stats.unserved_loss,
                "routing_cost": stats.routing_cost,
                "completed_distance": stats.completed_distance,
                "remaining_distance": stats.remaining_distance,
                "avg_insertion_time_ms": stats.avg_insertion_time_ms,
                "avg_candidate_count": stats.avg_candidate_count,
            }
        ]
    )
