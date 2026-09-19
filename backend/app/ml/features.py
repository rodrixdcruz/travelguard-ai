"""Feature engineering: structured journey/location data → numeric vectors.

Pure functions, no model logic. Kept separate from prediction so features
can be inspected, tested, and reused by both the ML models and the demo UI.
"""
from __future__ import annotations

from typing import Any

# Canonical, ordered feature list — the model contract.
FEATURE_NAMES: list[str] = [
    "weather_severity",
    "rain_intensity",
    "visibility",
    "wind_severity",
    "night_indicator",
    "road_disruption",
    "historical_incident_density",
    "distance_to_emergency_service",
    "nearby_service_density",
    "tourist_area_indicator",
    "area_activity_level",
    "route_condition",
    "time_of_day",
]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def weather_features(weather: dict[str, Any]) -> dict[str, float]:
    """Map raw weather fields to model features.

    weather_severity: 0 (clear) .. 100 (severe storm).
    """
    condition = str(weather.get("condition", "Clear")).lower()
    precip = _num(weather.get("precip_mm", 0.0))
    visibility = _num(weather.get("visibility_km", 10.0))
    wind = _num(weather.get("wind_kph", 8.0))

    severity = 5.0
    if "thunder" in condition:
        severity = 90.0
    elif "heavy" in condition and "rain" in condition:
        severity = 78.0
    elif "rain" in condition:
        severity = 45.0 + min(precip * 1.5, 30.0)
    elif "fog" in condition or "mist" in condition or "haze" in condition:
        severity = 55.0
    elif "cloud" in condition:
        severity = 20.0

    return {
        "weather_severity": min(severity, 100.0),
        "rain_intensity": min(precip, 50.0),
        "visibility": max(0.0, min(visibility, 20.0)),
        "wind_severity": min(max(wind - 10.0, 0.0) * 2.0, 100.0),
    }


def context_features(context: dict[str, Any]) -> dict[str, float]:
    """Map travel-context fields (hour, area profile) to model features."""
    hour = _num(context.get("hour", 12), 12) % 24
    is_night = 1.0 if (hour >= 22 or hour < 6) else 0.0
    return {
        "night_indicator": is_night,
        "tourist_area_indicator": 1.0 if context.get("tourist_area") else 0.0,
        "area_activity_level": max(0.0, min(_num(context.get("activity_level", 5.0), 5.0), 10.0)),
        # Cyclical-ish encoding kept simple: rush hours score higher exposure.
        "time_of_day": 8.0 if hour in (8, 9, 10, 17, 18, 19) else (2.0 if is_night else 4.0),
    }


def road_features(road: dict[str, Any], disruptions: list[dict[str, Any]] | None = None) -> dict[str, float]:
    """Map road profile + active disruptions to model features."""
    rtype = str(road.get("type", "highway")).lower()
    surface = str(road.get("surface", "good")).lower()

    condition = {"expressway": 90.0, "highway": 75.0, "urban": 65.0, "rural": 45.0, "ghat": 30.0}.get(rtype, 60.0)
    if surface == "fair":
        condition -= 12.0
    elif surface == "poor":
        condition -= 28.0

    disruption = 0.0
    for d in disruptions or []:
        disruption = max(disruption, _num(d.get("impact", 40.0), 40.0))

    return {
        "road_disruption": min(disruption, 100.0),
        "route_condition": max(0.0, min(condition, 100.0)),
    }


def safety_features(payload: dict[str, Any]) -> dict[str, float]:
    """Build the full ordered safety feature vector from an API payload.

    Expected payload keys: weather, location, road, context (all optional).
    Unknown/missing fields fall back to neutral defaults — features never throw.
    """
    weather = payload.get("weather") or {}
    location = payload.get("location") or {}
    road = payload.get("road") or {}
    context = payload.get("context") or {}

    values: dict[str, float] = {}
    values.update(weather_features(weather))
    values.update(context_features(context))
    values.update(road_features(road, context.get("disruptions")))

    values["historical_incident_density"] = max(0.0, _num(location.get("incident_density", 0.4), 0.4))
    values["distance_to_emergency_service"] = max(0.0, min(_num(location.get("nearest_hospital_km", 8.0), 8.0), 60.0))
    values["nearby_service_density"] = max(0.0, min(_num(location.get("service_density", 5.0), 5.0), 10.0))

    # Ordered vector; any missing feature becomes 0.0 rather than KeyError.
    return {name: round(values.get(name, 0.0), 4) for name in FEATURE_NAMES}


def vectorize(features: dict[str, float]) -> list[list[float]]:
    """Dict → single-row matrix in canonical order for sklearn."""
    return [[features[name] for name in FEATURE_NAMES]]


def describe_factors(features: dict[str, float]) -> list[dict[str, Any]]:
    """Human-readable contextual risk factors, strongest first.

    These are contextual explanations, NOT model feature importances.
    """
    factors: list[dict[str, Any]] = []

    def add(label: str, weight: float, detail: str) -> None:
        factors.append({"label": label, "weight": round(weight, 1), "detail": detail})

    if features["weather_severity"] >= 40:
        add("Weather severity", features["weather_severity"], "conditions degrade driving safety")
    if features["rain_intensity"] >= 5:
        add("Rainfall", min(features["rain_intensity"] * 2, 100), f"{features['rain_intensity']:.1f} mm precipitation")
    if features["visibility"] <= 4:
        add("Low visibility", (4.0 - features["visibility"]) * 20 + 30, f"~{features['visibility']:.1f} km visibility")
    if features["wind_severity"] >= 30:
        add("Strong wind", features["wind_severity"], "crosswind risk, especially for two-wheelers")
    if features["night_indicator"] >= 0.5:
        add("Night travel", 60, "reduced visibility and fewer emergency resources")
    if features["road_disruption"] >= 30:
        add("Road disruption", features["road_disruption"], "active disruptions along the stretch")
    if features["historical_incident_density"] >= 1.0:
        add("Incident history", min(features["historical_incident_density"] * 25, 100), f"{features['historical_incident_density']:.1f} incidents/km-yr nearby")
    if features["distance_to_emergency_service"] >= 15:
        add("Far from emergency services", min(features["distance_to_emergency_service"] * 2, 100), f"{features['distance_to_emergency_service']:.0f} km to nearest hospital")
    if features["route_condition"] <= 40:
        add("Poor road condition", 100 - features["route_condition"], "surface/alignment reduce safe speeds")

    return sorted(factors, key=lambda f: f["weight"], reverse=True)
