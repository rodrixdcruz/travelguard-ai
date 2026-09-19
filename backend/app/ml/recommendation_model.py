"""Tourist-place recommendation: lightweight learned ranking.

A small GradientBoostingRegressor learns a preference score from synthetic
pairwise-style training examples (which place a traveler would pick given
context). Deterministic, fast, and honest: this is a ranking heuristic
learned from data, not a deep recommender. Numpy-only (no pandas).
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from .model_store import MODELS_DIR

REC_MODEL_PATH = MODELS_DIR / "recommender_gb_v0_1.joblib"
REC_META_PATH = MODELS_DIR / "recommender_gb_v0_1.meta.json"
REC_MODEL_VERSION = "0.1-demo"

REC_FEATURES = [
    "distance_km",
    "estimated_cost",
    "popularity",
    "interest_match",
    "available_time_hours",
    "visit_duration_hours",
    "fits_time",
    "fits_budget",
    "is_open",
    "safety_context",
    "category_match",
    "budget_ratio",
]


def build_model() -> GradientBoostingRegressor:
    return GradientBoostingRegressor(
        n_estimators=160, max_depth=4, learning_rate=0.08, random_state=42
    )


# ── Single place + user context → feature vector ────────────────────────

def _interest_overlap(interests: list[str], place_tags: list[str]) -> float:
    if not interests:
        return 0.5
    inter = set(i.lower() for i in interests) & set(t.lower() for t in place_tags)
    return len(inter) / max(len(set(interests)), 1)


def place_features(place: dict[str, Any], prefs: dict[str, Any]) -> dict[str, float]:
    """Feature vector for one (place, user-context) pair. Missing → neutral."""
    interests = prefs.get("interests") or []
    budget = float(prefs.get("budget", 2000) or 2000)
    available = float(prefs.get("available_hours", 6) or 6)

    distance = float(place.get("distance_km", 5.0) or 5.0)
    cost = float(place.get("estimated_cost", 0) or 0)
    popularity = float(place.get("popularity", 50) or 50)
    duration = float(place.get("visit_duration_hours", 1.5) or 1.5)
    safety = float(place.get("safety_context", 70) or 70)
    is_open = 1.0 if place.get("is_open", True) else 0.0
    category = str(place.get("category", "")).lower()
    tags = [category] + [str(t).lower() for t in (place.get("tags") or [])]

    interest_match = _interest_overlap(interests, tags)
    category_match = 1.0 if any(category == str(i).lower() for i in interests) else interest_match

    return {
        "distance_km": distance,
        "estimated_cost": cost,
        "popularity": popularity,
        "interest_match": interest_match,
        "available_time_hours": available,
        "visit_duration_hours": duration,
        "fits_time": 1.0 if duration <= available else 0.0,
        "fits_budget": 1.0 if cost <= budget else 0.0,
        "is_open": is_open,
        "safety_context": safety,
        "category_match": category_match,
        "budget_ratio": round(cost / max(budget, 1.0), 3),
    }


def vectorize_row(f: dict[str, float]) -> list[float]:
    return [f[name] for name in REC_FEATURES]


# ── Training data synthesis (documented as synthetic) ───────────────────

def synth_matrix(n: int = 4000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic preference examples.

    Label construction: a plausible 'would-visit score' combining interest
    match, time/budget feasibility, distance decay, popularity and safety —
    with the seeded noise a real preference label would have.
    Returns (X, y) with X columns ordered as REC_FEATURES.
    """
    rng = np.random.default_rng(seed)
    n = int(n)

    distance = np.clip(rng.gamma(2.0, 3.0, n), 0.2, 40)
    cost = rng.choice([0, 20, 50, 100, 250, 500, 1000, 2000], n).astype(float)
    popularity = rng.uniform(5, 100, n)
    interest_match = rng.beta(2, 2, n)
    available = rng.choice([2, 3, 4, 6, 8, 12], n).astype(float)
    duration = np.clip(rng.gamma(2.0, 1.0, n), 0.5, 8)
    is_open = rng.binomial(1, 0.8, n).astype(float)
    safety = rng.uniform(20, 100, n)
    budget = rng.choice([500, 1000, 2000, 5000], n).astype(float)
    category_match = (rng.random(n) < interest_match * 0.9).astype(float)

    X = np.column_stack(
        [
            distance,
            cost,
            popularity,
            interest_match,
            available,
            duration,
            (duration <= available).astype(float),
            (cost <= budget).astype(float),
            is_open,
            safety,
            category_match,
            np.clip(cost / budget, 0, 3),
        ]
    )

    score = (
        62 * interest_match
        + 14 * category_match
        + 18 * (popularity / 100)
        + 12 * np.exp(-distance / 8.0)
        + 10 * X[:, 6]   # fits_time
        + 8 * X[:, 7]    # fits_budget
        + 8 * is_open
        + 6 * (safety / 100)
        - 10 * np.clip(X[:, 11], 0, 2)  # budget_ratio
        + rng.normal(0, 4, n)
    )
    return X, np.clip(score, 0, 100)


def train(model_dir: MODELS_DIR | None = None) -> dict:  # type: ignore[valid-type]
    from .model_store import save_with_metadata

    X, y = synth_matrix()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = build_model()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    metrics = {
        "mae": round(float(mean_absolute_error(y_test, y_pred)), 3),
        "r2": round(float(r2_score(y_test, y_pred)), 3),
        "test_rows": int(len(y_test)),
        "train_rows": int(len(y_train)),
    }
    metadata = {
        "model_version": REC_MODEL_VERSION,
        "dataset_type": "synthetic",
        "features": REC_FEATURES,
        "metrics": metrics,
    }
    out_dir = model_dir or MODELS_DIR
    save_with_metadata(
        model,
        metadata,
        out_dir / REC_MODEL_PATH.name,
        out_dir / REC_META_PATH.name,
    )
    return {"model": model, "metadata": metadata}


# ── Scoring + reasons ───────────────────────────────────────────────────

def score_place(model: Any, place: dict[str, Any], prefs: dict[str, Any]) -> dict[str, Any]:
    f = place_features(place, prefs)
    raw = float(model.predict([vectorize_row(f)])[0])
    score = round(max(0.0, min(raw, 100.0)), 1)

    reasons: list[str] = []
    if f["interest_match"] >= 0.5:
        reasons.append("Matches your interests")
    if f["category_match"] >= 1.0 and f["interest_match"] < 0.5:
        reasons.append("Similar to your interests")
    if f["fits_budget"] >= 1.0 and f["budget_ratio"] <= 0.5:
        reasons.append("Well within budget")
    elif f["fits_budget"] >= 1.0:
        reasons.append("Within budget")
    if f["distance_km"] <= 5:
        reasons.append("Nearby")
    if f["fits_time"] >= 1.0 and f["is_open"] >= 1.0:
        reasons.append("Open during your available time")
    if f["safety_context"] >= 70:
        reasons.append("In a well-rated safety area")
    if f["popularity"] >= 75:
        reasons.append("Popular with travelers")
    if not reasons:
        reasons.append("Worth a look given your context")

    return {
        "recommendation_score": score,
        "reasons": reasons[:4],
        "features": f,
    }


def feature_importance(model: Any) -> list[dict]:
    return sorted(
        (
            {"feature": name, "importance": round(float(imp), 4)}
            for name, imp in zip(REC_FEATURES, model.feature_importances_)
        ),
        key=lambda d: d["importance"],
        reverse=True,
    )
