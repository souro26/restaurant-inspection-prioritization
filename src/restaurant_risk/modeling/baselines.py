from __future__ import annotations

import pandas as pd

TARGET_COLUMN = "target_high_severity"


def add_smoothed_historical_risk(
    train_df: pd.DataFrame,
    data_to_score: pd.DataFrame,
    alpha: float,
    score_column: str = ("smoothed_historical_high_severity_risk"),
) -> pd.DataFrame:
    """Compute historical risk scores for data_to_score."""
    global_positive_rate = train_df[TARGET_COLUMN].mean()

    history = (
        train_df.groupby("camis")[TARGET_COLUMN]
        .agg(["sum", "count"])
        .rename(
            columns={
                "sum": "positive_count",
                "count": "inspection_count",
            }
        )
    )

    history["smoothed_risk"] = (
        history["positive_count"] + alpha * global_positive_rate
    ) / (history["inspection_count"] + alpha)

    scored = data_to_score.copy()

    scored[score_column] = (
        scored["camis"].map(history["smoothed_risk"]).fillna(global_positive_rate)
    )

    return scored
