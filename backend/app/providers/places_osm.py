"""Live places provider — OpenStreetMap Overpass API (key-less).

Fetches real nearby POIs (tourism/historic/leisure/amenity) for any
coordinate on earth. Chosen because it is key-less AND reachable from
cloud egress. Per OSM usage policy, requests carry a descriptive
User-Agent with a contact URL.

General discovery unions every interesting tag class (a single-tag query
misses most famous places — they are often `historic` or `leisure=park`,
not `tourism`) and ranks the pool by notability: places carrying a
wikidata/wikipedia tag come first, then strongly-tagged attractions, then
everything else. Normalized into the same dict shape as the demo dataset
so the API and UI layers stay untouched; data_status is "LIVE" with the
OSM element id as the place id. Any failure (network, throttling, empty
area) raises OsmUnavailable and callers fall back to the demo dataset
with DEMO labels — demo data is never presented as LIVE.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("travelguard.places_osm")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Mirrors tried in order — the primary endpoint throttles/hibernates
# occasionally (and on bad days 504s everything: "server too busy"), and
# some egress networks only reach some mirrors. Regional instances sit
# last: they answer fast but may lack global coverage, so they are the
# final attempt, not the first.
OVERPASS_MIRRORS = (
    OVERPASS_URL,
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
)
USER_AGENT = "TravelGuardAI/0.1 (https://github.com/rodrixdcruz/travelguard-ai)"
TIMEOUT = httpx.Timeout(8.0, connect=4.0)

# Circuit breaker: after an all-mirrors failure, skip Overpass entirely for
# a short window so a dead network costs one fast probe instead of a
# full mirror sweep on every request. Failures are timestamped per process.
BREAKER_WINDOW_SECONDS = 60.0
_last_all_fail: list[float] = []  # [monotonic ts] — empty = closed

# Result cache: successful queries are repeated constantly (meal lookups on
# every day plan, hospital proximity on every safety check) and each repeat
# re-pays the full mirror round-trip. POI data changes on OSM timescales
# (hours/days), so a 10-minute TTL is safely honest.
RESULT_TTL_SECONDS = 600.0
_RESULT_CACHE_MAX = 128
_result_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def overpass_query(query: str, timeout: httpx.Timeout | None = None) -> list[dict[str, Any]]:
    """Run one Overpass query across mirrors; raise OsmUnavailable if all fail."""
    import time as _time

    hit = _result_cache.get(query)
    if hit is not None:
        ts, elements = hit
        if _time.monotonic() - ts < RESULT_TTL_SECONDS:
            return elements
        _result_cache.pop(query, None)

    if _last_all_fail:
        age = _time.monotonic() - _last_all_fail[0]
        if age < BREAKER_WINDOW_SECONDS:
            raise OsmUnavailable(f"overpass circuit open ({BREAKER_WINDOW_SECONDS:.0f}s window, {age:.0f}s ago all mirrors failed)")
        _last_all_fail.clear()
    last: Exception | None = None
    empty_200: str | None = None  # a mirror answered 200 but with no elements
    for mirror in OVERPASS_MIRRORS:
        try:
            resp = httpx.post(
                mirror,
                data={"data": query},
                headers={"User-Agent": USER_AGENT},
                timeout=timeout or TIMEOUT,
            )
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            if not elements:
                # 200-but-empty: regional instances legitimately have no data
                # outside their area — not an authoritative "nothing here".
                # Remember it but keep trying the remaining mirrors.
                empty_200 = empty_200 or mirror
                continue
            _last_all_fail.clear()
            if len(_result_cache) >= _RESULT_CACHE_MAX:
                _result_cache.pop(min(_result_cache, key=lambda k: _result_cache[k][0]), None)
            _result_cache[query] = (_time.monotonic(), elements)
            return elements
        except Exception as exc:  # noqa: BLE001 — mirrors are best-effort
            last = exc
    if empty_200:
        # Every mirror either failed or answered empty; prefer the honest
        # empty result over a network error.
        _last_all_fail.clear()
        return []
    logger.warning("All Overpass mirrors failed (%s)", last)
    _last_all_fail[:] = [_time.monotonic()]
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

# General discovery (no category requested) unions every interesting tag —
# a single-tag query misses most famous places (they are often tagged
# `historic` or `leisure=park`, not `tourism`). Value-regexes keep the
# union to 4 statements (each `around` statement costs a spatial-index
# lookup); generic shop is excluded — it floods results with tiny stores.
GENERAL_TAG_FILTERS = (
    '["tourism"]["name"]',
    '["historic"]["name"]',
    '["leisure"~"^(park|nature_reserve)$"]["name"]',
    '["amenity"~"^(place_of_worship|marketplace|cinema|theatre|arts_centre)$"]["name"]',
)


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
    # Flood filter: generic commerce POIs are not discovery material — even
    # if a query shape ever returns them (belt-and-braces with the union
    # query, which already excludes these tag classes).
    if tags.get("shop") and not (tags.get("tourism") or tags.get("historic")):
        return None
    if tags.get("amenity") in ("restaurant", "cafe", "fast_food", "bar", "pub") and not (
        tags.get("tourism") or tags.get("historic")
    ):
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

    # Notability signals from OSM metadata — used to sort famous places up.
    notability = 0
    if "wikidata" in tags or "wikipedia" in tags:
        notability += 3  # strong signal: the place has an encyclopedia article
    if tourism in ("attraction", "museum", "zoo", "gallery") or historic:
        notability += 2
    if tags.get("description"):
        notability += 1

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
        "_notability": notability,
    }


def _notability_sort_key(p: dict[str, Any]) -> tuple:
    """Famous-first, then by name for stable output."""
    return (-p.get("_notability", 0), p.get("name", ""))


def _live_disabled() -> bool:
    return os.getenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "") == "1"


def fetch_nearby(
    latitude: float,
    longitude: float,
    radius_m: int = 10000,
    category: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Real POIs around a coordinate. Raises OsmUnavailable on failure.

    With a category: nearest-first within that category. Without one: a
    union query across all interesting tag classes, ranked famous-first
    (wikidata presence → attraction tags → described places).
    """
    if _live_disabled():
        raise OsmUnavailable("live providers disabled via TRAVELGUARD_DISABLE_LIVE_PROVIDERS")
    around = f"around:{int(radius_m)},{latitude:.6f},{longitude:.6f}"
    if category:
        tag = CATEGORY_MAP.get(category, CATEGORY_MAP["attraction"])
        body = f"nwr({around}){tag};"
        out_limit = max(1, min(int(limit), 50))
    else:
        # Union across all interesting tags, then rank by notability below —
        # otherwise the answer is whatever few `tourism` nodes happen to sit
        # nearby instead of the area's actually-famous places.
        body = "".join(f"nwr({around}){t};" for t in GENERAL_TAG_FILTERS)
        out_limit = 80  # wide pool; ranking trims to `limit`
    if category:
        query = f"[out:json][timeout:12];({body})out center {out_limit};"
        elements = overpass_query(query)
    else:
        # The union needs real server-side compute time — the client must
        # outlive the query's own [timeout] or every mirror dies prematurely
        # (observed: 8s client kill → all mirrors "fail" → honest-but-empty
        # DEMO fallback on production even though Overpass was healthy).
        query = f"[out:json][timeout:18];({body})out center {out_limit};"
        elements = overpass_query(query, timeout=httpx.Timeout(25.0, connect=5.0))

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for el in elements:
        norm = _normalize(el, latitude, longitude)
        if norm and norm["id"] not in seen:
            seen.add(norm["id"])
            out.append(norm)
    if not out:
        raise OsmUnavailable("no named results in this area")
    if not category:
        out.sort(key=_notability_sort_key)
    for p in out:
        p.pop("_notability", None)  # internal ranking field — never exposed
    return out[: max(1, min(int(limit), 50))]
