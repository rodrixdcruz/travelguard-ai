"""Local services provider — hospitals, police, pharmacies, ATMs, transport.

Demo-backed. Phone numbers are never fabricated: demo records carry
phone=None and the API omits the field, letting the UI show
"Emergency number unavailable in current data."
"""
from __future__ import annotations

from typing import Any, Optional

from .places import _with_distance
from .demo_mumbai import DEMO_SERVICES

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
