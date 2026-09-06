from __future__ import annotations

import pandas as pd


def select_top_k(
    data: pd.DataFrame,
    score_column: str,
    capacity: int,
    restaurant_id_column: str = "camis",
) -> pd.DataFrame:
    """Select the highest-scoring restaurants."""
    if capacity <= 0:
        raise ValueError(
            "Capacity must be a positive integer."
        )

    if score_column not in data.columns:
        raise ValueError(
            f"Score column not found: {score_column}"
        )

    if restaurant_id_column not in data.columns:
        raise ValueError(
            "Restaurant ID column not found: "
            f"{restaurant_id_column}"
        )

    return (
        data.sort_values(
            score_column,
            ascending=False,
            kind="stable",
        )
        .head(capacity)
        .reset_index(drop=True)
    )