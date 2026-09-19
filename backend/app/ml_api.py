"""ML API routes — /api/ml/*.

Every response honestly reports which system produced it
(`model_used`: random_forest / gradient_boosting / rule_based_demo / heuristic_demo).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .ml import itinerary as itinerary_opt
from .ml import safety_model
from .ml.predictor import (
    predict_safety,
    recommendation_status,
    recommend_places,
    safety_status,
)
from .schemas import MlItineraryRequest, MlRecommendRequest, MlSafetyRequest

router = APIRouter(prefix="/api/ml", tags=["ml"])


@router.post("/safety-predict")
async def ml_safety_predict(req: MlSafetyRequest) -> dict[str, Any]:
    """Contextual Travel Risk Score (0–100) from structured context.

    This is a decision-support indicator, not an accident probability.
    """
    return predict_safety(req.model_dump())


@router.post("/recommend")
async def ml_recommend(req: MlRecommendRequest) -> dict[str, Any]:
    """Rank places for the given user preferences (interests, budget, time)."""
    return recommend_places(req.places, req.user_preferences)


@router.post("/itinerary")
async def ml_itinerary(req: MlItineraryRequest) -> dict[str, Any]:
    """ML-ranked places → deterministic feasibility-filtered itinerary + costs."""
    prefs = req.user_preferences
    ranked = recommend_places(req.places, prefs)
    plan = itinerary_opt.build_itinerary(
        ranked["places"],
        available_hours=float(prefs.get("available_hours", 6) or 6),
        budget=float(prefs.get("budget", 2000) or 2000),
        interests=[str(i) for i in (prefs.get("interests") or [])],
    )
    return {
        "ranking_model": ranked["ranking_model"],
        "model_version": ranked["model_version"],
        "ranked_places": ranked["places"],
        "itinerary": plan,
    }


@router.get("/info")
async def ml_info() -> dict[str, Any]:
    """What is actually active right now — for the intelligence panel."""
    safety = safety_status()
    rec = recommendation_status()
    return {
        "safety_model": safety,
        "recommendation_model": rec,
        "features": safety_model.FEATURE_NAMES,
        "transparency": {
            "score_meaning": "Contextual Travel Risk Score (0–100) — decision support, not an accident probability",
            "dataset_type": "synthetic demonstration data",
        },
    }
