"""Live local-services provider — OpenStreetMap Overpass (key-less).

Real hospitals, police stations, pharmacies, ATMs, fuel stations etc. for
any coordinate. This is the SAFETY-relevant category: live data here is the
whole point of the discovery layer. Failures raise OsmUnavailable → callers
fall back to the demo dataset with DEMO labels (never presented as live).
"""
from __future__ import annotations

import logging
import os
from typing import Any


from .places_osm import OsmUnavailable, overpass_query

logger = logging.getLogger("travelguard.services_osm")

# OSM amenity → TravelGuard service_type
AMENITY_MAP = {
    "hospital": "hospital",
    "clinic": "hospital",
    "doctors": "hospital",
    "pharmacy": "pharmacy",
    "police": "police",
    "fire_station": "fire",
    "atm": "atm",
    "bank": "atm",
    "fuel": "fuel",
    "bus_station": "transport",
    "taxi": "taxi",
}

QUERY = (
    "[out:json][timeout:12];"
    "nwr(around:{radius},{lat:.6f},{lon:.6f})[\"amenity\"~\"^(hospital|clinic|doctors|pharmacy|police|fire_station|atm|bank|fuel|bus_station|taxi)$\"][\"name\"];"
    "out center {limit};"
)


def _normalize(el: dict[str, Any]) -> dict[str, Any] | None:
    tags = el.get("tags") or {}
    name = tags.get("name")
    if not name:
        return None
    if el.get("type") == "node":
        lat, lon = el.get("lat"), el.get("lon")
    else:
        center = el.get("center") or {}
        lat, lon = center.get("lat"), center.get("lon")
    if lat is None or lon is None:
        return None

    service_type = AMENITY_MAP.get(tags.get("amenity", ""), "transport")
    phone = tags.get("phone") or tags.get("contact:phone") or tags.get("emergency:phone")

    return {
        "id": f"osm-{el.get('type', 'n')}-{el.get('id')}",
        "name": name[:120],
        "service_type": service_type,
        "latitude": lat,
        "longitude": lon,
        "address": (tags.get("addr:street") or tags.get("addr:city") or "")[:160],
        # Real, OSM-published number when present; None stays None — the UI's
        # "unavailable in current data" path is preserved. Never fabricated.
        "phone": phone[:24] if phone else None,
        "opening_status": "open" if tags.get("opening_hours") else "unknown",
        "data_source": "openstreetmap_overpass",
        "data_status": "LIVE",
    }


def _live_disabled() -> bool:
    return os.getenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "") == "1"


def fetch_nearby(latitude: float, longitude: float, radius_m: int = 8000, limit: int = 20) -> list[dict[str, Any]]:
    if _live_disabled():
        raise OsmUnavailable("live providers disabled via TRAVELGUARD_DISABLE_LIVE_PROVIDERS")
    query = QUERY.format(radius=int(radius_m), lat=latitude, lon=longitude, limit=max(1, min(int(limit), 50)))
    elements = overpass_query(query)

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for el in elements:
        norm = _normalize(el)
        if norm and norm["id"] not in seen:
            seen.add(norm["id"])
            out.append(norm)
    if not out:
        raise OsmUnavailable("no named service results in this area")
    return out
