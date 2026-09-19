"""Places provider — nearby discovery with distance and category filtering.

Currently backed by the deterministic Mumbai demo dataset. A live provider
(e.g. OSM Overpass / Google Places) can replace `fetch_nearby` internals
without touching the API or UI layers; the normalized shape stays identical.
"""
from __future__ import annotations

import math
from typing import Any, Optional

from .demo_mumbai import DEMO_PLACES

CATEGORY_ALIASES = {
    "attraction": {"attraction", "historical", "museum", "culture", "religious", "photography", "experience"},
    "historical": {"historical"},
    "museum": {"museum"},
    "culture": {"culture", "religious"},
    "religious": {"religious"},
    "market": {"market", "shopping"},
    "park": {"park", "nature"},
    "nature": {"nature", "park"},
    "shopping": {"shopping", "market"},
    "entertainment": {"entertainment", "experience"},
    "photography": {"photography"},
    "experience": {"experience", "nature", "photography"},
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _with_distance(place: dict[str, Any], lat: float, lon: float) -> dict[str, Any]:
    out = dict(place)
    out["distance_km"] = round(haversine_km(lat, lon, place["latitude"], place["longitude"]), 2)
    return out


def fetch_nearby(
    latitude: float,
    longitude: float,
    radius_km: float = 10.0,
    category: Optional[str] = None,
    interest: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Normalized Place dicts, nearest first, with the requested filters applied."""
    limit = max(1, min(int(limit), 50))
    radius_km = max(0.2, min(float(radius_km), 60.0))

    results = [_with_distance(p, latitude, longitude) for p in DEMO_PLACES]
    results = [p for p in results if p["distance_km"] <= radius_km]

    if category:
        wanted = CATEGORY_ALIASES.get(category.lower(), {category.lower()})
        results = [p for p in results if p["category"] in wanted]

    if interest:
        tag = interest.lower()
        results = [p for p in results if tag in [t.lower() for t in p["tags"]]]

    results.sort(key=lambda p: p["distance_km"])
    return results[:limit]


def fetch_by_id(place_id: str) -> Optional[dict[str, Any]]:
    for p in DEMO_PLACES:
        if p["id"] == place_id:
            out = dict(p)
            out["distance_km"] = None  # no user origin in a detail lookup
            return out
    return None


def all_places() -> list[dict[str, Any]]:
    return [dict(p) for p in DEMO_PLACES]
