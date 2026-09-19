"""Weather provider seam for the discovery layer.

LIVE-first: real conditions via key-less Open-Meteo; deterministic demo
weather only as labeled fallback (the AI day planner's safety-context check
uses this). Observed fields are LIVE; visibility is derived and flagged
ESTIMATED.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from .weather_live import WeatherUnavailable, current_conditions as live_current

logger = logging.getLogger("travelguard.weather")


def current_conditions(latitude: float, longitude: float) -> dict[str, Any]:
    """LIVE Open-Meteo conditions; deterministic demo weather as labeled fallback."""
    try:
        return live_current(latitude, longitude)
    except WeatherUnavailable as exc:
        logger.warning("Live weather unavailable (%s) — DEMO fallback", exc)
    return _demo_conditions(latitude, longitude)


def _demo_conditions(latitude: float, longitude: float) -> dict[str, Any]:
    """Deterministic demo weather for a coordinate (stable across runs)."""
    h = hashlib.sha256(f"{latitude:.3f},{longitude:.3f}".encode()).digest()
    choices = ["Clear", "Partly Cloudy", "Haze", "Light Rain"]
    cond = choices[h[0] % len(choices)]
    return {
        "condition": cond,
        "precip_mm": round((h[1] % 5) * 1.6, 1),
        "visibility_km": [9.0, 8.0, 5.0, 3.5][h[2] % 4],
        "wind_kph": 8.0 + (h[3] % 18),
        "temp_c": 26.0 + (h[4] % 10),
        "data_source": "travelguard_demo_weather",
        "data_status": "DEMO",
    }
