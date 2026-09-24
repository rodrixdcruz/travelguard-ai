"""Keyed live provider — Geoapify Places API (OSM data, datacenter-friendly).

Render's shared egress IPs get throttled by Overpass and often by Nominatim,
so every key-less live tier degrades there. Geoapify serves the SAME
OpenStreetMap data from its own infrastructure and accepts cloud-provider
traffic — with a free GEOAPIFY_API_KEY (3,000 credits/day) discovery works
from Render for food, services (incl. metro/railway/bus stops) and leisure
POIs (lakes, zoos, parks, theme/water parks).

Used as the FIRST tier of the food/services chains and as a fusion source
for category-less place discovery. Any failure (no key, disabled by the CI
kill switch, network/API error) raises GeoapifyUnavailable → callers fall
through to the key-less OSM tiers and the demo dataset. A successful call
that legitimately finds nothing returns [] — callers report that honestly
(no fallback masking). Results carry data_status="LIVE" with the source
named; fields the API does not return are never fabricated.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

from .nominatim_cache import cached

logger = logging.getLogger("travelguard.geoapify_places")

PLACES_URL = "https://api.geoapify.com/v2/places"
USER_AGENT = "TravelGuardAI/0.1 (https://github.com/rodrixdcruz/travelguard-ai)"
TIMEOUT = httpx.Timeout(8.0, connect=4.0)
RESULT_TTL_SECONDS = 30 * 60  # POI turnover is slow; repeat discoveries are free

# Verified hierarchical categories (Geoapify Places docs). Only parents and
# children documented by Geoapify are requested — an unknown key could make
# the whole request fail.
CAT_FOOD = "catering"
CAT_SERVICES = (
    "healthcare.hospital,healthcare.pharmacy,service.financial,"
    "commercial.supermarket,public_transport"
)
CAT_SIGHTS = "tourism.sights,tourism.attraction,leisure,entertainment,natural"


class GeoapifyUnavailable(Exception):
    """Raised when the Geoapify provider cannot serve a request."""


def _api_key() -> str:
    return os.getenv("GEOAPIFY_API_KEY", "").strip()


def _live_disabled() -> bool:
    return os.getenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "") == "1"


def _title_category(title: str) -> str:
    """Discovery category from a place name (same vocabulary as the wiki tier)."""
    lowered = title.lower()
    for keyword, category in (
        ("zoo", "zoo"),
        ("lake", "lake"),
        ("garden", "garden"),
        ("national park", "park"),
        ("water park", "park"),
        ("sanctuary", "park"),
        ("reserve", "nature"),
        ("museum", "museum"),
        ("fort", "historical"),
        ("palace", "historical"),
        ("stadium", "attraction"),
        ("park", "park"),
    ):
        if keyword in lowered:
            return category
    return "attraction"


def _category_from_geo(cats: list[str]) -> str:
    for c in cats:
        if "zoo" in c:
            return "zoo"
        if "water_park" in c:
            return "park"
        if c.startswith("leisure.park"):
            return "park"
        if c.startswith("leisure.garden"):
            return "garden"
        if c.startswith("natural"):
            return "lake" if any(x in c for x in ("water", "pond", "wetland")) else "nature"
        if c.startswith("entertainment.museum"):
            return "museum"
        if c.startswith("tourism") or c.startswith("entertainment") or c.startswith("sport"):
            return "attraction"
        if c.startswith("leisure"):
            return "park"
    return "attraction"


def _search(
    categories: str,
    latitude: float,
    longitude: float,
    radius_m: int,
    limit: int,
) -> list[dict[str, Any]]:
    """One Places API call. Raises GeoapifyUnavailable on any failure."""
    if _live_disabled():
        raise GeoapifyUnavailable("live providers disabled via TRAVELGUARD_DISABLE_LIVE_PROVIDERS")
    key = _api_key()
    if not key:
        raise GeoapifyUnavailable("GEOAPIFY_API_KEY not configured")

    def _fetch() -> list[dict[str, Any]]:
        try:
            resp = httpx.get(
                PLACES_URL,
                params={
                    "categories": categories,
                    # GeoJSON order: longitude first.
                    "filter": f"circle:{longitude:.6f},{latitude:.6f},{int(radius_m)}",
                    "bias": f"proximity:{longitude:.6f},{latitude:.6f}",
                    "limit": max(1, min(int(limit), 50)),
                    "apiKey": key,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            raise GeoapifyUnavailable(f"geoapify places: {exc}") from exc
        if payload.get("error"):
            raise GeoapifyUnavailable(f"geoapify places: {payload['error']}")
        return list(payload.get("features") or [])

    # Results are cached per (categories, ~100 m cell, radius, limit) so repeat
    # discoveries and day-plan meal lookups don't burn free credits.
    return cached(
        ("geoapify", categories, round(latitude, 3), round(longitude, 3), int(radius_m), int(limit)),
        RESULT_TTL_SECONDS,
        _fetch,
    )


def _feature_coords(feature: dict[str, Any]) -> Optional[tuple[float, float]]:
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        return None
    try:
        return float(coords[1]), float(coords[0])  # (lat, lon) from GeoJSON (lon, lat)
    except (TypeError, ValueError):
        return None


# ── Public fetchers ───────────────────────────────────────────────────────


def fetch_places(latitude: float, longitude: float, radius_m: int = 10000, limit: int = 20) -> list[dict[str, Any]]:
    """Famous/leisure places (sights, parks, lakes, zoos, theme parks)."""
    features = _search(CAT_SIGHTS, latitude, longitude, radius_m, limit)
    out: list[dict[str, Any]] = []
    for f in features:
        props = f.get("properties") or {}
        name = str(props.get("name") or "").strip()
        coords = _feature_coords(f)
        if not name or coords is None:
            continue
        lat, lon = coords
        cats = [str(c) for c in (props.get("categories") or [])]
        out.append(
            {
                "id": f"geoapify-{str(props.get('place_id', name[:24]))[:32]}",
                "name": name[:120],
                "category": _title_category(name) if _title_category(name) != "attraction" else _category_from_geo(cats),
                "description": "POI on OpenStreetMap (via Geoapify)",
                "latitude": lat,
                "longitude": lon,
                "address": str(props.get("address_line2") or props.get("formatted") or "")[:160],
                "opening_hours": "Unknown",
                "rating": None,
                "tags": ["notable", "openstreetmap", "geoapify"],
                "data_source": "geoapify_places",
                "data_status": "LIVE",
            }
        )
    return out


def fetch_food(latitude: float, longitude: float, radius_m: int = 8000, limit: int = 20) -> list[dict[str, Any]]:
    """Restaurants/cafes/fast food — same dict shape as the OSM food tier."""
    features = _search(CAT_FOOD, latitude, longitude, radius_m, limit)
    out: list[dict[str, Any]] = []
    for f in features:
        props = f.get("properties") or {}
        name = str(props.get("name") or "").strip()
        coords = _feature_coords(f)
        if not name or coords is None:
            continue
        lat, lon = coords
        cats = [str(c) for c in (props.get("categories") or [])]
        cuisine = next((c.split(".")[-1].replace("_", " ").title() for c in cats if c.startswith("catering.")), "Restaurant")
        out.append(
            {
                "id": f"geoapify-{str(props.get('place_id', name[:24]))[:32]}",
                "name": name[:120],
                "cuisine": cuisine[:80],
                "vegetarian": False,  # unknown until diet tags say so — filters stay honest
                "non_vegetarian": True,
                "price_range": None,  # never invented; per-person spend stays ESTIMATED upstream
                "rating": None,
                "latitude": lat,
                "longitude": lon,
                "address": str(props.get("address_line2") or props.get("formatted") or "")[:160],
                "opening_status": "unknown",
                "data_source": "geoapify_places",
                "data_status": "LIVE",
            }
        )
    return out


def _service_kind(cats: list[str]) -> Optional[str]:
    """Geoapify categories → TravelGuard service_type; None = not a service we label."""
    for c in cats:
        if c.startswith("healthcare.pharmacy"):
            return "pharmacy"
        if c.startswith("healthcare"):
            return "hospital"
        if c.startswith("service.financial"):
            return "atm"
        if c.startswith("public_transport.subway"):
            return "metro_station"
        if c.startswith("public_transport.train"):
            return "railway_station"
        if c.startswith("public_transport.bus"):
            return "bus_stand"
        if c.startswith("public_transport"):
            return "transport"
        if c.startswith("commercial.supermarket"):
            return "supermarket"
    return None


def fetch_services(latitude: float, longitude: float, radius_m: int = 8000, limit: int = 25) -> list[dict[str, Any]]:
    """Hospitals, pharmacies, ATMs, supermarkets and transit stops (LIVE)."""
    features = _search(CAT_SERVICES, latitude, longitude, radius_m, limit)
    out: list[dict[str, Any]] = []
    for f in features:
        props = f.get("properties") or {}
        name = str(props.get("name") or "").strip()
        coords = _feature_coords(f)
        if not name or coords is None:
            continue
        cats = [str(c) for c in (props.get("categories") or [])]
        service_type = _service_kind(cats)
        if service_type is None:
            continue
        lat, lon = coords
        out.append(
            {
                "id": f"geoapify-{str(props.get('place_id', name[:24]))[:32]}",
                "name": name[:120],
                "service_type": service_type,
                "latitude": lat,
                "longitude": lon,
                "address": str(props.get("address_line2") or props.get("formatted") or "")[:160],
                "phone": None,  # Places rows carry no phone — never fabricated
                "opening_status": "unknown",
                "data_source": "geoapify_places",
                "data_status": "LIVE",
            }
        )
    return out
