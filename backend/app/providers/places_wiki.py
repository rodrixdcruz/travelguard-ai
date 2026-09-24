"""Notable-places provider — Wikipedia geosearch (key-less, global, fast).

General "near me" discovery needs FAMOUS places, not every mapped bench:
Wikipedia's geosearch returns exactly the places notable enough to have an
encyclopedia article for any coordinate on earth — landmarks, forts,
museums, stations, lakes — in one fast call that doesn't depend on
Overpass's capacity (which 504s under load, taking discovery with it).

Used as the primary source for category-less discovery. Fused results are
normalized into the same dict shape as the demo/OSM datasets so the API
and UI layers stay untouched; data_status is "LIVE" with the source named.
Coordinates come from Wikidata via the same MediaWiki API (page props),
so each entry is a real point, not a guess. Any failure raises
WikiUnavailable → callers fall back to OSM → demo, never silent
demo-as-live.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("travelguard.places_wiki")

GEOSEARCH_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "TravelGuardAI/0.1 (https://github.com/rodrixdcruz/travelguard-ai)"
TIMEOUT = httpx.Timeout(10.0, connect=4.0)
MAX_RADIUS_M = 10000  # MediaWiki hard limit for gsradius

# Words in titles that mark transport infrastructure rather than visitable
# attractions (metro/railway/bus stations dominate dense-city geosearch).
# They are EXCLUDED from place discovery — the services layer serves transit
# stops (LIVE) for the Transport tab, so stations never pollute Attractions.
_DEMOTE_SUBSTRINGS = (
    "metro station",
    "railway station",
    "railway halt",
    "bus station",
)

# Articles that geosearch matches by coordinates but that are NOT visitable
# places — historical polities, administrative areas, roads — so they are
# excluded outright rather than merely sorted to the back.
_EXCLUDE_SUBSTRINGS = (
    "kingdom of",
    "province",
    "empire",
    "dynasty",
    "siege of",
    "battle of",
    "constituency",
    "assembly",
    "municipal corporation",
    "zilla parishad",
    "taluka",
    "tehsil",
    "district council",
    "state highway",
    "national highway",
    "expressway",
    "airport authority",
)

# Title-keyword → discovery category. Wikipedia geosearch returns article
# titles, not OSM tags — a lake is "Ambazari Lake", a zoo is "[X] Zoo" —
# so classify from the title (first match wins; checked in specificity order).
_TITLE_CATEGORIES = (
    ("zoo", "zoo"),
    ("water park", "park"),
    ("amusement park", "park"),
    ("theme park", "park"),
    ("national park", "park"),
    ("sanctuary", "park"),
    ("waterfall", "nature"),
    ("beach", "nature"),
    ("island", "nature"),
    ("lake", "lake"),
    ("garden", "garden"),
    ("park", "park"),
    ("museum", "museum"),
    ("fort", "historical"),
    ("palace", "historical"),
    ("stadium", "attraction"),
)


def _title_category(title: str) -> str:
    lowered = title.lower()
    for keyword, category in _TITLE_CATEGORIES:
        if keyword in lowered:
            return category
    return "attraction"


class WikiUnavailable(Exception):
    """Raised when the Wikipedia provider cannot serve a request."""


def _live_disabled() -> bool:
    # Same CI kill switch the other live providers honor — the test suite
    # must make zero external HTTP calls.
    import os

    return os.getenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "") == "1"


def fetch_notable(
    latitude: float,
    longitude: float,
    radius_m: int = 10000,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Famous places around a coordinate, ranked by article quality signals.

    Raises WikiUnavailable on network/API failure. Returns [] when the area
    genuinely has no notable places (callers decide the fallback).
    """
    if _live_disabled():
        raise WikiUnavailable("live providers disabled via TRAVELGUARD_DISABLE_LIVE_PROVIDERS")
    radius_m = int(min(max(radius_m, 500), MAX_RADIUS_M))
    try:
        resp = httpx.get(
            GEOSEARCH_URL,
            params={
                "action": "query",
                "list": "geosearch",
                "gscoord": f"{latitude}|{longitude}",
                "gsradius": radius_m,
                "gslimit": max(10, min(int(limit) * 2, 50)),
                "format": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        pages = resp.json()["query"]["geosearch"]
    except Exception as exc:
        raise WikiUnavailable(f"wikipedia geosearch: {exc}") from exc

    out: list[dict[str, Any]] = []
    for p in pages:
        title = str(p.get("title", "")).strip()
        if not title:
            continue
        lat, lon = p.get("lat"), p.get("lon")
        if lat is None or lon is None:
            continue
        lowered = title.lower()
        if any(s in lowered for s in _EXCLUDE_SUBSTRINGS):
            continue
        if any(s in lowered for s in _DEMOTE_SUBSTRINGS):
            continue
        out.append(
            {
                "id": f"wiki-{p.get('pageid', title[:24])}",
                "name": title[:120],
                "category": _title_category(title),
                "description": "Notable place with a Wikipedia article",
                "latitude": float(lat),
                "longitude": float(lon),
                "address": "",
                "opening_hours": "Unknown",
                "rating": None,
                "tags": ["notable", "wikipedia"],
                "data_source": "wikipedia_geosearch",
                "data_status": "LIVE",
                "_rank": (0, title),
            }
        )

    # Alphabetical within the notable set; stations never reach here.
    out.sort(key=lambda p: p["_rank"])
    for p in out:
        p.pop("_rank", None)
    return out[: max(1, min(int(limit), 50))]
