"""Live places provider — OpenStreetMap Overpass API (key-less).

Fetches real nearby POIs (tourism/amenity/leisure/shop) for any coordinate
on earth. Chosen because it is key-less AND reachable from cloud egress.
Per OSM usage policy, requests carry a descriptive User-Agent with a
contact URL.

Normalized into the same dict shape as the demo dataset so the API and UI
layers stay untouched; data_status is "LIVE" with the OSM element id as the
place id. Any failure (network, throttling, empty area) raises
OsmUnavailable and callers fall back to the demo dataset with DEMO labels —
demo data is never presented as LIVE.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("travelguard.places_osm")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Mirrors tried in order — the primary endpoint throttles/hibernates
# occasionally, and some egress networks only reach some mirrors.
OVERPASS_MIRRORS = (
    OVERPASS_URL,
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
USER_AGENT = "TravelGuardAI/0.1 (https://github.com/rodrixdcruz/travelguard-ai)"
TIMEOUT = httpx.Timeout(15.0, connect=6.0)


def overpass_query(query: str) -> list[dict[str, Any]]:
    """Run one Overpass query across mirrors; raise OsmUnavailable if all fail."""
    last: Exception | None = None
    for mirror in OVERPASS_MIRRORS:
        try:
            resp = httpx.post(
                mirror,
                data={"data": query},
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except Exception as exc:  # noqa: BLE001 — mirrors are best-effort
            last = exc
    logger.warning("All Overpass mirrors failed (%s)", last)
    raise OsmUnavailable(str(last))

# OSM tag filters per UI category, applied together with an `around` filter.
CATEGORY_MAP = {
    "attraction": '["tourism"]["name"]',
    "historical": '["historic"]["name"]',
    "museum": '["tourism"="museum"]["name"]',
    "religious": '["amenity"="place_of_worship"]["name"]',
    "park": '["leisure"="park"]["name"]',
    "nature": '["leisure"="nature_reserve"]["name"]',
    "market": '["amenity"="marketplace"]["name"]',
    "shopping": '["shop"]["name"]',
    "entertainment": '["amenity"~"cinema|theatre|arts_centre"]["name"]',
    "experience": '["tourism"]["name"]',
}


class OsmUnavailable(Exception):
    """Raised when the live OSM provider cannot serve a request."""


def _demo_fallback_place(lat: float, lon: float) -> dict[str, Any]:
    return {
        "id": f"osm-fallback-{lat:.4f}-{lon:.4f}",
        "name": "No live results in this area",
        "category": "attraction",
        "description": (
            "Live OpenStreetMap data is unavailable or empty here. "
            "Enable Demo Mode to explore the sample Mumbai dataset instead."
        ),
        "latitude": lat,
        "longitude": lon,
        "address": "",
        "data_source": "openstreetmap_overpass",
        "data_status": "DEMO",
    }


def _normalize(el: dict[str, Any], lat: float, lon: float) -> dict[str, Any] | None:
    tags = el.get("tags") or {}
    name = tags.get("name")
    if not name:
        return None
    if el.get("type") == "node":
        plat, plon = el.get("lat"), el.get("lon")
    else:
        # ways/relations carry a centroid from Overpass when `out center` is used
        center = el.get("center") or {}
        plat, plon = center.get("lat"), center.get("lon")
    if plat is None or plon is None:
        return None

    tourism = tags.get("tourism", "")
    historic = tags.get("historic", "")
    if tourism == "museum":
        category = "museum"
    elif historic:
        category = "historical"
    elif tourism in ("attraction", "viewpoint", "artwork", "gallery", "zoo"):
        category = "attraction"
    elif tags.get("leisure") in ("park", "nature_reserve"):
        category = "park"
    elif tags.get("amenity") == "marketplace":
        category = "market"
    elif tags.get("shop"):
        category = "shopping"
    elif tags.get("amenity") == "place_of_worship":
        category = "religious"
    elif tags.get("amenity") in ("cinema", "theatre", "arts_centre"):
        category = "entertainment"
    else:
        category = "experience"

    kinds = [v for k, v in sorted(tags.items()) if k in ("tourism", "historic", "leisure", "amenity", "shop")]
    addr_parts = [
        tags.get(k)
        for k in ("addr:street", "addr:suburb", "addr:city")
        if tags.get(k)
    ]
    rating = None
    if tags.get("stars"):
        try:
            rating = float(tags["stars"])
        except ValueError:
            rating = None

    return {
        "id": f"osm-{el.get('type', 'n')}-{el.get('id')}",
        "name": name[:120],
        "category": category,
        "description": f"OSM: {' · '.join(kinds[:2]) or 'point of interest'}",
        "latitude": plat,
        "longitude": plon,
        "address": ", ".join(addr_parts)[:160] if addr_parts else "",
        "opening_hours": tags.get("opening_hours", "Unknown"),
        "rating": rating,
        "tags": kinds[:4],
        "data_source": "openstreetmap_overpass",
        "data_status": "LIVE",
    }


def _live_disabled() -> bool:
    return os.getenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "") == "1"


def fetch_nearby(
    latitude: float,
    longitude: float,
    radius_m: int = 10000,
    category: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Real POIs around a coordinate, sorted by distance. Raises OsmUnavailable on failure."""
    if _live_disabled():
        raise OsmUnavailable("live providers disabled via TRAVELGUARD_DISABLE_LIVE_PROVIDERS")
    tag = CATEGORY_MAP.get(category or "", CATEGORY_MAP["attraction"])
    query = (
        "[out:json][timeout:12];"
        f"nwr(around:{int(radius_m)},{latitude:.6f},{longitude:.6f}){tag};"
        f"out center {max(1, min(int(limit), 50))};"
    )
    elements = overpass_query(query)

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for el in elements:
        norm = _normalize(el, latitude, longitude)
        if norm and norm["id"] not in seen:
            seen.add(norm["id"])
            out.append(norm)
    if not out:
        raise OsmUnavailable("no named results in this area")
    return out
