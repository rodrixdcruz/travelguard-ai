"""Weather provider seam for the discovery layer.

Returns demo route-level conditions today; a live API (e.g. OpenWeatherMap)
slots in behind the same signature when WEATHER_API_KEY is configured.
The AI day planner uses this for the safety context check.
"""
from __future__ import annotations

import hashlib
from typing import Any


def current_conditions(latitude: float, longitude: float) -> dict[str, Any]:
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
