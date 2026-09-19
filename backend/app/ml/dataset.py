"""Synthetic demonstration dataset generator (deterministic, fixed seed).

⚠️ TRANSPARENCY: this dataset is SYNTHETIC. It demonstrates the ML pipeline
with plausible feature relationships. It is NOT a validated real-world
safety dataset and must never be presented as one. See data/ml/README.md.

Implemented with numpy only (no pandas) to keep the backend lightweight.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .features import FEATURE_NAMES

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "ml"
CSV_PATH = DATA_DIR / "training_data.csv"

# FEATURE_NAMES + target, in column order.
COLUMNS = [*FEATURE_NAMES, "risk_score"]


def generate(n: int = 6000, seed: int = 42) -> dict[str, np.ndarray]:
    """Create realistic-but-synthetic columns via conditional sampling."""
    rng = np.random.default_rng(seed)
    n = int(n)

    # Latent "severity" drives correlated weather features, like real weather.
    severity = rng.beta(2.0, 5.0, n)  # most days calm
    weather_severity = severity * 100

    rainy = rng.random(n) < (0.15 + 0.55 * severity)
    rain_intensity = np.where(rainy, rng.gamma(2.0, 4.0, n).clip(0, 60), 0.0)

    base_vis = rng.normal(9.0, 2.0, n)
    visibility = np.clip(base_vis - rain_intensity * 0.12 - severity * 3.0, 0.1, 20.0)

    wind_severity = np.clip(rng.gamma(1.5, 8.0, n) + severity * 25, 0, 100)

    night = rng.binomial(1, 0.28, n).astype(float)

    disruption = np.clip(
        np.where(rng.random(n) < 0.18, rng.uniform(30, 95, n), rng.uniform(0, 20, n)), 0, 100
    )

    incident_density = np.clip(rng.gamma(1.8, 0.5, n) + severity * 0.8, 0.0, 6.0)

    hospital_km = np.clip(rng.gamma(2.0, 4.0, n), 0.3, 60.0)
    service_density = np.clip(rng.normal(5.0, 2.2, n), 0.0, 10.0)
    tourist_area = rng.binomial(1, 0.4, n).astype(float)
    activity = np.clip(rng.normal(5.0 + 2.0 * tourist_area, 2.0, n), 0.0, 10.0)
    route_condition = np.clip(rng.normal(70.0, 18.0, n) - disruption * 0.15, 0.0, 100.0)
    time_of_day = np.where(night > 0.5, 2.0, rng.choice([2.0, 4.0, 8.0], n, p=[0.3, 0.45, 0.25]))

    cols: dict[str, np.ndarray] = {
        "weather_severity": weather_severity.round(2),
        "rain_intensity": rain_intensity.round(2),
        "visibility": visibility.round(2),
        "wind_severity": wind_severity.round(2),
        "night_indicator": night,
        "road_disruption": disruption.round(2),
        "historical_incident_density": incident_density.round(3),
        "distance_to_emergency_service": hospital_km.round(2),
        "nearby_service_density": service_density.round(2),
        "tourist_area_indicator": tourist_area,
        "area_activity_level": activity.round(2),
        "route_condition": route_condition.round(2),
        "time_of_day": time_of_day,
    }

    # Ground-truth rule: a plausible risk relationship the model can learn,
    # plus heteroscedastic noise so it isn't a trivially separable function.
    noise_scale = 3.0 + 4.0 * severity
    risk = (
        6.0
        + 0.20 * cols["weather_severity"]
        + 0.30 * cols["rain_intensity"].clip(0, 30)
        + 2.0 * np.clip(8.0 - cols["visibility"], 0, None)
        + 0.08 * cols["wind_severity"]
        + 15.0 * cols["night_indicator"]
        + 0.16 * cols["road_disruption"]
        + 5.0 * np.clip(cols["historical_incident_density"], None, 4)
        + 0.25 * np.clip(cols["distance_to_emergency_service"], None, 40)
        - 0.7 * cols["nearby_service_density"]
        + 1.5 * cols["tourist_area_indicator"]
        + 0.4 * cols["area_activity_level"]
        - 0.10 * (cols["route_condition"] - 50.0)
        + 0.5 * cols["time_of_day"]
        + rng.normal(0.0, noise_scale, n)
    )
    cols["risk_score"] = risk.clip(0, 100).round(1)
    return cols


def _write_csv(cols: dict[str, np.ndarray], path: Path) -> None:
    n = len(next(iter(cols.values())))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for i in range(n):
            writer.writerow([cols[c][i] for c in COLUMNS])


def ensure_csv(force: bool = False, n: int = 6000) -> Path:
    """Write the CSV if absent (or force=True). Deterministic across runs."""
    if force or not CSV_PATH.exists():
        _write_csv(generate(n=n), CSV_PATH)
    return CSV_PATH


def load_columns(path: Path | str | None = None) -> dict[str, np.ndarray]:
    """Read the training CSV into numpy columns, validating required fields."""
    p = Path(path) if path else ensure_csv()
    with p.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        raise ValueError(f"Training data is empty: {p}")
    missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"Training data missing columns: {missing}")
    return {c: np.array([float(r[c]) for r in rows]) for c in COLUMNS}
