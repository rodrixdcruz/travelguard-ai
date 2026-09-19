"""ML layer tests — feature extraction, prediction, ranking, fallback, optimizer."""
from __future__ import annotations

import math

import pytest

from app.ml import predictor
from app.ml.features import FEATURE_NAMES, safety_features, vectorize
from app.ml.itinerary import build_itinerary
from app.ml.predictor import predict_safety, recommend_places, safety_status
from app.ml.recommendation_model import place_features
from app.ml.safety_model import level_from_score


LOW_INPUT = {
    "weather": {"condition": "Clear", "precip_mm": 0, "visibility_km": 12, "wind_kph": 5},
    "context": {"hour": 14, "tourist_area": True, "activity_level": 6},
    "location": {"incident_density": 0.2, "nearest_hospital_km": 1.5, "service_density": 8},
    "road": {"type": "expressway", "surface": "good"},
}

HIGH_INPUT = {
    "weather": {"condition": "Heavy Rain", "precip_mm": 35, "visibility_km": 1.2, "wind_kph": 45},
    "context": {"hour": 2, "tourist_area": False, "activity_level": 2},
    "location": {"incident_density": 2.8, "nearest_hospital_km": 30, "service_density": 1},
    "road": {"type": "ghat", "surface": "poor"},
}


# ── Feature pipeline ────────────────────────────────────────────────────

def test_features_full_ordered_vector():
    f = safety_features(LOW_INPUT)
    assert list(f.keys()) == FEATURE_NAMES
    assert all(isinstance(v, float) for v in f.values())
    row = vectorize(f)
    assert len(row) == 1 and len(row[0]) == len(FEATURE_NAMES)


def test_features_never_throw_on_missing_payload():
    f = safety_features({})
    assert list(f.keys()) == FEATURE_NAMES
    assert all(v >= 0 for v in f.values())


def test_weather_severity_orders_by_condition():
    calm = safety_features({"weather": {"condition": "Clear"}})["weather_severity"]
    storm = safety_features({"weather": {"condition": "Thunderstorm"}})["weather_severity"]
    assert storm > calm


def test_night_indicator_from_hour():
    assert safety_features({"context": {"hour": 23}})["night_indicator"] == 1.0
    assert safety_features({"context": {"hour": 13}})["night_indicator"] == 0.0


# ── Risk level bands ────────────────────────────────────────────────────

def test_level_bands():
    assert level_from_score(10) == "LOW"
    assert level_from_score(40) == "MODERATE"
    assert level_from_score(60) == "HIGH"
    assert level_from_score(90) == "CRITICAL"


# ── Prediction ──────────────────────────────────────────────────────────

def test_high_risk_input_scores_higher_than_low():
    low = predict_safety(LOW_INPUT)
    high = predict_safety(HIGH_INPUT)
    assert 0.0 <= low["risk_score"] <= 100.0
    assert 0.0 <= high["risk_score"] <= 100.0
    assert high["risk_score"] > low["risk_score"]


def test_prediction_reports_model_used():
    result = predict_safety(LOW_INPUT)
    assert result["model_used"] in ("random_forest", "rule_based_demo")
    assert result["model_version"]
    assert isinstance(result["factors"], list)


def test_high_input_mentions_weather_or_night_factors():
    factors = {f["label"] for f in predict_safety(HIGH_INPUT)["factors"]}
    assert factors & {"Weather severity", "Night travel", "Rainfall", "Low visibility"}


# ── Fallback behavior ───────────────────────────────────────────────────

def test_rule_fallback_matches_rule_engine_direction(monkeypatch):
    """With the artifact removed, the fallback still orders low < high."""
    monkeypatch.setattr(predictor, "_safety", None)
    low = predict_safety(LOW_INPUT)
    high = predict_safety(HIGH_INPUT)
    assert low["model_used"] == "rule_based_demo"
    assert high["model_used"] == "rule_based_demo"
    assert high["risk_score"] > low["risk_score"]


def test_safety_status_reports_kind():
    status = safety_status()
    assert status["active"] is True
    assert status["kind"] in ("ml", "rules")
    if status["kind"] == "ml":
        assert status["model_used"] == "random_forest"
    else:
        assert status["model_used"] == "rule_based_demo"


# ── Recommendation ranking ──────────────────────────────────────────────

PLACES = [
    {
        "place_id": "fort", "name": "Old Fort", "category": "history",
        "tags": ["history", "culture"], "distance_km": 3, "estimated_cost": 100,
        "popularity": 85, "visit_duration_hours": 2, "is_open": True, "safety_context": 85,
    },
    {
        "place_id": "mall", "name": "Big Mall", "category": "shopping",
        "tags": ["shopping"], "distance_km": 15, "estimated_cost": 1900,
        "popularity": 55, "visit_duration_hours": 4, "is_open": True, "safety_context": 70,
    },
    {
        "place_id": "park", "name": "Lake Park", "category": "nature",
        "tags": ["nature", "photography"], "distance_km": 6, "estimated_cost": 0,
        "popularity": 70, "visit_duration_hours": 1.5, "is_open": False, "safety_context": 80,
    },
]

HISTORY_PREFS = {"interests": ["history"], "budget": 2000, "available_hours": 6}


def test_interest_match_feature():
    f = place_features(PLACES[0], HISTORY_PREFS)
    assert f["interest_match"] == 1.0
    assert f["fits_budget"] == 1.0


def test_ranking_prefers_matching_place():
    ranked = recommend_places(PLACES, HISTORY_PREFS)
    top = ranked["places"][0]
    assert top["place_id"] == "fort"
    assert top["recommendation_score"] >= ranked["places"][1]["recommendation_score"]
    assert any("interest" in r.lower() for r in top["reasons"])


def test_ranking_reports_model_honestly():
    ranked = recommend_places(PLACES, HISTORY_PREFS)
    assert ranked["ranking_model"] in ("gradient_boosting", "heuristic_demo")
    assert all(p["ranking_model"] == ranked["ranking_model"] for p in ranked["places"])


# ── Itinerary optimizer ────────────────────────────────────────────────

def test_optimizer_respects_time_and_budget():
    ranked = recommend_places(PLACES, HISTORY_PREFS)
    plan = build_itinerary(ranked["places"], available_hours=3.0, budget=500, interests=["history"])
    assert plan["summary"]["used_hours"] <= 3.0 + 1e-9
    assert plan["cost_breakdown"]["tickets"] <= 500
    assert len(plan["stops"]) >= 1
    names = {s["name"] for s in plan["stops"]}
    assert "Lake Park" not in names  # closed → skipped
    assert any(s["why"] for s in plan["skipped"])


def test_optimizer_cost_breakdown_adds_up():
    ranked = recommend_places(PLACES, HISTORY_PREFS)
    plan = build_itinerary(ranked["places"], available_hours=6.0, budget=5000, interests=["history"])
    cb = plan["cost_breakdown"]
    assert math.isclose(cb["total_estimate"], cb["tickets"] + cb["food_estimate"] + cb["transport_estimate"], abs_tol=0.11)


# ── End-to-end blend through the main analysis path ─────────────────────

def test_analyze_journey_uses_ml_and_reports_mode():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/analyze-journey",
        json={"origin": "Mumbai", "destination": "Pune", "date": "2026-09-20", "time": "22:00"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intelligence_mode"] in ("random_forest", "rule_based_demo")
    for seg in body["segments"]:
        assert seg["ml_model_used"] in ("random_forest", "rule_based_demo")
        assert seg["ml_score"] is not None


# ── ML API contract ─────────────────────────────────────────────────────

def test_ml_safety_predict_endpoint():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post("/api/ml/safety-predict", json=HIGH_INPUT)
    assert resp.status_code == 200
    body = resp.json()
    assert {"risk_score", "risk_level", "model_used", "model_version"} <= set(body)
    assert 0 <= body["risk_score"] <= 100


def test_ml_recommend_endpoint():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/ml/recommend",
        json={"user_preferences": HISTORY_PREFS, "places": PLACES},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ranking_model"] in ("gradient_boosting", "heuristic_demo")
    assert [p["recommendation_score"] for p in body["places"]] == sorted(
        [p["recommendation_score"] for p in body["places"]], reverse=True
    )


def test_ml_info_endpoint():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/ml/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["safety_model"]["active"] and body["recommendation_model"]["active"]
    assert "synthetic" in body["transparency"]["dataset_type"]


def test_health_still_works():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
