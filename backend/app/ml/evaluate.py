"""Evaluate trained model artifacts on a held-out split of the dataset.

Usage:
    python -m app.ml.evaluate [path/to/training_data.csv]

If no path is given, the dataset is generated deterministically (identical
to training data) and evaluated. Never fabricates metrics — everything is
recomputed with sklearn.
"""
from __future__ import annotations

import json
import sys

from .model_store import SAFETY_META_PATH, SAFETY_MODEL_PATH, load_with_metadata


def main(csv_path: str | None = None) -> int:
    from .dataset import ensure_csv
    from .safety_model import evaluate, feature_importance

    path = csv_path or str(ensure_csv())
    loaded = load_with_metadata(SAFETY_MODEL_PATH, SAFETY_META_PATH)
    if loaded is None:
        print("No trained safety model found. Run: python -m app.ml.train")
        return 1
    model, meta = loaded

    metrics = evaluate(model, path)
    print("── Safety model evaluation ──")
    print(f"model_version : {meta.get('model_version')}")
    print(f"dataset_type  : {meta.get('dataset_type')} (synthetic demonstration data)")
    print(f"MAE           : {metrics['mae']}  (score points, 0–100 scale)")
    print(f"R²            : {metrics['r2']}")
    print("Model feature importance (top 8):")
    for row in feature_importance(model)[:8]:
        print(f"  {row['feature']:<34} {row['importance']:.4f}")

    print(json.dumps({"metrics": metrics, "model_version": meta.get("model_version")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
