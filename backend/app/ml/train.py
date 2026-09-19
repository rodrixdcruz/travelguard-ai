"""Train the TravelGuard ML models.

Usage:
    python -m app.ml.train            # both models
    python -m app.ml.train safety     # safety model only
    python -m app.ml.train recommender

The safety model trains on data/ml/training_data.csv (generated
deterministically if missing — synthetic demonstration data, see
data/ml/README.md). Metrics printed are computed on a real held-out split.
"""
from __future__ import annotations

import sys


def train_all(which: str = "all") -> int:
    from . import recommendation_model, safety_model
    from .dataset import ensure_csv

    if which in ("all", "safety"):
        csv_path = ensure_csv()
        print(f"▸ Training safety model on {csv_path}")
        result = safety_model.train(str(csv_path))
        m = result["metadata"]["metrics"]
        print(f"  ✓ safety_rf_v0_1.joblib  "
              f"MAE={m['mae']}  R²={m['r2']}  "
              f"(train={m['train_rows']} rows, test={m['test_rows']} rows)")
        print(f"    dataset_type={result['metadata']['dataset_type']}  "
              f"model_version={result['metadata']['model_version']}")

        top = safety_model.feature_importance(result["model"])[:5]
        print("    Model feature importance (top 5):")
        for row in top:
            print(f"      {row['feature']:<32} {row['importance']:.3f}")

    if which in ("all", "recommender"):
        print("▸ Training recommendation model (synthetic preference examples)")
        result = recommendation_model.train()
        m = result["metadata"]["metrics"]
        print(f"  ✓ recommender_gb_v0_1.joblib  "
              f"MAE={m['mae']}  R²={m['r2']}  "
              f"(train={m['train_rows']} rows, test={m['test_rows']} rows)")

    print("Done.")
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    raise SystemExit(train_all(arg))
