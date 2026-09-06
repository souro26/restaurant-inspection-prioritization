from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline

from restaurant_risk.config import ProjectConfig
from restaurant_risk.modeling.calibration import SigmoidCalibrator
from restaurant_risk.modeling.features import MODEL_FEATURES


class ModelArtifactError(Exception):
    """Raised when a model artifact does not satisfy the expected contract."""


@dataclass(frozen=True)
class ModelArtifacts:
    """Validated production model artifacts."""

    model: Pipeline
    calibrator: SigmoidCalibrator
    feature_names: tuple[str, ...]
    model_path: Path
    calibrator_path: Path


def load_model_artifacts(
    config: ProjectConfig,
) -> ModelArtifacts:
    """Load and validate the frozen production model artifacts."""
    if not config.model_path.exists():
        raise ModelArtifactError(
            f"Model artifact not found: {config.model_path}"
        )

    if not config.calibrator_path.exists():
        raise ModelArtifactError(
            f"Calibrator artifact not found: {config.calibrator_path}"
        )

    try:
        model = joblib.load(config.model_path)
    except Exception as exc:
        raise ModelArtifactError(
            f"Failed to load model artifact: {config.model_path}"
        ) from exc

    try:
        calibrator = joblib.load(config.calibrator_path)
    except Exception as exc:
        raise ModelArtifactError(
            f"Failed to load calibrator artifact: {config.calibrator_path}"
        ) from exc

    if not hasattr(model, "predict_proba"):
        raise ModelArtifactError(
            "Loaded model does not provide predict_proba()."
        )

    if not isinstance(calibrator, SigmoidCalibrator):
        raise ModelArtifactError(
            "Loaded calibrator is not a SigmoidCalibrator."
        )

    return ModelArtifacts(
        model=model,
        calibrator=calibrator,
        feature_names=tuple(MODEL_FEATURES),
        model_path=config.model_path,
        calibrator_path=config.calibrator_path,
    )