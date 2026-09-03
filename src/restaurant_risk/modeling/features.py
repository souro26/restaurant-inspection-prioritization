from __future__ import annotations
from typing import Final
import pandas as pd 
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TARGET_COLUMN: Final[str] = "target_high_severity"

NUMERIC_FEATURES: Final[list[str]] = [
    "prior_cycle_inspection_count",
    "prior_cycle_initial_count",
    "prior_cycle_reinspection_count",

    "prior_high_severity_inspection_count",
    "prior_high_severity_inspection_rate",
    "prior_cycle_initial_high_severity_count",
    "prior_cycle_reinspection_high_severity_count",
    "high_severity_cycle_inspections_last_365d",

    "prior_critical_violation_count",
    "prior_total_violations",
    "prior_critical_violation_rows",
    "violations_last_365d",
    "critical_violations_last_365d",

    "max_historical_score",
    "average_historical_score",
    "average_score_last_365d",

    "days_since_last_critical_inspection",
    "days_since_last_high_severity_inspection",
]

CATEGORICAL_FEATURES: Final[list[str]] = ["borough", "cuisine_description", "history_depth_bucket"]
MODEL_FEATURES: Final[list[str]] = NUMERIC_FEATURES + CATEGORICAL_FEATURES
AUDIT_ONLY_FEATURES: Final[list[str]] = ["days_since_last_cycle_inspection",
    "prior_critical_inspection_rate",
    "feature_source_max_date",
    "violation_feature_source_max_date",
]

def validate_model_feature_schema(df: pd.DataFrame) -> None:
    """Assert that the feature columns in df match the expected schema"""
    missing_features = [feature for feature in MODEL_FEATURES if feature not in df.columns]
    if missing_features:
        raise ValueError(f"Missing required columns: {missing_features}")
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Missing target column: {TARGET_COLUMN}")
    forbidden_present = [column for column in df.columns if column.startswith("target_") and column != TARGET_COLUMN]
    if forbidden_present:
        raise ValueError(f"Forbidden columns found {forbidden_present}")
    
def get_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the approved model feature columns."""
    missing_features = [feature for feature in MODEL_FEATURES if feature not in df.columns]
    if missing_features:
        raise ValueError(f"Missing model features: {missing_features}")
    return df[MODEL_FEATURES].copy()

def get_target_vector(df: pd.DataFrame) -> pd.Series:
    """Return the canonical binary target vector."""
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Missing target column: {TARGET_COLUMN}")
    target = df[TARGET_COLUMN].copy()
    if target.isna().any():
        raise ValueError("Target contains missing values.")
    if not target.isin([0,1]).all():
        raise ValueError("Target must contain only binary values: 0 or 1.")
    return target

def build_preprocessor() -> ColumnTransformer:
    """Build train-only preprocessing for model features."""
    numeric_pipeline = Pipeline(steps=[("imputer",SimpleImputer(strategy="median",add_indicator=True)),("scaler",StandardScaler(),),])
    categorical_pipeline = Pipeline(steps=[("imputer",SimpleImputer(strategy="constant",fill_value="Missing",)),("onehot",OneHotEncoder(handle_unknown="ignore"))])
    return ColumnTransformer(transformers=[("numeric",numeric_pipeline,NUMERIC_FEATURES),("categorical",categorical_pipeline,CATEGORICAL_FEATURES)], remainder="drop")