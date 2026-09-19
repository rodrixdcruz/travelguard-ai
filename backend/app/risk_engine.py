"""Deterministic risk scoring engine.

Pure functions: same inputs always produce the same outputs. No randomness,
no network calls. All factors are derived from the journey context and the
demo dataset so every score is explainable.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from .schemas import Coordinate, RiskLevel, SegmentFactor


# ── Public helpers ──────────────────────────────────────────────────────

def level_from_score(score: float) -> RiskLevel:
    if score >= 75:
        return RiskLevel.CRITICAL
    if score >= 55:
        return RiskLevel.HIGH
    if score >= 35:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


# ── Factor scorers (0..100 each) ────────────────────────────────────────

def weather_score(conditions: dict[str, Any]) -> tuple[float, str]:
    """Score from demo weather conditions."""
    cond = str(conditions.get("condition", "Clear")).lower()
    visibility_km = float(conditions.get("visibility_km", 10.0))
    wind_kph = float(conditions.get("wind_kph", 8.0))

    base = 5.0
    if "thunder" in cond:
        base, why = 88.0, "Thunderstorm activity in the area"
    elif "rain" in cond:
        intensity = float(conditions.get("precip_mm", 0.0))
        base = 40.0 + min(intensity * 9.0, 40.0)
        why = f"Rainfall ({conditions.get('precip_mm', 0)} mm) reduces grip and visibility"
    elif "fog" in cond or "mist" in cond:
        base = 55.0 + max(0.0, (5.0 - visibility_km)) * 6.0
        why = f"Fog with visibility around {visibility_km} km"
    elif "clear" in cond:
        base, why = 5.0, "Clear skies, good visibility"
    else:
        why = f"Conditions reported as {conditions.get('condition')}"

    if visibility_km < 4.0 and base < 55.0:
        base, why = 60.0, f"Low visibility ({visibility_km} km)"
    base += min(max(wind_kph - 25.0, 0.0) * 0.8, 12.0)
    return clamp_score(base), why


def accident_score(history: dict[str, Any]) -> tuple[float, str]:
    """Score from historical accident density for the stretch."""
    density = float(history.get("accidents_per_km_year", 0.4))
    severity = float(history.get("severity_index", 3.0))  # 1..10
    score = 8.0 + density * 26.0 + (severity - 3.0) * 6.0
    why = (
        f"Historical accident density {density}/km-yr with severity index {severity}/10"
        if density >= 1.0 or severity >= 6.0
        else "Accident history within normal range for highways"
    )
    return clamp_score(score), why


def road_score(road: dict[str, Any]) -> tuple[float, str]:
    """Score from road condition / type."""
    rtype = str(road.get("type", "highway")).lower()
    surface = str(road.get("surface", "good")).lower()
    lighting = str(road.get("lighting", "none")).lower()

    type_base = {"highway": 25.0, "expressway": 12.0, "ghat": 62.0, "rural": 48.0, "urban": 30.0}
    surface_mult = {"good": 1.0, "fair": 1.25, "poor": 1.6}
    score = type_base.get(rtype, 35.0) * surface_mult.get(surface, 1.2)
    if lighting == "none" and rtype in ("ghat", "rural"):
        score += 8.0
    if rtype == "ghat":
        why = "Ghat section: sharp curves and steep gradient"
    elif surface == "poor":
        why = "Poor surface quality increases loss-of-control risk"
    else:
        why = f"{rtype.capitalize()} road in {surface} condition"
    return clamp_score(score), why


def disruption_score(disruptions: list[dict[str, Any]]) -> tuple[float, str]:
    """Score from active disruptions along the stretch."""
    if not disruptions:
        return 5.0, "No active disruptions reported"
    worst = 0.0
    reasons: list[str] = []
    for d in disruptions:
        impact = float(d.get("impact", 40.0))
        worst = max(worst, impact)
        reasons.append(str(d.get("description", "Disruption reported")))
    return clamp_score(worst), "; ".join(reasons[:2])


def time_score(travel_dt: datetime) -> tuple[float, str]:
    """Score from time of day / day of week context."""
    hour = travel_dt.hour
    weekday = travel_dt.weekday()  # 0 = Mon
    night = hour >= 22 or hour < 6
    score = 8.0
    if night:
        score += 34.0
    elif hour in (8, 9, 10, 17, 18, 19):
        score += 18.0
    if weekday == 4:  # Friday evening rush
        score += 6.0
    if weekday in (5, 6):  # weekend leisure traffic
        score += 5.0
    if night:
        why = f"Night travel at {hour:02d}:00 sharply reduces reaction margins"
    elif hour in (8, 9, 10, 17, 18, 19):
        why = f"Peak traffic window around {hour:02d}:00 raises incident likelihood"
    else:
        why = "Travel window carries typical traffic exposure"
    return clamp_score(score), why


# ── Aggregation ─────────────────────────────────────────────────────────

WEIGHTS = {
    "weather": 0.30,
    "accident": 0.22,
    "road": 0.24,
    "disruption": 0.14,
    "time": 0.10,
}


def aggregate(factors: list[SegmentFactor]) -> float:
    total = sum(f.weight for f in factors) or 1.0
    return clamp_score(sum(f.score * f.weight for f in factors) / total)


def overall_from_segments(
    segments: list[Any],  # list[Segment], kept loose to avoid a circular import
) -> tuple[float, str]:
    """Journey-level score: worst segments dominate but average matters."""
    if not segments:
        return 0.0, "No segments analyzed"
    avg = sum(s.score for s in segments) / len(segments)
    worst = max(s.score for s in segments)
    score = clamp_score(avg * 0.55 + worst * 0.45)
    level = level_from_score(score)
    worst_seg = max(segments, key=lambda s: s.score)
    concern = f"{worst_seg.name}: {worst_seg.factors[0].reason}" if worst_seg.factors else worst_seg.name
    return score, f"{level.value} risk driven by {concern}"


def main_concern_from_factors(segments: list[Any]) -> str:
    worst = max(segments, key=lambda s: s.score) if segments else None
    if not worst:
        return "No significant concerns identified"
    heavy = [f.reason for f in worst.factors if f.score >= 50.0]
    return "; ".join(heavy[:2]) if heavy else worst.factors[0].reason if worst.factors else worst.name


def segment_recommended_action(level: RiskLevel, factors: list[SegmentFactor]) -> str:
    categories = {f.category for f in factors if f.score >= 50.0}
    if level == RiskLevel.CRITICAL:
        return "Consider postponing travel or taking an alternate route entirely."
    if "weather" in categories and "road" in categories:
        return "Reduce speed, double following distance, and use low beams through this stretch."
    if "weather" in categories:
        return "Slow down and increase following distance; conditions change quickly here."
    if "road" in categories:
        return "Keep to lane discipline and brake before curves on this stretch."
    if "disruption" in categories:
        return "Expect delays and follow posted diversion signs."
    if level == RiskLevel.HIGH:
        return "Stay alert, maintain steady speed, and avoid overtaking."
    if level == RiskLevel.MODERATE:
        return "Normal caution; scan ahead and keep safe gaps."
    return "Conditions look good. Maintain regular safe driving habits."
