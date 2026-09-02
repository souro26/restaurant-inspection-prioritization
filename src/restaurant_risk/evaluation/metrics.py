from __future__ import annotations
import pandas as pd 
from restaurant_risk.evaluation.ranking import select_top_k

TARGET_COLUMN = "target_high_severity"

def random_expected_metrics(data: pd.DataFrame, capacity: int) -> dict[str, float]:
    """Calculate expected yield and precision under uniform random selection."""
    if capacity<=0:
        raise ValueError("capacity must be positive.")
    prevalence = float(data[TARGET_COLUMN].mean())
    return {"capacity": float(capacity), "expected_high_severity_outcomes": (capacity * prevalence), "expected_precision_at_k": prevalence, "lift_vs_random": 1.0}
    
def evaluate_ranking_policy(data: pd.DataFrame,score_column: str,capacity: int,policy_name: str) -> dict[str, float | str]:
    """Evaluate a score-based prioritization policy at fixed capacity."""
    selected = select_top_k(data=data,score_column=score_column,capacity=capacity,)
    precision_at_k = float(selected[TARGET_COLUMN].mean())
    outcomes_found = int(selected[TARGET_COLUMN].sum())
    prevalence = float(data[TARGET_COLUMN].mean())
    recall_at_k = float(outcomes_found / data[TARGET_COLUMN].sum())
    return {
        "policy": policy_name,
        "capacity": capacity,
        "selected_examples": len(selected),
        "high_severity_outcomes_found": outcomes_found,
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "lift_vs_random": (precision_at_k / prevalence if prevalence > 0 else float("nan")),
    }