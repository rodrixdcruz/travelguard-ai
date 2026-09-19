"""Food provider — nearby eateries with dietary/budget/cuisine filters.

LIVE-first (OSM Overpass, key-less) with honest DEMO fallback. Per-person
spend estimates stay ESTIMATED (documented rate per price class) — never
presented as live prices.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .places import _with_distance
from .demo_mumbai import DEMO_FOOD
from .food_osm import fetch_nearby as osm_fetch_nearby
from .places_osm import OsmUnavailable

logger = logging.getLogger("travelguard.food")

BUDGET_CLASS = {"₹": 1, "₹₹": 2, "₹₹₹": 3, "₹₹₹₹": 4}

# Rough per-person spend per price class (ESTIMATED, documented as such).
PRICE_CLASS_ESTIMATE = {"₹": 150, "₹₹": 400, "₹₹₹": 900, "₹₹₹₹": 2000}

STYLE_FILTERS = {
    "local": None,          # any — Mumbai demo is inherently local
    "street food": {"₹"},
    "vegetarian": None,     # handled by the vegetarian flag
    "non-vegetarian": None,
    "cafe": None,           # handled by cuisine contains 'cafe'
    "family": None,
    "budget": {"₹", "₹₹"},
    "premium": {"₹₹₹", "₹₹₹₹"},
}


def fetch_nearby(
    latitude: float,
    longitude: float,
    radius_km: float = 8.0,
    vegetarian: Optional[bool] = None,
    budget: Optional[int] = None,
    cuisine: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 50))
    radius_km = max(0.2, min(float(radius_km), 40.0))

    # LIVE-first: real OSM eateries win when the provider answers.
    try:
        live = osm_fetch_nearby(latitude, longitude, radius_m=int(radius_km * 1000), limit=limit)
        results = [_with_distance(f, latitude, longitude) for f in live]
    except OsmUnavailable as exc:
        logger.warning("Live food unavailable (%s) — serving DEMO fallback", exc)
        results = [_with_distance(f, latitude, longitude) for f in DEMO_FOOD]
    results = [f for f in results if f["distance_km"] <= radius_km]

    if vegetarian is True:
        results = [f for f in results if f["vegetarian"]]
    if vegetarian is False:
        results = [f for f in results if f["non_vegetarian"]]

    if budget is not None:
        budget = max(0, int(budget))
        results = [
            f for f in results
            if PRICE_CLASS_ESTIMATE.get(f["price_range"], 400) <= budget
        ]

    if cuisine:
        c = cuisine.lower()
        results = [f for f in results if c in f["cuisine"].lower() or c in f["name"].lower()]

    results.sort(key=lambda f: f["distance_km"])
    return results[:limit]


def per_person_estimate(price_range: str) -> dict[str, Any]:
    """Estimated per-person spend for a price class — always labeled ESTIMATED."""
    return {
        "per_person_inr": PRICE_CLASS_ESTIMATE.get(price_range),
        "data_status": "ESTIMATED",
    }
