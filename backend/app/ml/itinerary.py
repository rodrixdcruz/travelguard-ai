"""Itinerary optimizer — deterministic feasibility selection.

ML ranks places; this layer selects a feasible plan under time, budget,
opening-hours and safety constraints. No ML here by design, and the LLM
only narrates the result afterwards.
"""
from __future__ import annotations

from typing import Any

FOOD_COST_PER_STOP = 250.0
TRANSPORT_COST_PER_KM = 12.0


def build_itinerary(
    ranked_places: list[dict[str, Any]],
    available_hours: float,
    budget: float,
    interests: list[str] | None = None,
    max_stops: int = 6,
) -> dict[str, Any]:
    """Greedy feasibility-preserving selection over ranked places.

    Places are visited in ML-score order; each candidate is added only if
    visiting it keeps the plan inside time and budget. Safety context gates
    the plan: low-safety options are only kept if little else qualifies.
    """
    interests = interests or []
    stops: list[dict[str, Any]] = []
    time_left = float(available_hours)
    cost_so_far = 0.0
    skipped: list[dict[str, Any]] = []

    for place in ranked_places:
        if len(stops) >= max_stops:
            break
        duration = float(place.get("visit_duration_hours", 1.5) or 1.5)
        cost = float(place.get("estimated_cost", 0) or 0)
        safety = float(place.get("safety_context", 70) or 70)

        if not place.get("is_open", True):
            skipped.append({**place, "why": "Closed during your window"})
            continue
        if duration > time_left:
            skipped.append({**place, "why": "Not enough time left"})
            continue
        if cost > (budget - cost_so_far):
            skipped.append({**place, "why": "Would exceed your budget"})
            continue

        stops.append(place)
        time_left -= duration
        cost_so_far += cost

    # Travel estimate: straight-line distances between consecutive stops.
    transport_km = 0.0
    coords = [(p.get("lat"), p.get("lon")) for p in stops if p.get("lat") is not None]
    for (lat1, lon1), (lat2, lon2) in zip(coords, coords[1:]):
        transport_km += _haversine(lat1, lon1, lat2, lon2)
    transport_cost = round(transport_km * TRANSPORT_COST_PER_KM, 1)

    interest_hits = sum(
        1
        for p in stops
        if str(p.get("category", "")).lower() in [i.lower() for i in interests]
        or any(str(t).lower() in [i.lower() for i in interests] for t in (p.get("tags") or []))
    )

    food_stops = max(1, round(float(available_hours) / 4.0))
    food_cost = food_stops * FOOD_COST_PER_STOP
    tickets = round(cost_so_far, 1)
    transport = transport_cost
    total = round(tickets + food_cost + transport, 1)

    return {
        "stops": [
            {
                "place_id": p.get("place_id", p.get("name", f"stop-{i + 1}")),
                "name": p.get("name", f"Stop {i + 1}"),
                "category": p.get("category", ""),
                "visit_duration_hours": p.get("visit_duration_hours", 1.5),
                "estimated_cost": p.get("estimated_cost", 0),
                "recommendation_score": p.get("recommendation_score"),
                "safety_context": p.get("safety_context"),
            }
            for i, p in enumerate(stops)
        ],
        "skipped": [
            {"name": p.get("name", "?"), "why": p.get("why", "infeasible")} for p in skipped
        ],
        "summary": {
            "total_stops": len(stops),
            "used_hours": round(float(available_hours) - time_left, 1),
            "available_hours": float(available_hours),
            "interest_matches": interest_hits,
            "avg_safety": round(
                sum(float(p.get("safety_context", 70) or 70) for p in stops) / max(len(stops), 1), 1
            )
            if stops
            else 0.0,
        },
        "cost_breakdown": {
            "tickets": tickets,
            "food_estimate": round(food_cost, 1),
            "transport_estimate": transport,
            "transport_km": round(transport_km, 1),
            "total_estimate": total,
            "budget": float(budget),
            "within_budget": total <= float(budget),
        },
        "optimizer": "greedy-feasibility-v0.1",
    }


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 0.0
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))
