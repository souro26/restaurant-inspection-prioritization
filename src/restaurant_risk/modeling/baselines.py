from __future__ import annotations
import pandas as pd

TARGET_COLUMN = "target_high_severity"
HIGH_SEVERITY_COUNT_COLUMN = "prior_high_severity_inspection_count"
INSPECTION_COUNT_COLUMN = "prior_cycle_inspection_count"

def training_base_rate(train_df: pd.DataFrame) -> float:
    """Estimate the high severity target prevalence from training data only."""
    return float(train_df[TARGET_COLUMN].mean())

def calculate_smoothed_historical_risk(data: pd.DataFrame, base_rate: float, alpha: float) -> pd.Series:
    """Calculate empirical Bayes style smoothed historical risk."""
    if alpha<= 0:
        raise ValueError("alpha must be positive.")
    high_severity_count = data[HIGH_SEVERITY_COUNT_COLUMN]
    inspection_count = data[INSPECTION_COUNT_COLUMN]
    return (high_severity_count + alpha * base_rate) / (inspection_count + alpha)

def add_smoothed_historical_risk(train_df: pd.DataFrame, data_to_score: pd.DataFrame, alpha: float, score_column: str("smoothed_historical_high_severity_risk")) -> pd.DataFrame:
    """Compute training historical risk score to a copy of data_to_score"""
    result = data_to_score.copy()
    base_rate = training_base_rate(train_df)
    result[score_column] = calculate_smoothed_historical_risk(data = result, base_rate= base_rate, alpha= alpha)
    return result
