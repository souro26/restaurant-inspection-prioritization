from pathlib import Path

import pytest

from restaurant_risk.config import load_config
from restaurant_risk.modeling.artifacts import (
    ModelArtifactError,
    ModelArtifacts,
    load_model_artifacts,
)
from restaurant_risk.modeling.features import MODEL_FEATURES

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_load_model_artifacts():
    config = load_config(PROJECT_ROOT)

    artifacts = load_model_artifacts(config)

    assert isinstance(artifacts, ModelArtifacts)

    assert artifacts.model_path == config.model_path
    assert artifacts.calibrator_path == config.calibrator_path

    assert artifacts.feature_names == tuple(MODEL_FEATURES)

    assert hasattr(artifacts.model, "predict_proba")


def test_model_artifacts_exist():
    config = load_config(PROJECT_ROOT)

    assert config.model_path.exists()
    assert config.calibrator_path.exists()


def test_missing_model_artifact_fails(tmp_path):
    config = load_config(PROJECT_ROOT)

    missing_config = config.__class__(
        **{
            **config.__dict__,
            "model_path": tmp_path / "missing_model.joblib",
        }
    )

    with pytest.raises(ModelArtifactError, match="Model artifact not found"):
        load_model_artifacts(missing_config)
