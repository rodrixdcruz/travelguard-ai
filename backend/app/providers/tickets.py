"""Ticket & cost intelligence.

Combines place entry fees (DEMO dataset values) with transport estimates
(ESTIMATED) and food estimates (ESTIMATED) into a total trip cost — every
component carries its own data_status so the UI can never present a derived
total as a live fact.
"""
from __future__ import annotations

from typing import Any

from .food import PRICE_CLASS_ESTIMATE
from .transport import estimate as transport_estimate
from .transport import vehicles_for

FOOD_PER_MEAL_STATUS = "ESTIMATED"


def attraction_costs(place: dict[str, Any], origin: tuple[float, float], travelers: int = 1) -> dict[str, Any]:
    """Entry + transport for one attraction visit, honestly labeled."""
    travelers = max(1, int(travelers))
    vehicles = vehicles_for(travelers)
    entry_fee = int(place.get("entry_fee", 0) or 0)
    ticket_required = place.get("ticket_required")
    transport = transport_estimate(origin, (place["latitude"], place["longitude"]), mode="taxi")
    party_fare = round(transport["estimated_fare_inr"] * vehicles)

    return {
        "place_id": place.get("id"),
        "name": place.get("name"),
        "entry_fee_per_person": entry_fee,
        "entry_fee_data_status": "DEMO",
        "ticket_required": ticket_required,
        "opening_status": place.get("opening_status", "unknown"),
        "estimated_visit_minutes": place.get("estimated_visit_minutes", 60),
        "transport": {**transport, "estimated_fare_inr": party_fare, "vehicles": vehicles},
        "total_estimate_inr": round(entry_fee * travelers + party_fare),
        "travelers": travelers,
    }


def meal_costs(price_range: str, travelers: int = 1) -> dict[str, Any]:
    per_person = PRICE_CLASS_ESTIMATE.get(price_range, 400)
    return {
        "price_range": price_range,
        "per_person_inr": per_person,
        "total_inr": per_person * max(1, int(travelers)),
        "data_status": FOOD_PER_MEAL_STATUS,
    }
