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
from .veg_hints import apply_veg_hint

logger = logging.getLogger("travelguard.geoapify_places")

PLACES_URL = "https://api.geoapify.com/v2/places"
USER_AGENT = "TravelGuardAI/0.1 (https://github.com/rodrixdcruz/travelguard-ai)"
TIMEOUT = httpx.Timeout(8.0, connect=4.0)
RESULT_TTL_SECONDS = 30 * 60  # POI turnover is slow; repeat discoveries are free

# Verified hierarchical categories (Geoapify Places docs). Only parents and
# children documented by Geoapify are requested — an unknown key could make
# the whole request fail.
CAT_FOOD = "catering"
CAT_SIGHTS = "tourism.sights,tourism.attraction,leisure,entertainment,natural"

# Services are fetched as one Places call PER KIND GROUP, then merged.
# A single combined query (all groups, one limit) is nearest-first, so
# wherever one kind is dense — a hospital district, a market street — it
# fills the whole window and pharmacies/ATMs/transit vanish from discovery
# even though they exist nearby (observed live in Nagpur). Disjoint category
# sets per group mean no cross-group duplicates; _service_kind still refines
# transit sub-kinds (metro/railway/bus) per feature. Police stations and
# tourist-information offices get their own groups too — without them the
# Safety page and SAFETY filters report "unavailable" even in well-mapped
# cities (observed live in Nagpur).
SERVICE_CATEGORY_GROUPS: tuple[str, ...] = (
    "healthcare.hospital",
    "healthcare.pharmacy",
    "service.financial",
    "commercial.supermarket",
    "service.police",
    "tourism.information",
    "public_transport",
)
SERVICE_GROUP_FETCH_LIMIT = 20  # per group; circle-bounded, nearest-first

# ── Transport discovery ───────────────────────────────────────────────────
# Every transit category is queried INDEPENDENTLY with its own pagination so a
# dense cluster of one mode (hundreds of bus stops) can never crowd another
# mode (metro/railway) out of the window, and so the result is everything the
# provider knows for the selected area — not a nearest-first sample.
# All categories verified against the live API (an unknown key fails the whole
# request). Order is irrelevant to correctness: cross-group duplicates are
# removed by provider place_id (a bus terminal legitimately appears under
# both public_transport.bus and public_transport.platform).
TRANSPORT_CATEGORY_GROUPS: tuple[str, ...] = (
    "public_transport.bus",            # bus stops & bus stations
    "public_transport.platform",       # public transport platforms
    "public_transport.subway.entrance",  # metro entrances
    "public_transport.subway",         # metro stations
    "public_transport.train",          # railway stations
    "public_transport.light_rail",
    "public_transport.tram",
    "public_transport.monorail",
)
TRANSPORT_PAGE_SIZE = 200            # features per request (provider max 500)
TRANSPORT_MAX_PER_GROUP = 500        # hard cap per category group

# Stable subtype vocabulary derived from the provider's own category + raw
# OSM tags (never invented). 'transit' = tagged public_transport but with no
# resolvable mode.
TRANSPORT_SUBTYPES = (
    "bus_stop", "bus_terminal", "metro_station", "metro_entrance",
    "railway_station", "tram", "monorail", "light_rail", "transit",
)


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
    offset: int = 0,
    bbox: Optional[str] = None,
) -> list[dict[str, Any]]:
    """One Places API call. Raises GeoapifyUnavailable on any failure.

    ``bbox`` is "lat1,lon1,lat2,lon2" (any corner order) — when given the
    query filters a rectangle (visible-map search) instead of a circle;
    proximity bias stays on the supplied center point.
    """
    if _live_disabled():
        raise GeoapifyUnavailable("live providers disabled via TRAVELGUARD_DISABLE_LIVE_PROVIDERS")
    key = _api_key()
    if not key:
        raise GeoapifyUnavailable("GEOAPIFY_API_KEY not configured")

    def _fetch() -> list[dict[str, Any]]:
        try:
            if bbox is not None:
                parts = [float(p) for p in bbox.split(",")]  # "lat1,lon1,lat2,lon2"
                lat1, lon1, lat2, lon2 = parts[0], parts[1], parts[2], parts[3]
                area_filter = (
                    f"rect:{min(lon1, lon2):.6f},{min(lat1, lat2):.6f},"
                    f"{max(lon1, lon2):.6f},{max(lat1, lat2):.6f}"
                )
            else:
                # GeoJSON order: longitude first.
                area_filter = f"circle:{longitude:.6f},{latitude:.6f},{int(radius_m)}"
            params: dict[str, Any] = {
                "categories": categories,
                "filter": area_filter,
                "bias": f"proximity:{longitude:.6f},{latitude:.6f}",
                "limit": max(1, min(int(limit), 500)),
                "apiKey": key,
            }
            if offset:
                params["offset"] = int(offset)
            resp = httpx.get(
                PLACES_URL,
                params=params,
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

    # Results are cached per (categories, ~100 m cell, radius, limit, offset)
    # so repeat discoveries and day-plan meal lookups don't burn free credits.
    return cached(
        ("geoapify", categories, round(latitude, 3), round(longitude, 3),
         int(radius_m) if bbox is None else str(bbox), int(limit), int(offset)),
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
        # Raw OSM tags are the only diet/price signal Geoapify exposes here.
        # They are used when mapped and left honest (False/None) when not —
        # without this, live rows always read vegetarian=False and the VEG
        # filter emptied out entire live datasets (observed live in Nagpur).
        raw = props.get("raw") or {}
        veg_tag = str(raw.get("diet:vegetarian", "")).lower()
        vegan_only = str(raw.get("diet:vegan", "")).lower() == "only"
        veg = veg_tag in ("yes", "only") or vegan_only
        nonveg = (str(raw.get("diet:non-vegetarian", "")).lower() in ("yes", "only")
                  or not veg)
        diet_tagged = veg or str(raw.get("diet:non-vegetarian", "")).lower() in ("yes", "only")
        price = raw.get("charge") or raw.get("price") or None
        row = {
            {
                "id": f"geoapify-{str(props.get('place_id', name[:24]))[:32]}",
                "name": name[:120],
                "cuisine": cuisine[:80],
                "vegetarian": veg,
                "non_vegetarian": nonveg,
                "price_range": str(price) if price else None,  # never invented; per-person spend stays ESTIMATED upstream
                "rating": None,
                "latitude": lat,
                "longitude": lon,
                "address": str(props.get("address_line2") or props.get("formatted") or "")[:160],
                "opening_status": "unknown",
                "data_source": "geoapify_places",
                "data_status": "LIVE",
            }
        # Conservative name-based hint when no real diet tags were mapped
        # (a separate ``veg_hint`` field — never merged into ``vegetarian``).
        out.append(apply_veg_hint(row, diet_tagged=diet_tagged))
    return out


def _service_kind(cats: list[str]) -> Optional[str]:
    """Geoapify categories → TravelGuard service_type; None = not a service we label.

    Geoapify lists parent and child categories together (e.g. both
    "public_transport" and "public_transport.subway"), in no guaranteed
    order — so specificity beats first-match: all strings are classified,
    then the most specific kind wins (metro_station over transport).
    """
    kinds: set[str] = set()
    for c in cats:
        if c.startswith("healthcare.pharmacy"):
            kinds.add("pharmacy")
        elif c.startswith("healthcare"):
            kinds.add("hospital")
        elif c.startswith("service.police"):
            kinds.add("police")
        elif c.startswith("service.financial"):
            kinds.add("atm")
        elif c.startswith("tourism.information"):
            kinds.add("tourist_help")
        elif c.startswith("public_transport.subway"):
            kinds.add("metro_station")
        elif c.startswith("public_transport.train"):
            kinds.add("railway_station")
        elif c.startswith("public_transport.bus"):
            kinds.add("bus_stand")
        elif c.startswith("public_transport"):
            kinds.add("transport")
        elif c.startswith("commercial.supermarket"):
            kinds.add("supermarket")
    for k in (
        "pharmacy", "hospital", "atm", "police", "tourist_help",
        "metro_station", "railway_station", "bus_stand", "supermarket",
        "transport",
    ):
        if k in kinds:
            return k
    return None


def _approx_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km — enough to order merged multi-group results."""
    import math

    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def fetch_services(latitude: float, longitude: float, radius_m: int = 8000, limit: int = 25) -> list[dict[str, Any]]:
    """Hospitals, pharmacies, ATMs, supermarkets and transit stops (LIVE).

    One Places query per service kind group (see SERVICE_CATEGORY_GROUPS) so
    a dense cluster of one kind cannot crowd the others out of the result
    window; groups are merged nearest-first and deduped. Costs one credit
    per group call — cached ~30 min via the shared discovery cache.
    """
    limit = max(1, min(int(limit), 50))
    per_group = min(limit, SERVICE_GROUP_FETCH_LIMIT)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for categories in SERVICE_CATEGORY_GROUPS:
        for f in _search(categories, latitude, longitude, radius_m, per_group):
            props = f.get("properties") or {}
            name = str(props.get("name") or "").strip()
            coords = _feature_coords(f)
            if not name or coords is None:
                continue
            cats = [str(c) for c in (props.get("categories") or [])]
            service_type = _service_kind(cats)
            if service_type is None:
                continue
            place_id = f"geoapify-{str(props.get('place_id', name[:24]))[:32]}"
            if place_id in seen:
                continue
            seen.add(place_id)
            lat, lon = coords
            out.append(
                {
                    "id": place_id,
                    "name": name[:120],
                    "service_type": service_type,
                    "latitude": lat,
                    "longitude": lon,
                    "address": str(props.get("address_line2") or props.get("formatted") or "")[:160],
                    "phone": None,  # Places rows carry no phone — never fabricated
                    "opening_status": "unknown",
                    "data_source": "geoapify_places",
                    "data_status": "LIVE",
                    "_distance_km": _approx_distance_km(latitude, longitude, lat, lon),
                }
            )
    # Merged nearest-first; the internal sort key is stripped so callers
    # (which re-add their own distance fields) see the plain service shape.
    out.sort(key=lambda s: s.pop("_distance_km"))
    return out


# ── Transport discovery ───────────────────────────────────────────────────


def _transport_subtype(cats: list[str], raw: dict[str, Any]) -> str:
    """Subtype from the provider's own category metadata + raw OSM tags.

    Uses only data Geoapify actually returns (its ``categories`` list and the
    ``raw`` OSM tag block) — station types are never invented. Specificity
    beats order: all category strings are classified, then the most specific
    subtype wins.
    """
    subtypes: set[str] = set()
    for c in cats:
        if c.startswith("public_transport.subway.entrance"):
            subtypes.add("metro_entrance")
        elif c.startswith("public_transport.subway"):
            subtypes.add("metro_station")
        elif c.startswith("public_transport.train"):
            subtypes.add("railway_station")
        elif c.startswith("public_transport.bus"):
            subtypes.add("bus_stop")
        elif c.startswith("public_transport.tram"):
            subtypes.add("tram")
        elif c.startswith("public_transport.monorail"):
            subtypes.add("monorail")
        elif c.startswith("public_transport.light_rail"):
            subtypes.add("light_rail")
        elif c.startswith("public_transport.platform"):
            subtypes.add("transit")  # bare platform — mode resolved from raw tags below
        elif c.startswith("public_transport"):
            subtypes.add("transit")
    # Raw OSM tags refine the mode where Geoapify's categories are coarse —
    # e.g. a bus TERMINAL is an OSM way/area whose raw tags say so, and a
    # bare platform with highway=bus_stop is a bus stop, not unknown transit.
    pub = str(raw.get("public_transport", ""))
    if "bus_stop" in subtypes or (pub == "platform" and str(raw.get("highway", "")) == "bus_stop"):
        subtypes.discard("transit")
        subtypes.add("bus_stop")
    if str(raw.get("amenity", "")) == "bus_station" or (
        pub == "station" and "bus" in str(raw.get("bus", ""))
    ):
        subtypes.discard("bus_stop")
        subtypes.discard("transit")
        subtypes.add("bus_terminal")
    if pub == "station" and str(raw.get("station", "")) == "subway":
        subtypes.add("metro_station")
    for k in (
        "bus_terminal", "metro_station", "metro_entrance", "railway_station",
        "bus_stop", "tram", "monorail", "light_rail", "transit",
    ):
        if k in subtypes:
            return k
    return "transit"


def _feature_transport_row(
    feature: dict[str, Any],
    latitude: float,
    longitude: float,
) -> Optional[dict[str, Any]]:
    """Normalize one Geoapify feature into a transport-stop row (or None)."""
    props = feature.get("properties") or {}
    raw = props.get("raw") or {}
    name = str(props.get("name") or "").strip()
    coords = _feature_coords(feature)
    if not name or coords is None:
        return None
    cats = [str(c) for c in (props.get("categories") or [])]
    lat, lon = coords
    return {
        "id": f"geoapify-{str(props.get('place_id', name[:24]))[:64]}",
        "name": name[:120],
        "transport_type": _transport_subtype(cats, raw),
        "latitude": lat,
        "longitude": lon,
        "address": str(props.get("address_line2") or props.get("formatted") or "")[:160],
        "distance_km": round(_approx_distance_km(latitude, longitude, lat, lon), 3),
        "data_source": "geoapify_places",
        "data_status": "LIVE",
    }


def fetch_transport(
    latitude: float,
    longitude: float,
    radius_m: int = 5000,
    bbox: Optional[str] = None,
    limit: int = 400,
) -> dict[str, Any]:
    """ALL transit stops/stations in the selected area (LIVE, paginated).

    One paginated Places query per transport category group (see
    TRANSPORT_CATEGORY_GROUPS) so a dense cluster of one mode cannot crowd
    another mode out; results are deduped by provider place_id (a bus
    terminal legitimately appears under both ``.bus`` and ``.platform`` —
    those merge; distinct stops are never merged by proximity). A category
    group that fails is skipped and reported in ``failed_groups`` while the
    successful groups still serve — partial results with honest status.
    Cached per (group, area, offset) for ~30 min.
    """
    limit = max(1, min(int(limit), 5000))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    failed_groups: list[str] = []
    for categories in TRANSPORT_CATEGORY_GROUPS:
        collected = 0
        offset = 0
        while collected < TRANSPORT_MAX_PER_GROUP:
            page_size = min(TRANSPORT_PAGE_SIZE, TRANSPORT_MAX_PER_GROUP - collected)
            try:
                features = _search(
                    categories, latitude, longitude, int(radius_m),
                    page_size, offset=offset, bbox=bbox,
                )
            except GeoapifyUnavailable as exc:
                logger.warning("Geoapify transport group failed (%s): %s", categories, exc)
                failed_groups.append(categories)
                break
            out.extend(f for f in features if (_transport_key(f) not in seen))
            for f in features:
                seen.add(_transport_key(f))
            collected += len(features)
            if len(features) < page_size:  # short page → group exhausted
                break
            offset += page_size
    rows: list[dict[str, Any]] = []
    row_ids: set[str] = set()
    for f in out:
        row = _feature_transport_row(f, latitude, longitude)
        if row is not None and row["id"] not in row_ids:
            row_ids.add(row["id"])
            rows.append(row)
    rows.sort(key=lambda r: r["distance_km"])
    rows = rows[:limit]
    return {"stops": rows, "failed_groups": failed_groups, "area_filter": "bbox" if bbox else "circle"}


def _transport_key(feature: dict[str, Any]) -> str:
    props = feature.get("properties") or {}
    return str(props.get("place_id") or f"{feature.get('geometry', {}).get('coordinates')}" )
