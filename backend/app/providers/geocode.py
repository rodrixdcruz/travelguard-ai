"""Geocoding providers: Geoapify (API key tier) + OSM Nominatim (key-less).

Powers two honest-location features:
- place search (frontend "Set your location" box, journey planner for cities
  outside the built-in table) — an unknown place is geocoded to its REAL
  coordinates or rejected, never invented;
- reverse geocoding (naming a GPS fix "Nagpur, Maharashtra" instead of the
  anonymous "Your location").

Two-tier chain, so place search survives OSM's datacenter-IP throttling
(Nominatim/Overpass 429 cloud egress like Render's) when an API key exists:

1. GEOAPIFY_API_KEY set  → Geoapify (3,000 free req/day, no credit card,
   accepts cloud-egress traffic).
2. no key (or keyed call FAILED) → OSM Nominatim key-less fallback.

Fallback happens only when the keyed provider *fails* (HTTP error, timeout,
invalid key). A legitimate "no matches" answer from Geoapify is reported as
such — never masked by a second provider, so the labels stay honest.
Either way results carry real coordinates or the caller reports UNAVAILABLE.

All requests respect TRAVELGUARD_DISABLE_LIVE_PROVIDERS like the other live
providers, go through the shared TTL cache, and carry a descriptive
User-Agent per Nominatim policy.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Literal

from .nominatim_cache import cached

logger = logging.getLogger("travelguard.geocode")

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

GeoSource = Literal["geoapify", "osm_nominatim"]

_SEARCH_TTL = 6 * 60 * 60  # Place names change on OSM-edit timescales (days) — 6h keeps LIVE honest.
_REVERSE_TTL = 30 * 60  # City-level names for a coordinate — 30 min covers a planning session.
_TIMEOUT = 8.0

_NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
_NOMINATIM_HEADERS = {"User-Agent": "TravelGuardAI/1.0 (https://github.com/rodrixdcruz/travelguard-ai)"}

_GEOAPIFY_SEARCH = "https://api.geoapify.com/v1/geocode/search"
_GEOAPIFY_REVERSE = "https://api.geoapify.com/v1/geocode/reverse"


def _live_disabled() -> bool:
    return os.getenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "").strip().lower() in ("1", "true", "yes")


def _api_key() -> str | None:
    key = os.getenv("GEOAPIFY_API_KEY", "").strip()
    return key or None


def active_provider() -> GeoSource | None:
    """Which geocoder would serve right now (None = all disabled / no httpx)."""
    if httpx is None or _live_disabled():
        return None
    return "geoapify" if _api_key() else "osm_nominatim"


def search(query: str, limit: int = 6) -> tuple[list[dict[str, Any]], GeoSource | None]:
    """Geocode a place name → ([{name, short_name, latitude, longitude, type}], source).

    Empty list on any failure — callers must treat that as "unavailable", not
    as license to fabricate coordinates. The second element names the geocoder
    that produced the answer (None when nothing could answer).
    """
    if httpx is None or not query.strip() or _live_disabled():
        return [], None

    key = _api_key()
    if key is not None:
        results = _search_geoapify(query, limit, key)
        if results is not None:
            return results, "geoapify"
        logger.warning("Geoapify search failed — falling back to OSM Nominatim")
    return _search_nominatim(query, limit), "osm_nominatim"


def reverse(latitude: float, longitude: float) -> tuple[str | None, GeoSource | None]:
    """Human place name for a coordinate (city-level) → (name, source)."""
    if httpx is None or _live_disabled():
        return None, None

    key = _api_key()
    if key is not None:
        name = _reverse_geoapify(latitude, longitude, key)
        if name is not None:
            return name, "geoapify"
        logger.warning("Geoapify reverse failed — falling back to OSM Nominatim")
    return _reverse_nominatim(latitude, longitude), "osm_nominatim"


# ── Tier 1: Geoapify (API key) ────────────────────────────────────────────


def _search_geoapify(query: str, limit: int, key: str) -> list[dict[str, Any]] | None:
    """Geoapify forward geocoding. None = provider failure (→ fallback);
    [] = a real, honest "no matches" (reported as such, not masked)."""

    def _fetch() -> list[dict[str, Any]] | None:
        try:
            resp = httpx.get(  # type: ignore[union-attr]
                _GEOAPIFY_SEARCH,
                params={
                    "text": query.strip(),
                    "limit": str(min(max(int(limit), 1), 10)),
                    "format": "json",
                    "apiKey": key,
                },
                timeout=_TIMEOUT,
                follow_redirects=True,
            )
            resp.raise_for_status()
            payload = resp.json() or {}
            rows = payload.get("results") or []
            out: list[dict[str, Any]] = []
            for row in rows[: max(min(int(limit), 10), 1)]:
                lat, lon = row.get("lat"), row.get("lon")
                if lat is None or lon is None:
                    continue
                # Geoapify returns labelled address parts; prefer the most
                # specific non-street line for the display name.
                parts = [
                    row.get(k)
                    for k in (
                        "name",
                        "city",
                        "town",
                        "village",
                        "municipality",
                        "county",
                        "state",
                        "country",
                    )
                    if row.get(k)
                ]
                seen: list[str] = []
                for p in parts:
                    if p not in seen:
                        seen.append(p)
                display = ", ".join(seen) or row.get("formatted") or ""
                out.append(
                    {
                        "name": display,
                        "short_name": (row.get("name") or row.get("city") or display.split(",")[0]).strip(),
                        "latitude": float(lat),
                        "longitude": float(lon),
                        "type": row.get("result_type") or "",
                    }
                )
            return out
        except Exception as exc:
            logger.warning("Geoapify search unavailable (%s)", exc)
            return None

    return cached(("geo:geoapify:search", query.strip().lower(), limit), _SEARCH_TTL, _fetch)


def _reverse_geoapify(latitude: float, longitude: float, key: str) -> str | None:
    """Geoapify reverse geocoding. None = failure or no name (→ fallback)."""

    def _fetch() -> str | None:
        try:
            resp = httpx.get(  # type: ignore[union-attr]
                _GEOAPIFY_REVERSE,
                params={"lat": str(latitude), "lon": str(longitude), "format": "json", "apiKey": key},
                timeout=_TIMEOUT,
                follow_redirects=True,
            )
            resp.raise_for_status()
            payload = resp.json() or {}
            row = (payload.get("features") or [{}])[0].get("properties", {}) if isinstance(payload, dict) else {}
            if not isinstance(row, dict):
                return None
            return (row.get("city") or row.get("name") or row.get("state") or "").strip() or None
        except Exception as exc:
            logger.warning("Geoapify reverse unavailable (%s)", exc)
            return None

    return cached(("geo:geoapify:reverse", round(latitude, 4), round(longitude, 4)), _REVERSE_TTL, _fetch)


# ── Tier 2: OSM Nominatim (key-less fallback) ────────────────────────────


def _search_nominatim(query: str, limit: int) -> list[dict[str, Any]]:
    def _fetch() -> list[dict[str, Any]]:
        try:
            resp = httpx.get(  # type: ignore[union-attr]
                _NOMINATIM_SEARCH,
                params={
                    "q": query.strip(),
                    "format": "jsonv2",
                    "limit": str(min(max(int(limit), 1), 10)),
                    "addressdetails": "0",
                },
                headers=_NOMINATIM_HEADERS,
                timeout=_TIMEOUT,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.json() or []
        except Exception as exc:
            logger.warning("Nominatim search unavailable (%s)", exc)
            return []

    payload = cached(("geo:osm:search", query.strip().lower(), limit), _SEARCH_TTL, _fetch)
    out: list[dict[str, Any]] = []
    for row in payload if isinstance(payload, list) else []:
        lat, lon = row.get("lat"), row.get("lon")
        if lat is None or lon is None:
            continue
        display = row.get("display_name") or ""
        out.append(
            {
                "name": display,
                "short_name": (row.get("name") or display.split(",")[0]).strip(),
                "latitude": float(lat),
                "longitude": float(lon),
                "type": row.get("type") or "",
            }
        )
    return out


def _reverse_nominatim(latitude: float, longitude: float) -> str | None:
    def _fetch() -> dict[str, Any] | None:
        try:
            resp = httpx.get(  # type: ignore[union-attr]
                _NOMINATIM_REVERSE,
                params={"lat": str(latitude), "lon": str(longitude), "format": "jsonv2", "zoom": "10"},
                headers=_NOMINATIM_HEADERS,
                timeout=_TIMEOUT,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("Nominatim reverse unavailable (%s)", exc)
            return None

    data = cached(("geo:osm:reverse", round(latitude, 4), round(longitude, 4)), _REVERSE_TTL, _fetch)
    if not isinstance(data, dict):
        return None
    name = (data.get("name") or "").strip()
    if not name:
        name = (data.get("display_name") or "").split(",")[0].strip()
    return name or None
