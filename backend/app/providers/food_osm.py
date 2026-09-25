"""Live food provider — OpenStreetMap Overpass (key-less).

Real nearby restaurants/cafes/street food for any coordinate, mapped into
the demo dataset's dict shape. Fields OSM does not carry (price class) are
marked ESTIMATED upstream, never invented as live. Any failure raises
OsmUnavailable → callers fall back to the demo dataset with DEMO labels.
"""
from __future__ import annotations

import logging
import os
from typing import Any


from .places_osm import OsmUnavailable, overpass_query
from .veg_hints import apply_veg_hint

logger = logging.getLogger("travelguard.food_osm")

QUERY = (
    '[out:json][timeout:12];'
    'nwr(around:{radius},{lat:.6f},{lon:.6f})["amenity"~"^(restaurant|fast_food|cafe|food_court)$"]["name"];'
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

    veg = tags.get("diet:vegetarian", "") in ("yes", "only")
    vegan_only = tags.get("diet:vegan", "") == "only"
    nonveg = tags.get("diet:non-vegetarian", "") in ("yes", "only") or not (veg or vegan_only)
    diet_tagged = veg or tags.get("diet:non-vegetarian", "") in ("yes", "only")

    cuisine = (tags.get("cuisine") or "restaurant").replace(";", ", ").replace("_", " ")
    stars = tags.get("stars")
    try:
        rating = float(stars) if stars else None
    except ValueError:
        rating = None

    return apply_veg_hint({
        "id": f"osm-{el.get('type', 'n')}-{el.get('id')}",
        "name": name[:120],
        "cuisine": cuisine[:80].title(),
        "vegetarian": veg,
        "non_vegetarian": nonveg,
        # OSM has no reliable price class — left None; per-person spend stays
        # an ESTIMATED figure upstream, never presented as a live price.
        "price_range": None,
        "rating": rating,
        "latitude": lat,
        "longitude": lon,
        "address": (tags.get("addr:street") or tags.get("addr:city") or "")[:160],
        "opening_status": "open" if tags.get("opening_hours") else "unknown",
        "data_source": "openstreetmap_overpass",
        "data_status": "LIVE",
    }, diet_tagged=diet_tagged)


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
        raise OsmUnavailable("no named food results in this area")
    return out
