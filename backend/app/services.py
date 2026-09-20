"""Data services: routing + weather + disruptions.

All providers gracefully degrade to the deterministic demo dataset, so the
app works end-to-end with zero external API keys (DEMO MODE).
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from . import demo_data
from .schemas import AnalyzeRequest, Coordinate, RoutePoint

logger = logging.getLogger("travelguard.services")

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


# ── Routing ─────────────────────────────────────────────────────────────

def resolve_point(name: str) -> RoutePoint:
    coord = demo_data.lookup_city(name)
    if coord is None:
        # Unknown city: derive a stable pseudo-coordinate from the name so the
        # demo still renders a route without any network call.
        h = hashlib.sha256(name.strip().lower().encode()).digest()
        lat = 8.0 + (h[0] / 255.0) * 28.0        # 8..36 N (India-ish band)
        lon = 68.0 + (h[1] / 255.0) * 30.0       # 68..98 E
        coord = Coordinate(lat=round(lat, 4), lon=round(lon, 4))
    return RoutePoint(name=name.strip().title(), lat=coord.lat, lon=coord.lon)


def resolve_route(origin: RoutePoint, destination: RoutePoint) -> tuple[list[Coordinate], bool]:
    """Return (path, is_known_route)."""
    known = demo_data.get_route(origin.name, destination.name)
    if known:
        return [Coordinate(lat=lat, lon=lon) for lat, lon in known], True
    return demo_data.build_generic_route(origin, destination), False


# ── Weather (demo; live provider hook kept separate) ────────────────────

_DEMO_WEATHER: dict[str, dict[str, Any]] = {
    "mumbai-pune": {
        "condition": "Heavy Rain", "precip_mm": 18.0, "visibility_km": 2.5,
        "wind_kph": 32.0, "temp_c": 24.0,
    },
    "delhi-jaipur": {
        "condition": "Haze", "precip_mm": 0.0, "visibility_km": 3.0,
        "wind_kph": 14.0, "temp_c": 31.0,
    },
    "bengaluru-mysuru": {
        "condition": "Partly Cloudy", "precip_mm": 0.0, "visibility_km": 9.0,
        "wind_kph": 12.0, "temp_c": 27.0,
    },
    "bengaluru-chennai": {
        "condition": "Clear", "precip_mm": 0.0, "visibility_km": 10.0,
        "wind_kph": 10.0, "temp_c": 33.0,
    },
}


def _route_key(origin_name: str, destination_name: str) -> str:
    a, b = sorted([origin_name.strip().lower(), destination_name.strip().lower()])
    return f"{a}-{b}"


def _demo_weather_for_key(key: str) -> dict[str, Any]:
    if key in _DEMO_WEATHER:
        return dict(_DEMO_WEATHER[key])
    # Deterministic variation derived from the key hash (stable across runs).
    h = hashlib.sha256(key.encode()).digest()
    choices = ["Clear", "Partly Cloudy", "Light Rain", "Mist"]
    cond = choices[h[2] % len(choices)]
    return {
        "condition": cond,
        "precip_mm": round(h[3] % 6 * 1.4, 1),
        "visibility_km": [9.0, 8.0, 4.5, 3.0][h[4] % 4],
        "wind_kph": 8.0 + (h[5] % 20),
        "temp_c": 22.0 + (h[6] % 14),
    }


def fetch_route_weather_sync(origin_name: str, destination_name: str, *,
                             origin_coord: Coordinate | None = None,
                             destination_coord: Coordinate | None = None) -> dict[str, Any]:
    """Synchronous body of fetch_route_weather — callers inside async
    endpoints must run this via asyncio.to_thread so the blocking HTTP call
    (Open-Meteo) never stalls the event loop.
    """
    if origin_coord is not None and destination_coord is not None:
        mid_lat = (origin_coord.lat + destination_coord.lat) / 2.0
        mid_lon = (origin_coord.lon + destination_coord.lon) / 2.0
        try:
            from .providers.weather_live import current_conditions
            return current_conditions(mid_lat, mid_lon)
        except Exception as exc:
            logger.warning("Live route weather unavailable (%s) — DEMO fallback", exc)
    demo = _demo_weather_for_key(_route_key(origin_name, destination_name))
    demo["data_source"] = "travelguard_demo_weather"
    demo["data_status"] = "DEMO"
    return demo


async def fetch_route_weather(origin_name: str, destination_name: str, *,
                              origin_coord: Coordinate | None = None,
                              destination_coord: Coordinate | None = None) -> dict[str, Any]:
    """Async convenience wrapper kept for existing callers/tests."""
    return fetch_route_weather_sync(
        origin_name, destination_name,
        origin_coord=origin_coord, destination_coord=destination_coord,
    )


# ── Per-segment conditions (deterministic, context-aware) ───────────────

def segment_weather(
    base: dict[str, Any], index: int, total: int, travel_dt: datetime, is_ghat: bool
) -> dict[str, Any]:
    """Vary the route-level weather per segment in a deterministic way.

    Early segments are calmer; the middle third is worst (storms/fog peak);
    the last third recovers. Ghat segments get mist multipliers.
    """
    cond = str(base.get("condition", "Clear"))
    out = dict(base)
    h = hashlib.sha256(f"{cond}-{index}".encode()).digest()
    position = index / max(total - 1, 1)

    if "rain" in cond.lower() and 0.3 <= position <= 0.7:
        out["condition"] = "Heavy Rain" if "heavy" not in cond.lower() else cond
        out["precip_mm"] = round(float(base.get("precip_mm", 5.0)) * 1.8, 1)
        out["visibility_km"] = round(min(float(base.get("visibility_km", 6.0)), 2.0), 1)
    elif "haze" in cond.lower() or "fog" in cond.lower() or "mist" in cond.lower():
        out["visibility_km"] = round(max(0.6, float(base.get("visibility_km", 3.0)) - index * 0.3), 1)
    if is_ghat and "clear" not in cond.lower():
        out["visibility_km"] = round(min(out.get("visibility_km", 9.0), 3.5), 1)
        out["condition"] = out.get("condition") if out.get("condition") != "Clear" else "Mist"
    # Night travel: visibility drop everywhere
    if travel_dt.hour >= 22 or travel_dt.hour < 6:
        out["visibility_km"] = round(max(0.8, float(out.get("visibility_km", 9.0)) * 0.5), 1)
        out["night"] = True
    return out


# ── Road + disruption profiles ──────────────────────────────────────────

def segment_road(index: int, total: int, is_known: bool) -> dict[str, Any]:
    position = index / max(total - 1, 1)
    if is_known:
        # Middle stretch of known demo routes passes ghat/rural terrain.
        if 0.3 <= position <= 0.6:
            return {"type": "ghat", "surface": "fair", "lighting": "none"}
        if position < 0.15 or position > 0.85:
            return {"type": "urban", "surface": "good", "lighting": "yes"}
        return {"type": "highway", "surface": "good", "lighting": "none"}
    h = hashlib.sha256(f"road-{index}".encode()).digest()
    rtype = ["highway", "rural", "urban"][h[0] % 3]
    surface = ["good", "fair", "good"][h[1] % 3]
    return {"type": rtype, "surface": surface, "lighting": "yes" if rtype == "urban" else "none"}


def segment_accident_history(index: int, total: int, is_known: bool) -> dict[str, Any]:
    position = index / max(total - 1, 1)
    if is_known and 0.35 <= position <= 0.55:
        return {"accidents_per_km_year": 2.4, "severity_index": 7.5}
    if is_known and position > 0.8:
        return {"accidents_per_km_year": 1.1, "severity_index": 5.0}
    h = hashlib.sha256(f"acc-{index}".encode()).digest()
    return {"accidents_per_km_year": round(0.3 + (h[0] % 10) / 10.0, 1), "severity_index": 3.0 + (h[1] % 3)}


def segment_disruptions(index: int, total: int, is_known: bool) -> list[dict[str, Any]]:
    position = index / max(total - 1, 1)
    if is_known and 0.4 <= position <= 0.5:
        return [{"type": "construction", "impact": 68.0, "description": "Lane closure for monsoon repair work"}]
    if is_known and 0.6 <= position <= 0.65:
        return [{"type": "diversion", "impact": 45.0, "description": "Diversion due to bridge maintenance"}]
    return []


def segment_duration(
    path: list[Coordinate], road: dict[str, Any], weather: dict[str, Any], scale: float = 1.0
) -> float:
    """Duration estimate that reflects conditions (slower in bad weather)."""
    dist = demo_data.route_length_km(path) * scale
    base_speed = 70.0
    rtype = road.get("type")
    if rtype == "ghat":
        base_speed = 38.0
    elif rtype == "rural":
        base_speed = 50.0
    elif rtype == "urban":
        base_speed = 40.0
    vis = float(weather.get("visibility_km", 9.0))
    if vis < 2.0:
        base_speed *= 0.65
    elif vis < 4.0:
        base_speed *= 0.8
    return round(dist / max(base_speed, 15.0) * 60.0, 1)
