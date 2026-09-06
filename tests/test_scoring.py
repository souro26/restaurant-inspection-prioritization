from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from restaurant_risk.config import load_config
from restaurant_risk.modeling.features import MODEL_FEATURES
from restaurant_risk.score_restaurants import score_restaurants

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeModel:
    """Minimal model used to test scoring behavior."""

    def predict_proba(
        self,
        X: pd.DataFrame,
    ) -> np.ndarray:
        """Return deterministic probabilities."""
        probabilities = np.linspace(
            0.1,
            0.9,
            len(X),
        )

        return np.column_stack(
            [
                1 - probabilities,
                probabilities,
            ]
        )


class FakeCalibrator:
    """Minimal calibrator used to test scoring behavior."""

    def predict_positive_probability(
        self,
        model,
        data_to_score: pd.DataFrame,
    ) -> pd.Series:
        """Return deterministic calibrated probabilities."""
        return pd.Series(
            np.linspace(
                0.2,
                0.8,
                len(data_to_score),
            )
        )


class FakeArtifacts:
    """Minimal model artifact bundle."""

    model = FakeModel()
    calibrator = FakeCalibrator()
    feature_names = tuple(MODEL_FEATURES)


def make_test_dataframe(
    n: int = 5,
) -> pd.DataFrame:
    """Create a minimal valid scoring population."""
    data: dict[str, list] = {}

    for feature in MODEL_FEATURES:
        if feature in {
            "borough",
            "cuisine_description",
            "history_depth_bucket",
        }:
            data[feature] = ["Test"] * n
        else:
            data[feature] = [1.0] * n

    data["camis"] = list(range(1, n + 1))

    return pd.DataFrame(data)


def test_score_restaurants_orders_by_calibrated_probability(
    monkeypatch: pytest.MonkeyPatch,
):
    """Scores should be ranked by calibrated probability."""
    config = load_config(PROJECT_ROOT)

    monkeypatch.setattr(
        "restaurant_risk.score_restaurants.load_model_artifacts",
        lambda config: FakeArtifacts(),
    )

    df = make_test_dataframe()

    scored, priority_queue = score_restaurants(
        df=df,
        config=config,
        capacity=3,
    )

    assert len(scored) == 5
    assert len(priority_queue) == 3

    assert scored["calibrated_high_severity_probability"].is_monotonic_decreasing

    assert scored["priority_rank"].tolist() == [
        1,
        2,
        3,
        4,
        5,
    ]


def test_score_restaurants_rejects_non_positive_capacity():
    """Non-positive inspection capacity should fail."""
    config = load_config(PROJECT_ROOT)

    df = make_test_dataframe()

    with pytest.raises(
        ValueError,
        match="positive integer",
    ):
        score_restaurants(
            df=df,
            config=config,
            capacity=0,
        )


def test_score_restaurants_rejects_capacity_above_population():
    """Capacity larger than the scoring population should fail."""
    config = load_config(PROJECT_ROOT)

    df = make_test_dataframe()

    with pytest.raises(
        ValueError,
        match="exceeds the number of scorable restaurants",
    ):
        score_restaurants(
            df=df,
            config=config,
            capacity=len(df) + 1,
        )


def test_score_restaurants_rejects_feature_schema_mismatch(
    monkeypatch: pytest.MonkeyPatch,
):
    """A feature schema mismatch should fail before prediction."""
    config = load_config(PROJECT_ROOT)

    class WrongArtifacts:
        """Artifact bundle with an incompatible feature schema."""

        model = FakeModel()
        calibrator = FakeCalibrator()
        feature_names = ("wrong_feature",)

    monkeypatch.setattr(
        "restaurant_risk.score_restaurants.load_model_artifacts",
        lambda config: WrongArtifacts(),
    )

    df = make_test_dataframe()

    with pytest.raises(
        ValueError,
        match="feature schema",
    ):
        score_restaurants(
            df=df,
            config=config,
            capacity=3,
        )
