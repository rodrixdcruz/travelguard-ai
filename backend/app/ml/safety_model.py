"""Contextual Travel Risk model (RandomForest regression).

Predicts a 0–100 *contextual travel risk score* — a decision-support
indicator, NOT a probability of accidents. Trained on the documented
synthetic demonstration dataset (see data/ml/README.md).
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from .dataset import load_columns
from .features import FEATURE_NAMES

TARGET = "risk_score"
MODEL_VERSION = "0.1-demo"
DATASET_TYPE = "synthetic"


def build_model() -> RandomForestRegressor:
    """Small, fast forest suitable for a hackathon MVP."""
    return RandomForestRegressor(
        n_estimators=220,
        max_depth=14,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )


def load_dataset(csv_path: str | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Load and validate the CSV, returning (X, y) as numpy arrays."""
    cols = load_columns(csv_path)
    missing = [c for c in FEATURE_NAMES + [TARGET] if c not in cols]
    if missing:
        raise ValueError(f"Training data missing columns: {missing}")
    X = np.column_stack([cols[name] for name in FEATURE_NAMES])
    y = cols[TARGET]
    return X, y


def train(csv_path: str | None = None) -> dict:
    """Train, evaluate on a held-out split, and return everything needed to persist."""
    from .model_store import save_with_metadata, SAFETY_MODEL_PATH, SAFETY_META_PATH

    X, y = load_dataset(csv_path)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

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
        "model_version": MODEL_VERSION,
        "dataset_type": DATASET_TYPE,
        "target": TARGET,
        "features": FEATURE_NAMES,
        "metrics": metrics,
    }
    save_with_metadata(model, metadata, SAFETY_MODEL_PATH, SAFETY_META_PATH)
    return {"model": model, "metadata": metadata}


def evaluate(model: RandomForestRegressor, csv_path: str | None = None) -> dict:
    """Recompute metrics on a fresh holdout (used by evaluate.py)."""
    X, y = load_dataset(csv_path)
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    y_pred = model.predict(X_test)
    return {
        "mae": round(float(mean_absolute_error(y_test, y_pred)), 3),
        "r2": round(float(r2_score(y_test, y_pred)), 3),
    }


def feature_importance(model: RandomForestRegressor) -> list[dict]:
    """Genuine RandomForest impurity-based importances (labeled as such downstream)."""
    return sorted(
        (
            {"feature": name, "importance": round(float(imp), 4)}
            for name, imp in zip(FEATURE_NAMES, model.feature_importances_)
        ),
        key=lambda d: d["importance"],
        reverse=True,
    )


def level_from_score(score: float) -> str:
    """Shared 0–100 → band mapping, consistent with the rule engine."""
    if score >= 75:
        return "CRITICAL"
    if score >= 55:
        return "HIGH"
    if score >= 35:
        return "MODERATE"
    return "LOW"
