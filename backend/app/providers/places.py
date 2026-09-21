"""Places provider — nearby discovery with distance and category filtering.

LIVE-first with a two-tier live chain for general (category-less) discovery:
1. **Wikipedia geosearch** — places notable enough to have an encyclopedia
   article (the "famous places" users expect: forts, museums, landmarks).
   Fast, global, key-less, and immune to Overpass capacity problems.
2. **OpenStreetMap Overpass union query** — broader POI coverage when the
   wiki layer fails or adds nothing.
Category-filtered queries go straight to OSM (wiki has no category tags).
Any failure falls through to the Mumbai demo dataset, whose items keep
their honest data_status="DEMO" — never silent demo-as-live.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Optional

from .demo_mumbai import DEMO_PLACES
from .places_osm import OsmUnavailable, fetch_nearby as osm_fetch_nearby
from .places_wiki import WikiUnavailable, fetch_notable as wiki_fetch_notable

logger = logging.getLogger("travelguard.places")

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

    # LIVE-first, two tiers: notable places (Wikipedia) then broad POIs (OSM).
    if not category:
        try:
            wiki = wiki_fetch_notable(
                latitude,
                longitude,
                radius_m=int(radius_km * 1000),
                limit=limit,
            )
            if wiki:
                results = [_with_distance(p, latitude, longitude) for p in wiki]
                results.sort(key=lambda p: p["distance_km"])
                return results[:limit]
        except WikiUnavailable as exc:
            logger.warning("Wikipedia places unavailable (%s) — trying OSM", exc)

    try:
        live = osm_fetch_nearby(
            latitude,
            longitude,
            radius_m=int(radius_km * 1000),
            category=category,
            limit=limit,
        )
        results = [_with_distance(p, latitude, longitude) for p in live]
        results.sort(key=lambda p: p["distance_km"])
        return results[:limit]
    except OsmUnavailable as exc:
        logger.warning("Live places unavailable (%s) — serving DEMO fallback", exc)

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
    # Live OSM ids are not cached server-side; detail lookups are served from
    # the demo dataset only. Returning None (→ API 404) keeps labels honest.
    for p in DEMO_PLACES:
        if p["id"] == place_id:
            out = dict(p)
            out["distance_km"] = None  # no user origin in a detail lookup
            return out
    return None


def all_places() -> list[dict[str, Any]]:
    return [dict(p) for p in DEMO_PLACES]
