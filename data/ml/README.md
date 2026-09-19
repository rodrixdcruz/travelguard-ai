# ML Training Data

**`training_data.csv` is SYNTHETIC and exists to demonstrate the ML pipeline.
It is NOT a validated real-world safety dataset.**

- Generated deterministically by `backend/app/ml/dataset.py` (fixed seed 42).
- Regenerate: `python -m app.ml.train` (creates the file if missing) or
  `python -c "from app.ml.dataset import ensure_csv; ensure_csv(force=True)"`.
- 6,000 rows × 14 columns (13 features + `risk_score` target).
- Feature relationships are plausible but invented: a latent "severity" factor
  drives correlated weather columns; the target is a transparent weighted rule
  plus heteroscedastic noise — so the model learns real structure, but the
  structure itself is a design choice, not measured reality.
- The score it trains is the **Contextual Travel Risk Score** (0–100), a
  decision-support indicator. It is **not** a probability of accidents.

## Columns

| Column | Range | Meaning |
|---|---|---|
| `weather_severity` | 0–100 | Overall weather harshness |
| `rain_intensity` | 0–60 mm | Precipitation intensity |
| `visibility` | 0.1–20 km | Estimated visibility |
| `wind_severity` | 0–100 | Wind risk above calm baseline |
| `night_indicator` | 0/1 | Travel between 22:00–06:00 |
| `road_disruption` | 0–100 | Active disruption impact |
| `historical_incident_density` | 0–6 /km-yr | Historical incident rate (synthetic) |
| `distance_to_emergency_service` | 0.3–60 km | Distance to nearest hospital |
| `nearby_service_density` | 0–10 | Local services density |
| `tourist_area_indicator` | 0/1 | Tourist-area flag |
| `area_activity_level` | 0–10 | Current activity level |
| `route_condition` | 0–100 | Road quality/alignment |
| `time_of_day` | 2/4/8 | Traffic-exposure encoding |
| `risk_score` | 0–100 | **Target** — contextual travel risk |
