from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd

from restaurant_risk.dataset.load import load_scoring_population
from restaurant_risk.modeling.calibration import SigmoidCalibrator
from restaurant_risk.modeling.features import get_feature_matrix


MODEL_FEATURES = [
    "prior_cycle_inspection_count",
    "prior_cycle_initial_count",
    "prior_cycle_reinspection_count",
    "prior_critical_inspection_count",
    "prior_cycle_initial_critical_count",
    "prior_cycle_reinspection_critical_count",
    "prior_critical_violation_count",
    "last_cycle_inspection_date",
    "days_since_last_critical_inspection",
    "max_historical_score",
    "average_historical_score",
    "average_score_last_365d",
    "cycle_inspections_last_365d",
    "critical_cycle_inspections_last_365d",
    "prior_total_violations",
    "prior_critical_violation_rows",
    "violations_last_365d",
    "critical_violations_last_365d",
    "has_no_cycle_initial_history",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score restaurants and create a capacity-constrained priority queue.")
    parser.add_argument("--capacity", type=int, required=True, help="Maximum number of restaurants to include in the priority queue.")
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    
    if args.capacity <= 0:
        raise ValueError("Capacity must be a positive integer.")
    
    project_root = Path(__file__).resolve().parents[2]
    database_path = project_root / "data" / "restaurant_risk.duckdb"
    
    model_path = project_root / "models" / "logistic_regression_C1.joblib"
    calibrator_path = project_root / "models" / "logistic_regression_C1_sigmoid_calibrator.joblib"
    all_scores_path = project_root / "output" / "restaurant_risk_scores.csv"
    priority_queue_path = project_root / "output" / "restaurant_priority_queue.csv"
    
    all_scores_path.parent.mkdir(parents=True, exist_ok=True)
    df = load_scoring_population(database_path)
    missing_features = [feature for feature in MODEL_FEATURES if feature not in df.columns]
    
    if missing_features:
        raise ValueError(f"Scoring population is missing required model features: {missing_features}")
    
    if args.capacity > len(df):
        raise ValueError(f"Capacity ({args.capacity}) exceeds the number of scorable restaurants ({len(df)}).")
    
    model = joblib.load(model_path)
    calibrator: SigmoidCalibrator = joblib.load(calibrator_path)
    X = get_feature_matrix(df)
    raw_scores = model.predict_proba(X)[:, 1]

    calibrated_scores = calibrator.predict_positive_probability(
        model=model,
        data_to_score=df,
    ).to_numpy()

    scored_columns = [
        column
        for column in [
            "camis",
            "restaurant_name",
            "borough",
            "cuisine_description",
            "cutoff_date",
            "history_depth_bucket",
        ]
        if column in df.columns
    ]

    scored = df[scored_columns].copy()
    scored["raw_logistic_probability"] = raw_scores
    scored["calibrated_high_severity_probability"] = calibrated_scores
    scored = scored.sort_values("calibrated_high_severity_probability", ascending=False, kind="stable").reset_index(drop=True)
    scored["priority_rank"] = scored.index + 1
    scored.to_csv(all_scores_path, index=False)
    priority_queue = scored.head(args.capacity).copy()
    priority_queue.to_csv(priority_queue_path, index=False)
    print(f"Scored restaurants: {len(scored)}")
    print(f"Inspection capacity: {args.capacity}")
    print(f"Priority queue size: {len(priority_queue)}")
    print()
    print(f"All scores written to: {all_scores_path}")
    print(f"Priority queue written to: {priority_queue_path}")
    print()
    print("Priority queue:")
    print(priority_queue.to_string(index=False))


if __name__ == "__main__":
    main()