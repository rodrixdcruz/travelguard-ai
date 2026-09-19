"""Model artifact storage with metadata and graceful missing-model handling."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("travelguard.ml")

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
SAFETY_MODEL_PATH = MODELS_DIR / "safety_rf_v0_1.joblib"
SAFETY_META_PATH = MODELS_DIR / "safety_rf_v0_1.meta.json"


def models_dir() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR


def save_with_metadata(model: Any, metadata: dict[str, Any], model_path: Path, meta_path: Path) -> None:
    import joblib

    models_dir()
    metadata = {**metadata, "training_date": datetime.now(timezone.utc).isoformat()}
    joblib.dump(model, model_path)
    meta_path.write_text(json.dumps(metadata, indent=2))
    logger.info("Saved model %s (v%s)", model_path.name, metadata.get("model_version"))


def load_with_metadata(model_path: Path, meta_path: Path) -> Optional[tuple[Any, dict[str, Any]]]:
    """Return (model, metadata) or None if the artifact is missing/corrupt."""
    if not model_path.exists():
        return None
    try:
        import joblib

        model = joblib.load(model_path)
        metadata: dict[str, Any] = {}
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text())
        return model, metadata
    except Exception as exc:  # corrupt artifact, sklearn version skew, etc.
        logger.warning("Failed to load model %s: %s — falling back to rule engine", model_path.name, exc)
        return None
