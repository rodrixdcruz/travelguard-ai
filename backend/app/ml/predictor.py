"""Inference layer — the only module the API talks to.

Loads model artifacts once at first use; every call degrades gracefully to
the deterministic rule engine when a model is missing or fails. The
`model_used` field always tells the truth about which system produced a score.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from . import recommendation_model as rec
from . import safety_model
from .features import describe_factors, safety_features, vectorize
from .safety_model import level_from_score  # plain-str bands, mirrors risk_engine
from .model_store import (
    SAFETY_META_PATH,
    SAFETY_MODEL_PATH,
    load_with_metadata,
)

logger = logging.getLogger("travelguard.ml")

_safety: Optional[tuple[Any, dict[str, Any]]] = None
_recommender: Optional[tuple[Any, dict[str, Any]]] = None
_LOADED = False


def _load() -> None:
    global _safety, _recommender, _LOADED
    if _LOADED:
        return
    _LOADED = True
    _safety = load_with_metadata(SAFETY_MODEL_PATH, SAFETY_META_PATH)
    _recommender = load_with_metadata(rec.REC_MODEL_PATH, rec.REC_META_PATH)
    if _safety is None:
        logger.info("Safety model artifact not found — rule-based fallback active.")
    if _recommender is None:
        logger.info("Recommender artifact not found — heuristic ranking active.")


def reload_models() -> None:
    """Force reload (used after training from the demo panel)."""
    global _LOADED
    _LOADED = False
    _load()


# ── Safety prediction ───────────────────────────────────────────────────

def predict_safety(payload: dict[str, Any]) -> dict[str, Any]:
    """Predict contextual travel risk from structured input.

    Returns the API contract:
    { risk_score, risk_level, model_used, model_version, factors, model_features }
    """
    _load()
    features = safety_features(payload)
    factors = describe_factors(features)

    if _safety is not None:
        model, meta = _safety
        try:
            raw = float(model.predict(vectorize(features))[0])
            score = round(max(0.0, min(raw, 100.0)), 1)
            return {
                "risk_score": score,
                "risk_level": level_from_score(score),
                "model_used": "random_forest",
                "model_version": str(meta.get("model_version", safety_model.MODEL_VERSION)),
                "dataset_type": str(meta.get("dataset_type", "synthetic")),
                "factors": factors,
                "model_features": features,
                "feature_importance": safety_model.feature_importance(model)[:5],
            }
        except Exception as exc:
            logger.warning("Safety prediction failed (%s) — using rule fallback.", exc)

    # ── Fallback: deterministic rule engine (kept honest in the response) ──
    score = _rule_based_score(features)
    return {
        "risk_score": score,
        "risk_level": level_from_score(score),
        "model_used": "rule_based_demo",
        "model_version": "rules-0.1",
        "dataset_type": "n/a",
        "factors": factors,
        "model_features": features,
        "feature_importance": [],
    }


def _rule_based_score(f: dict[str, float]) -> float:
    """Transparent linear fallback mirroring the demo dataset's relationships."""
    score = 6.0
    score += f["weather_severity"] * 0.22
    score += f["rain_intensity"] * 0.35
    score += max(0.0, 8.0 - f["visibility"]) * 2.2
    score += f["wind_severity"] * 0.10
    score += f["night_indicator"] * 16.0
    score += f["road_disruption"] * 0.18
    score += f["historical_incident_density"] * 5.5
    score += min(f["distance_to_emergency_service"], 40.0) * 0.30
    score -= f["nearby_service_density"] * 0.8
    score -= (f["route_condition"] - 50.0) * 0.12
    score += f["time_of_day"] * 0.5
    return round(max(0.0, min(score, 100.0)), 1)


def safety_status() -> dict[str, Any]:
    """For the intelligence panel — reports what is ACTUALLY active."""
    _load()
    if _safety is not None:
        _, meta = _safety
        return {
            "active": True,
            "kind": "ml",
            "model_used": "random_forest",
            "model_version": str(meta.get("model_version", "?")),
            "metrics": meta.get("metrics", {}),
            "dataset_type": str(meta.get("dataset_type", "synthetic")),
        }
    return {
        "active": True,
        "kind": "rules",
        "model_used": "rule_based_demo",
        "model_version": "rules-0.1",
        "metrics": {},
        "dataset_type": "n/a",
    }


# ── Recommendations ─────────────────────────────────────────────────────

def recommend_places(places: list[dict[str, Any]], prefs: dict[str, Any]) -> dict[str, Any]:
    """Rank places for a user context. Falls back to a heuristic score."""
    _load()
    scored: list[dict[str, Any]] = []

    if _recommender is not None:
        model, meta = _recommender
        try:
            for place in places:
                result = rec.score_place(model, place, prefs)
                scored.append(
                    {
                        **place,
                        "recommendation_score": result["recommendation_score"],
                        "reasons": result["reasons"],
                        "ranking_model": "gradient_boosting",
                    }
                )
            scored.sort(key=lambda p: p["recommendation_score"], reverse=True)
            return {
                "ranking_model": "gradient_boosting",
                "model_version": str(meta.get("model_version", rec.REC_MODEL_VERSION)),
                "places": scored,
            }
        except Exception as exc:
            logger.warning("Recommendation scoring failed (%s) — heuristic fallback.", exc)

    # Heuristic fallback: transparent weighted score.
    for place in places:
        f = rec.place_features(place, prefs)
        score = (
            f["interest_match"] * 45
            + f["category_match"] * 10
            + (f["popularity"] / 100) * 20
            + 12.0 * (2.718281828 ** (-f["distance_km"] / 8.0))
            + f["fits_time"] * 10
            + f["fits_budget"] * 8
            + f["is_open"] * 8
            + (f["safety_context"] / 100) * 6
            - min(f["budget_ratio"], 2.0) * 10
        )
        score = round(max(0.0, min(score, 100.0)), 1)
        reasons = (
            ["Matches your interests"] if f["interest_match"] >= 0.5 else []
        ) + (["Within budget"] if f["fits_budget"] >= 1.0 else []) + (
            ["Nearby"] if f["distance_km"] <= 5 else []
        )
        scored.append(
            {
                **place,
                "recommendation_score": score,
                "reasons": reasons or ["Worth a look given your context"],
                "ranking_model": "heuristic_demo",
            }
        )
    scored.sort(key=lambda p: p["recommendation_score"], reverse=True)
    return {
        "ranking_model": "heuristic_demo",
        "model_version": "heuristic-0.1",
        "places": scored,
    }


def recommendation_status() -> dict[str, Any]:
    _load()
    if _recommender is not None:
        _, meta = _recommender
        return {
            "active": True,
            "kind": "ml",
            "model_used": "gradient_boosting",
            "model_version": str(meta.get("model_version", "?")),
            "metrics": meta.get("metrics", {}),
        }
    return {
        "active": True,
        "kind": "heuristic",
        "model_used": "heuristic_demo",
        "model_version": "heuristic-0.1",
        "metrics": {},
    }
