from __future__ import annotations
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from restaurant_risk.modeling.features import (
    build_preprocessor,
    get_feature_matrix,
    get_target_vector,
    validate_model_feature_schema,
)

def build_logistic_regression_pipeline(c: float = 1.0, max_iter: int = 1000, random_state: int = 42) -> Pipeline:
    """Build the first multivariable ML model."""
    if c<=0:
        raise ValueError("c must be positive.")
    preprocessor = build_preprocessor()
    classifier = LogisticRegression(C=c, max_iter=max_iter, random_state=random_state, solver="lbfgs")
    return Pipeline(steps = [("preprocessor", preprocessor),("classifier", classifier)])

def fit_logistic_regression(train_df: pd.DataFrame, c:float = 1.0, max_iter: int = 1000, random_state:int =42) -> Pipeline:
    """Fit leakage safe logistic regression using training data only."""
    validate_model_feature_schema(train_df)
    X_train = get_feature_matrix(train_df)
    y_train = get_target_vector(train_df)
    pipeline = build_logistic_regression_pipeline(c=c,max_iter=max_iter,random_state=random_state,)
    pipeline.fit(X_train, y_train)
    return pipeline

def predict_logistic_probabilities(model: Pipeline, data_to_score: pd.DataFrame) -> pd.Series:
    """Predict high severity probabilities using a fitted pipeline."""
    validate_model_feature_schema(data_to_score)
    X = get_feature_matrix(data_to_score)
    probabilities = model.predict_proba(X)[:, 1]
    return pd.Series(probabilities,index=data_to_score.index,name="logistic_high_severity_probability")

def add_logistic_probabilities(model: Pipeline, data_to_score: pd.DataFrame, score_column: str = "logistic_high_severity_probability") -> pd.DataFrame:
    """Return a copy of data_to_score with logistic probabilities added."""
    result = data_to_score.copy()
    result[score_column] = predict_logistic_probabilities(model=model, data_to_score=result)
    return result