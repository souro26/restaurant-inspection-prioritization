from __future__ import annotations
import pandas as pd

TARGET_COLUMN = "target_high_severity"

def create_primary_temporal_splits(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create the primary temporal split."""
    cohort = df[(df.cutoff_date >= "2022-01-01") and (df.cutoff_date < "2026-01-01")].copy()
    train_df = cohort[cohort.cutoff_date < "2024-01-01"].copy()
    validation_df = cohort[(cohort["cutoff_date"] >= "2024-01-01") and (cohort["cutoff_date"] < "2025-01-01")].copy()
    test_df = cohort[(cohort["cutoff_date"] >= "2025-01-01") and (cohort["cutoff_date"] < "2026-01-01")].copy()
    validate_temporal_splits(train_df, validation_df, test_df)
    return train_df, validation_df, test_df

def validate_temporal_splits(train_df: pd.DataFrame, validation_df: pd.DataFrame, test_df: pd.DataFrame) -> None:
    """Raise an error if split boundaries or target values are invalid."""
    splits = {"train": train_df,"validation": validation_df,"test": test_df}
    for split_name, split_df in splits.items():
        if split_df.empty:
            raise ValueError(f"{split_name} split is empty.")
        if not split_df[TARGET_COLUMN].isin([0, 1]).all():
            raise ValueError(f"{split_name} split contains invalid target values.")
        if split_df[TARGET_COLUMN].sum() == 0:
            raise ValueError(f"{split_name} split has no positive examples.")
    if train_df["cutoff_date"].max() >= validation_df["cutoff_date"].min():
        raise ValueError("Training and validation periods overlap.")
    if validation_df["cutoff_date"].max() >= test_df["cutoff_date"].min():
        raise ValueError("Validation and test periods overlap.")