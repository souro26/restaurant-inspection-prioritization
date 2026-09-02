from __future__ import annotations
import pandas as pd 

def select_top_k(data: pd.DataFrame, score_column: str, capacity: str, restaurant_id_column: str = "camis") -> pd.DataFrame:
    """Return the highest-risk rows under a fixed inspection capacity."""
    if capacity <= 0:
        raise ValueError("Capacity must be positive.")
    if score_column not in data.columns:
        raise KeyError(f"{score_column} not found in data.")
    if restaurant_id_column not in data.columns:
        raise KeyError(f"{restaurant_id_column} not found in data.")
    return data.sort_values(by = [score_column, restaurant_id_column], ascending=[False, True]).head(capacity).reset_index(drop=True).copy()
    