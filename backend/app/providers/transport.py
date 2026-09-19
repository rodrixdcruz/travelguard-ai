"""Transport estimation between points.

Costs are MODELED ESTIMATES (documented rates × straight-line distance),
never live fares. Modeled rates chosen to feel plausible for Mumbai demos.
"""
from __future__ import annotations

from typing import Any

from .places import haversine_km

# Modeled rates (INR per km) + minimum fares — ESTIMATED data, not live fares.
RATES = {
    "taxi": {"per_km": 22.0, "min_fare": 60.0},
    "auto": {"per_km": 15.0, "min_fare": 30.0},
    "local_train": {"per_km": 2.5, "min_fare": 10.0},
    "bus": {"per_km": 2.0, "min_fare": 8.0},
}

def vehicles_for(travelers: int) -> int:
    """One vehicle per up to 4 travelers (taxi/auto seating)."""
    import math

    return max(1, math.ceil(max(1, int(travelers)) / 4))


# Road distance factor: streets wind, straight lines don't.
ROAD_FACTOR = 1.35
# Average city speed used for travel-time estimates (km/h) — ESTIMATED.
SPEED_KMPH = {"taxi": 20.0, "auto": 18.0, "local_train": 32.0, "bus": 14.0}


def estimate(a: tuple[float, float], b: tuple[float, float], mode: str = "taxi") -> dict[str, Any]:
    """Distance (km), duration (min) and fare (INR) between two coordinates."""
    rate = RATES.get(mode, RATES["taxi"])
    straight = haversine_km(a[0], a[1], b[0], b[1])
    road_km = round(straight * ROAD_FACTOR, 2)
    fare = max(rate["min_fare"], road_km * rate["per_km"])
    duration_min = round(road_km / SPEED_KMPH.get(mode, 20.0) * 60.0, 1)
    return {
        "mode": mode,
        "distance_km": road_km,
        "duration_min": duration_min,
        "estimated_fare_inr": round(fare, 0),
        "data_status": "ESTIMATED",
    }
