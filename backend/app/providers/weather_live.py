"""Live weather for the discovery + route layers.

Provider order, chosen for cloud deployments:
1. MET Norway Locationforecast (key-less). Primary because it does NOT block
   shared cloud-platform egress IPs — Open-Meteo answers Render/shared IPs
   with 429 regardless of request rate (observed live; the same finding made
   MausamBagha AI switch to MET Norway).
2. Open-Meteo (key-less). Kept as fallback for environments where MET is
   unreachable.

Both are mapped into the same weather dict shape the risk engine already
consumes; `data_status` is "LIVE" with the actual source in `data_source`.
Visibility is not published by either provider's current block — it is
derived from the observed condition and flagged `visibility_status:
"ESTIMATED"`. Failures raise WeatherUnavailable → callers fall back to their
deterministic demo weather with DEMO labels, never silent demo-as-live.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import httpx

logger = logging.getLogger("travelguard.weather_live")

MET_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
# MET's terms require an identifying User-Agent with contact info.
USER_AGENT = "TravelGuardAI/0.1 (https://github.com/rodrixdcruz/travelguard-ai)"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = httpx.Timeout(12.0, connect=5.0)

# --- In-memory TTL cache ---------------------------------------------------
# Journeys analyze 5-8 segments per request and users re-analyze the same
# routes repeatedly; without a cache every analysis re-hits MET Norway per
# segment (and MET rate-limits per identifying User-Agent). Observations
# update hourly upstream, so a short TTL keeps "LIVE" honest: the value is
# at most a few minutes old and `data_source` still names the real provider.
CACHE_TTL_SECONDS = 15 * 60
CACHE_MAX_ENTRIES = 256
# ~2 decimal places ≈ 1.1 km — segment midpoints for the same route collapse
# to one fetch without confusing distinct nearby cities.
_CACHE: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = Lock()


def _cache_key(latitude: float, longitude: float) -> tuple[float, float]:
    return (round(latitude, 2), round(longitude, 2))


def _cache_get(key: tuple[float, float]) -> dict[str, Any] | None:
    now = time.monotonic()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is None:
            return None
        fetched_at, value = hit
        if now - fetched_at >= CACHE_TTL_SECONDS:
            _CACHE.pop(key, None)
            return None
        return dict(value)  # copy: callers must not mutate the shared entry


def _cache_put(key: tuple[float, float], value: dict[str, Any]) -> None:
    with _CACHE_LOCK:
        if len(_CACHE) >= CACHE_MAX_ENTRIES:
            _CACHE.pop(min(_CACHE, key=lambda k: _CACHE[k][0]), None)
        _CACHE[key] = (time.monotonic(), dict(value))

# MET symbol stems -> condition label + derived visibility (km).
# Suffixes (_day/_night/_polartwilight) are stripped before lookup.
MET_SYMBOLS = {
    "clearsky": ("Clear", 10.0), "fair": ("Fair", 9.0),
    "partlycloudy": ("Partly Cloudy", 8.0), "cloudy": ("Overcast", 6.0),
    "lightrain": ("Light Rain", 4.5), "rain": ("Rain", 3.5), "heavyrain": ("Heavy Rain", 2.0),
    "lightrainshowers": ("Rain Showers", 4.0), "rainshowers": ("Rain Showers", 3.0),
    "heavyrainshowers": ("Heavy Showers", 1.8),
    "lightsnow": ("Light Snow", 4.0), "snow": ("Snow", 2.5), "heavysnow": ("Heavy Snow", 1.0),
    "lightsnowshowers": ("Snow Showers", 3.5), "snowshowers": ("Snow Showers", 2.5),
    "heavysnowshowers": ("Heavy Snow Showers", 1.0),
    "sleet": ("Sleet", 3.0), "sleetshowers": ("Sleet Showers", 2.5),
    "fog": ("Fog", 1.0),
}

# Open-Meteo WMO codes → condition label + derived visibility (km)
WMO = {
    0: ("Clear", 10.0), 1: ("Partly Cloudy", 9.0), 2: ("Partly Cloudy", 7.5),
    3: ("Overcast", 6.0), 45: ("Fog", 1.0), 48: ("Fog", 0.8),
    51: ("Light Drizzle", 6.0), 53: ("Drizzle", 5.0), 55: ("Drizzle", 4.0),
    61: ("Light Rain", 4.5), 63: ("Rain", 3.5), 65: ("Heavy Rain", 2.0),
    71: ("Light Snow", 4.0), 73: ("Snow", 2.5), 75: ("Heavy Snow", 1.0),
    80: ("Rain Showers", 4.0), 81: ("Rain Showers", 3.0), 82: ("Violent Showers", 1.5),
    95: ("Thunderstorm", 2.0), 96: ("Thunderstorm", 1.5), 99: ("Thunderstorm", 1.0),
}


def _live_disabled() -> bool:
    return os.getenv("TRAVELGUARD_DISABLE_LIVE_PROVIDERS", "") == "1"


class WeatherUnavailable(Exception):
    """Raised when no live weather provider can serve a request."""


def current_conditions(latitude: float, longitude: float) -> dict[str, Any]:
    """Observed current weather for a coordinate (LIVE) + derived visibility (ESTIMATED).

    Served from a small TTL cache when a recent observation exists (repeat
    journey analyses skip the provider round-trip entirely). Tries MET
    Norway, then Open-Meteo; raises WeatherUnavailable when both fail.
    Failures are NOT cached — the next request retries the providers.
    """
    if _live_disabled():
        raise WeatherUnavailable("live providers disabled via TRAVELGUARD_DISABLE_LIVE_PROVIDERS")
    key = _cache_key(latitude, longitude)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    errors: list[str] = []
    for fetch in (_met_conditions, _open_meteo_conditions):
        try:
            result = fetch(latitude, longitude)
            _cache_put(key, result)
            return result
        except WeatherUnavailable as exc:
            errors.append(str(exc))
    logger.warning("All live weather providers unavailable (%s); caller should fall back to demo", "; ".join(errors))
    raise WeatherUnavailable("; ".join(errors))


def _met_conditions(latitude: float, longitude: float) -> dict[str, Any]:
    """MET Norway Locationforecast compact → the app's weather dict."""
    try:
        resp = httpx.get(
            MET_URL, params={"lat": latitude, "lon": longitude},
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        raise WeatherUnavailable(f"met-norway: {exc}") from exc

    try:
        timeseries = payload["properties"]["timeseries"]
        # Entry closest to (not after) now UTC — MET starts the series at the current hour.
        now = datetime.now(timezone.utc)
        entry = min(
            timeseries,
            key=lambda e: abs((datetime.fromisoformat(str(e["time"]).replace("Z", "+00:00")) - now).total_seconds()),
        )
        details = entry["data"]["instant"]["details"]
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise WeatherUnavailable(f"met-norway: malformed response ({exc})") from exc

    symbol = None
    precip_mm = 0.0
    data = entry.get("data", {})
    for window in ("next_1_hours", "next_6_hours", "next_12_hours"):
        section = data.get(window)
        if not isinstance(section, dict):
            continue
        w_details = section.get("details")
        if isinstance(w_details, dict) and w_details.get("precipitation_amount") is not None:
            precip_mm = float(w_details["precipitation_amount"])
        summary = section.get("summary")
        if isinstance(summary, dict) and summary.get("symbol_code"):
            symbol = str(summary["symbol_code"])
        if symbol or precip_mm:
            break

    stem = (symbol or "").split("_", 1)[0]
    if "thunder" in stem:
        cond, vis = "Thunderstorm", 2.0
    else:
        cond, vis = MET_SYMBOLS.get(stem, ("Unknown", 6.0))

    wind_ms = details.get("wind_speed")
    return {
        "condition": cond,
        "precip_mm": round(precip_mm, 1),
        # Derived from the observed symbol, not observed directly:
        "visibility_km": vis,
        "visibility_status": "ESTIMATED",
        "wind_kph": round(float(wind_ms) * 3.6, 1) if wind_ms is not None else 0.0,
        "temp_c": float(details.get("air_temperature", 0.0)),
        "data_source": "met-norway",
        "data_status": "LIVE",
    }


def _open_meteo_conditions(latitude: float, longitude: float) -> dict[str, Any]:
    """Open-Meteo current block → the app's weather dict (fallback provider)."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,precipitation,weather_code,wind_speed_10m",
        "wind_speed_unit": "kmh",
    }
    try:
        resp = httpx.get(OPEN_METEO_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
        cur = resp.json()["current"]
    except Exception as exc:
        raise WeatherUnavailable(f"open-meteo: {exc}") from exc

    code = int(cur.get("weather_code", 0))
    cond, vis = WMO.get(code, ("Unknown", 6.0))
    return {
        "condition": cond,
        "precip_mm": float(cur.get("precipitation", 0.0)),
        # Derived from the observed WMO code, not observed directly:
        "visibility_km": vis,
        "visibility_status": "ESTIMATED",
        "wind_kph": round(float(cur.get("wind_speed_10m", 0.0)), 1),
        "temp_c": float(cur.get("temperature_2m", 0.0)),
        "data_source": "open-meteo",
        "data_status": "LIVE",
    }
