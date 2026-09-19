"""Local services provider — hospitals, police, pharmacies, ATMs, transport.

LIVE-first (OSM Overpass, key-less) with honest DEMO fallback. Phone
numbers are never fabricated: live records carry the OSM-published number
when present, demo records carry phone=None and the API omits the field,
letting the UI show "Emergency number unavailable in current data."
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .places import _with_distance
from .demo_mumbai import DEMO_SERVICES
from .services_osm import fetch_nearby as osm_fetch_nearby
from .places_osm import OsmUnavailable

logger = logging.getLogger("travelguard.services")

SERVICE_TYPES = {
    "hospital", "pharmacy", "police", "ambulance", "fire", "tourist_help",
    "atm", "fuel", "supermarket", "transport", "taxi",
}

SAFETY_RELEVANT = {"hospital", "police", "pharmacy", "ambulance", "fire"}


def fetch_nearby(
    latitude: float,
    longitude: float,
    radius_km: float = 8.0,
    service_type: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 50))
    radius_km = max(0.2, min(float(radius_km), 40.0))

    # LIVE-first: real OSM services (hospitals, police…) win when available.
    try:
        live = osm_fetch_nearby(latitude, longitude, radius_m=int(radius_km * 1000), limit=limit)
        results = [_with_distance(s, latitude, longitude) for s in live]
    except OsmUnavailable as exc:
        logger.warning("Live services unavailable (%s) — serving DEMO fallback", exc)
        results = [_with_distance(s, latitude, longitude) for s in DEMO_SERVICES]
    results = [s for s in results if s["distance_km"] <= radius_km]

    if service_type:
        st = service_type.lower()
        if st == "sos":
            results = [s for s in results if s["service_type"] in SAFETY_RELEVANT]
        else:
            results = [s for s in results if s["service_type"] == st]

    results.sort(key=lambda s: s["distance_km"])
    return results[:limit]


def nearest_by_type(latitude: float, longitude: float, service_type: str) -> Optional[dict[str, Any]]:
    items = fetch_nearby(latitude, longitude, radius_km=40.0, service_type=service_type, limit=1)
    return items[0] if items else None
