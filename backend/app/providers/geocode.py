"""Key-less geocoding via OpenStreetMap Nominatim.

Powers two honest-location features:
- place search (frontend "Set your location" box, journey planner for cities
  outside the built-in table) — an unknown place is geocoded to its REAL
  coordinates or rejected, never invented;
- reverse geocoding (naming a GPS fix "Nagpur, Maharashtra" instead of the
  anonymous "Your location").

Respects TRAVELGUARD_DISABLE_LIVE_PROVIDERS like the other live providers, and
returns empty/None on any failure so callers degrade to their labeled
fallbacks. Per Nominatim policy requests carry a descriptive User-Agent.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("travelguard.geocode")

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
_HEADERS = {"User-Agent": "TravelGuardAI/1.0 (https://github.com/rodrixdcruz/travelguard-ai)"}
_TIMEOUT = 8.0


def _live_disabled() -> bool:
    return os.getenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "").strip().lower() in ("1", "true", "yes")


def search(query: str, limit: int = 6) -> list[dict[str, Any]]:
    """Geocode a place name → [{name, short_name, latitude, longitude, type}].

    Empty list on any failure — callers must treat that as "unavailable", not
    as license to fabricate coordinates.
    """
    if httpx is None or not query.strip() or _live_disabled():
        return []
    try:
        resp = httpx.get(
            _SEARCH_URL,
            params={
                "q": query.strip(),
                "format": "jsonv2",
                "limit": str(min(max(int(limit), 1), 10)),
                "addressdetails": "0",
            },
            headers=_HEADERS,
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        logger.warning("Nominatim search unavailable (%s)", exc)
        return []
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


def reverse(latitude: float, longitude: float) -> str | None:
    """Human place name for a coordinate (city-level), or None on failure."""
    if httpx is None or _live_disabled():
        return None
    try:
        resp = httpx.get(
            _REVERSE_URL,
            params={"lat": str(latitude), "lon": str(longitude), "format": "jsonv2", "zoom": "10"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Nominatim reverse unavailable (%s)", exc)
        return None
    if not isinstance(data, dict):
        return None
    name = (data.get("name") or "").strip()
    if not name:
        name = (data.get("display_name") or "").split(",")[0].strip()
    return name or None
