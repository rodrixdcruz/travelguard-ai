"""Journey fare comparison — all transport modes side by side.

Pure derivation from the existing modeled-rate transport estimator: given a
journey's endpoints and traveler count, every mode's fare/time is computed by
the SAME `transport.estimate` used for segments, so the comparison row can
never disagree with the rest of the app. Everything is honestly ESTIMATED —
modeled rate cards × road-factor distance, never live fares.
"""
from __future__ import annotations

from typing import Any

from .providers import transport

# Display metadata per mode (backend owns the ordering).
MODE_META = [
    ("local_train", "Local train", "🚆"),
    ("bus", "Bus", "🚌"),
    ("metro", "Metro", "🚇"),
    ("rapido", "Rapido bike", "🛵"),
    ("auto", "Auto", "🛺"),
    ("ola", "Ola cab", "🚗"),
    ("uber", "Uber cab", "🚕"),
    ("taxi", "Black taxi", "🚖"),
]


def compare(origin: tuple[float, float], destination: tuple[float, float],
            travelers: int = 1) -> list[dict[str, Any]]:
    """All 8 modes sorted cheapest-first, per-person fares × vehicle sharing."""
    vehicles = transport.vehicles_for(travelers)
    rows: list[dict[str, Any]] = []
    for mode, label, icon in MODE_META:
        est = transport.estimate(origin, destination, mode=mode)
        rows.append({
            "mode": mode,
            "label": label,
            "icon": icon,
            "distance_km": est["distance_km"],
            "duration_min": est["duration_min"],
            "fare_inr": est["estimated_fare_inr"] * vehicles,
            "data_status": est["data_status"],
        })
    rows.sort(key=lambda r: r["fare_inr"])
    return rows
