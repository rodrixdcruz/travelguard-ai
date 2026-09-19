"""Live weather via Open-Meteo (key-less) for the discovery + route layers.

Current observed conditions for any coordinate on earth, mapped into the
weather dict shape the risk engine already consumes. Visibility is derived
from the observed WMO condition (Open-Meteo's current block has no visibility
field) and is flagged as such — observed fields are LIVE, the derived one is
ESTIMATED. Failures raise WeatherUnavailable → callers fall back to their
deterministic demo weather with DEMO labels, never silent demo-as-live.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("travelguard.weather_live")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "TravelGuardAI/0.1 (https://github.com/rodrixdcruz/travelguard-ai)"
TIMEOUT = httpx.Timeout(12.0, connect=5.0)

# WMO weather interpretation codes → condition label + derived visibility (km)
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
    """Raised when the live weather provider cannot serve a request."""


def current_conditions(latitude: float, longitude: float) -> dict[str, Any]:
    """Observed current weather for a coordinate (LIVE) + derived visibility (ESTIMATED)."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,precipitation,weather_code,wind_speed_10m",
        "wind_speed_unit": "kmh",
    }
    if _live_disabled():
        raise WeatherUnavailable("live providers disabled via TRAVELGUARD_DISABLE_LIVE_PROVIDERS")
    try:
        resp = httpx.get(OPEN_METEO_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
        cur = resp.json()["current"]
    except Exception as exc:
        logger.warning("Open-Meteo unavailable (%s); caller should fall back to demo", exc)
        raise WeatherUnavailable(str(exc)) from exc

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
