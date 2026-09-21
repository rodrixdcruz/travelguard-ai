"""Live local-services provider — OpenStreetMap Overpass (key-less).

Real hospitals, police stations, pharmacies, ATMs, fuel stations etc. for
any coordinate. This is the SAFETY-relevant category: live data here is the
whole point of the discovery layer. Failures raise OsmUnavailable → callers
fall back to the demo dataset with DEMO labels (never presented as live).
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
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
    "bus_station": "bus_stand",
    "bus_stop": "bus_stand",
    "taxi": "taxi",
}

QUERY = (
    "[out:json][timeout:12];"
    "nwr(around:{radius},{lat:.6f},{lon:.6f})[\"amenity\"~\"^(hospital|clinic|doctors|pharmacy|police|fire_station|atm|bank|fuel|bus_station|bus_stop|taxi)$\"][\"name\"];"
    "(nwr(around:{radius},{lat:.6f},{lon:.6f})[\"railway\"~\"^(station|halt)$\"][\"name\"];"
    "nwr(around:{radius},{lat:.6f},{lon:.6f})[\"station\"~\"^(subway|light_rail)$\"][\"name\"];"
    "nwr(around:{radius},{lat:.6f},{lon:.6f})[\"highway\"=\"bus_stop\"][\"name\"];)"
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

    # Tag-precedence classification: railway/station/highway elements carry
    # no `amenity` key, so classify by the most specific tag present.
    if tags.get("railway") in ("station", "halt"):
        service_type = "railway_station"
    elif tags.get("station") in ("subway", "light_rail"):
        service_type = "metro_station"
    elif tags.get("highway") == "bus_stop":
        service_type = "bus_stand"
    else:
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


# ── Nominatim fallback tier ─────────────────────────────────────────────
# Render's shared egress IPs get throttled by Overpass (same pattern as
# Open-Meteo) while Nominatim keeps answering — same OSM data, different
# infrastructure. A bounded-viewbox phrase search ("[railway=station]")
# returns the same POI classes; the query's type field maps 1:1 to
# service_type. Results are LIVE with data_source=openstreetmap_nominatim.

_NOMINATIM_QUERIES = (
    ("[amenity=hospital]", "hospital"),
    ("[amenity=police]", "police"),
    ("[amenity=pharmacy]", "pharmacy"),
    ("[amenity=atm]", "atm"),
    ("[amenity=fuel]", "fuel"),
    ("[amenity=bus_station]", "bus_stand"),
    ("[amenity=taxi]", "taxi"),
    ("[railway=station]", "railway_station"),
    ("[station=subway]", "metro_station"),
)


def _viewbox(latitude: float, longitude: float, radius_m: int) -> str:
    """lat,lon → Nominatim viewbox string (left,top,right,bottom degrees)."""
    import math

    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(0.2, math.cos(math.radians(latitude))))
    return f"{longitude - dlon:.4f},{latitude + dlat:.4f},{longitude + dlon:.4f},{latitude - dlat:.4f}"


def fetch_via_nominatim(
    latitude: float, longitude: float, radius_m: int = 8000, limit: int = 20,
) -> list[dict[str, Any]]:
    """Service POIs via Nominatim bounded phrase search (LIVE fallback tier).

    Raises OsmUnavailable when Nominatim answers nothing usable — callers
    then fall back to the demo dataset. Phrase queries use brackets so only
    POI-class objects match ("[railway=station]", not the word "station").
    Phrase calls run in a small pool to bound the worst case (~2 rounds).
    """
    if _live_disabled():
        raise OsmUnavailable("live providers disabled via TRAVELGUARD_DISABLE_LIVE_PROVIDERS")
    vb = _viewbox(latitude, longitude, int(radius_m))
    per_query_limit = str(max(2, int(limit) // len(_NOMINATIM_QUERIES)))

    def _phrase(pair: tuple[str, str]) -> list[dict[str, Any]]:
        phrase, service_type = pair
        try:
            resp = httpx.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": phrase,
                    "viewbox": vb,
                    "bounded": "1",
                    "format": "jsonv2",
                    "limit": per_query_limit,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=httpx.Timeout(8.0, connect=4.0),
            )
            resp.raise_for_status()
            rows = resp.json()
        except Exception:
            return []
        rows_out: list[dict[str, Any]] = []
        for r in rows:
            try:
                rlat, rlon = float(r["lat"]), float(r["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            name = str(r.get("name") or "").strip()
            if not name:
                continue
            rows_out.append({
                "id": f"nom-{service_type}-{r.get('osm_id', len(rows_out))}",
                "name": name[:120],
                "service_type": service_type,
                "latitude": rlat,
                "longitude": rlon,
                "address": str(r.get("display_name", ""))[:160],
                "phone": None,  # Nominatim search rows carry no phone — never fabricated
                "opening_status": "unknown",
                "data_source": "openstreetmap_nominatim",
                "data_status": "LIVE",
            })
        return rows_out

    with ThreadPoolExecutor(max_workers=4) as pool:
        batches = list(pool.map(_phrase, _NOMINATIM_QUERIES))
    out = [row for batch in batches for row in batch]
    if not out:
        raise OsmUnavailable("nominatim service search returned nothing usable")
    return out


def fetch_nearby(latitude: float, longitude: float, radius_m: int = 8000, limit: int = 20) -> list[dict[str, Any]]:
    if _live_disabled():
        raise OsmUnavailable("live providers disabled via TRAVELGUARD_DISABLE_LIVE_PROVIDERS")
    query = QUERY.format(radius=int(radius_m), lat=latitude, lon=longitude, limit=max(1, min(int(limit), 50)))
    try:
        elements = overpass_query(query)
    except OsmUnavailable:
        # Overpass throttled/unavailable → same OSM data via Nominatim,
        # covering every service class (safety POIs included).
        return fetch_via_nominatim(latitude, longitude, radius_m=radius_m, limit=limit)

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
