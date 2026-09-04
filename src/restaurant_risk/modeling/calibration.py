from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from restaurant_risk.modeling.features import (
    get_feature_matrix,
    get_target_vector,
)


class SigmoidCalibrator:
    """
    Platt/sigmoid probability calibration.

    The underlying classifier is assumed to already be fitted.
    The calibrator learns a sigmoid mapping from the classifier's
    raw decision scores to observed outcomes on a held-out
    calibration period.
    """

    def __init__(self) -> None:
        self.model = LogisticRegression()
        self.is_fitted = False

    def fit(
        self,
        model: Pipeline,
        calibration_df: pd.DataFrame,
    ) -> "SigmoidCalibrator":
        """
        Fit the sigmoid calibration mapping using a held-out
        temporal calibration dataset.
        """
        X_calibration = get_feature_matrix(calibration_df)
        y_calibration = get_target_vector(calibration_df)

        # Get the raw decision score from the already-fitted model.
        raw_scores = model.decision_function(X_calibration)

        raw_scores = np.asarray(raw_scores).reshape(-1, 1)

        # Fit sigmoid mapping:
        #
        # P(Y=1) = sigmoid(A * raw_score + B)
        #
        # This logistic regression is the Platt calibrator.
        self.model.fit(raw_scores, y_calibration)

        self.is_fitted = True

        return self

    def predict_proba(
        self,
        model: Pipeline,
        data_to_score: pd.DataFrame,
    ) -> np.ndarray:
        """
        Return calibrated probabilities for both classes.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "SigmoidCalibrator must be fitted before prediction."
            )

        X = get_feature_matrix(data_to_score)

        raw_scores = model.decision_function(X)
        raw_scores = np.asarray(raw_scores).reshape(-1, 1)

        return self.model.predict_proba(raw_scores)

    def predict_positive_probability(
        self,
        model: Pipeline,
        data_to_score: pd.DataFrame,
    ) -> pd.Series:
        """
        Return calibrated probability of the positive class.
        """
        probabilities = self.predict_proba(
            model=model,
            data_to_score=data_to_score,
        )[:, 1]

        return pd.Series(
            probabilities,
            index=data_to_score.index,
            name="calibrated_high_severity_probability",
        )