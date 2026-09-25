"""Local services provider — hospitals, police, pharmacies, ATMs, transport.

LIVE-first (OSM Overpass, key-less) with honest DEMO fallback. Phone
numbers are never fabricated: live records carry the OSM-published number
when present, demo records carry phone=None and the API omits the field,
letting the UI show "Emergency number unavailable in current data."
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .places import _with_distance, haversine_km
from .demo_mumbai import DEMO_SERVICES
from .services_osm import fetch_nearby as osm_fetch_nearby
from .geoapify_places import (
    GeoapifyUnavailable,
    TRANSPORT_CATEGORY_GROUPS as TRANSPORT_GROUPS_ALL,
    fetch_services as geoapify_fetch_services,
    fetch_transport as geoapify_fetch_transport,
)
from .places_osm import OsmUnavailable

logger = logging.getLogger("travelguard.services")

SERVICE_TYPES = {
    "hospital", "pharmacy", "police", "ambulance", "fire", "tourist_help",
    "atm", "fuel", "supermarket", "transport", "taxi",
    "bus_stand", "railway_station", "metro_station", "auto_stand",
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

    # LIVE-first, three tiers: keyed Geoapify (datacenter-friendly OSM data —
    # includes metro/train/bus stops), then key-less Overpass (+ its Nominatim
    # fallback), then the labeled demo dataset. Honest empty stays empty.
    try:
        live = geoapify_fetch_services(latitude, longitude, radius_m=int(radius_km * 1000), limit=limit)
        results = [_with_distance(s, latitude, longitude) for s in live]
    except GeoapifyUnavailable as exc:
        logger.info("Geoapify services unavailable (%s) — trying Overpass", exc)
        try:
            live = osm_fetch_nearby(latitude, longitude, radius_m=int(radius_km * 1000), limit=limit)
            results = [_with_distance(s, latitude, longitude) for s in live]
        except OsmUnavailable as exc2:
            logger.warning("Live services unavailable (%s) — serving DEMO fallback", exc2)
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


# ── Full transport discovery ─────────────────────────────────────────────


# OSM fallback rows → the transport subtype vocabulary (taxis are NOT transit;
# they stay on the services path). bus_stand collapses to bus_stop — the
# key-less OSM tier cannot distinguish a terminal from a stop.
_OSM_TRANSPORT_TYPES = {
    "bus_stand": "bus_stop",
    "railway_station": "railway_station",
    "metro_station": "metro_station",
    "transport": "transit",
}


def fetch_transport_nearby(
    latitude: float,
    longitude: float,
    radius_km: float = 5.0,
    bbox: Optional[str] = None,
    limit: int = 400,
) -> dict[str, Any]:
    """ALL transit stops/stations in the area — keyed tier first, then OSM.

    ``bbox`` ("lat1,lon1,lat2,lon2") searches the visible map rectangle
    instead of a circle (full-city / visible-area discovery); the point stays
    as the proximity bias and distance origin.

    Geoapify: one paginated query per transport category (bus/platform/
    subway/entrance/train/tram/…), merged and deduped by provider id, so no
    mode crowds out another and the result is everything the provider knows
    for the area — not a nearest-first sample. Honest empty stays empty.
    Only when EVERY Geoapify group fails does the key-less Overpass tier
    serve (its fewer subtypes are mapped honestly, e.g. bus_terminal is not
    distinguishable there → bus_stop). Distinct stops are never merged.
    """
    radius_km = max(0.2, min(float(radius_km), 50.0))
    limit = max(1, min(int(limit), 2000))
    try:
        data = geoapify_fetch_transport(
            latitude, longitude, radius_m=int(radius_km * 1000),
            bbox=bbox, limit=limit,
        )
        if data["stops"] or len(data["failed_groups"]) < len(TRANSPORT_GROUPS_ALL):
            # Served (or honestly empty) — report as-is. failed_groups tells
            # the caller which category queries did not contribute.
            return data
        logger.warning("Geoapify transport empty with ALL groups failed — trying Overpass")
    except GeoapifyUnavailable as exc:
        logger.info("Geoapify transport unavailable (%s) — trying Overpass", exc)

    try:
        osm_rows = osm_fetch_nearby(latitude, longitude, radius_m=int(radius_km * 1000), limit=limit)
    except OsmUnavailable as exc:
        # Both live tiers down/empty → honest empty; the UI explains that no
        # matching stations were found rather than inventing any.
        logger.warning("OSM transport fallback unavailable (%s) — serving honest empty", exc)
        return {
            "stops": [],
            "failed_groups": list(TRANSPORT_GROUPS_ALL),
            "area_filter": "circle",
        }
    transit = [
        {**row,
         "transport_type": _OSM_TRANSPORT_TYPES.get(row["service_type"], "transit"),
         "distance_km": round(haversine_km(latitude, longitude, row["latitude"], row["longitude"]), 3)}
        for row in osm_rows
        if row["service_type"] in _OSM_TRANSPORT_TYPES
    ]
    transit.sort(key=lambda r: r["distance_km"])
    return {
        "stops": transit[:limit],
        "failed_groups": list(TRANSPORT_GROUPS_ALL),
        "area_filter": "circle",
    }
