from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from restaurant_risk.config import ProjectConfig, load_config
from restaurant_risk.dataset.load import load_scoring_population
from restaurant_risk.modeling.artifacts import load_model_artifacts
from restaurant_risk.modeling.features import get_feature_matrix

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Score restaurants and create a "
            "capacity-constrained priority queue."
        )
    )

    parser.add_argument(
        "--capacity",
        type=int,
        required=True,
        help=(
            "Maximum number of restaurants to include "
            "in the priority queue."
        ),
    )

    return parser.parse_args()


def score_restaurants(
    df: pd.DataFrame,
    config: ProjectConfig,
    capacity: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score restaurants and create a priority queue."""
    if capacity <= 0:
        raise ValueError(
            "Capacity must be a positive integer."
        )

    if capacity > len(df):
        raise ValueError(
            f"Capacity ({capacity}) exceeds the "
            f"number of scorable restaurants ({len(df)})."
        )

    artifacts = load_model_artifacts(config)

    X = get_feature_matrix(df)

    if tuple(X.columns) != artifacts.feature_names:
        raise ValueError(
            "Scoring feature schema does not match the "
            "frozen model artifact contract."
        )

    raw_scores = (
        artifacts.model.predict_proba(X)[:, 1]
    )

    calibrated_scores = (
        artifacts.calibrator
        .predict_positive_probability(
            model=artifacts.model,
            data_to_score=df,
        )
        .to_numpy()
    )

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

    scored[
        "calibrated_high_severity_probability"
    ] = calibrated_scores

    scored = (
        scored.sort_values(
            "calibrated_high_severity_probability",
            ascending=False,
            kind="stable",
        )
        .reset_index(drop=True)
    )

    scored["priority_rank"] = (
        scored.index + 1
    )

    priority_queue = (
        scored.head(capacity)
        .copy()
    )

    return scored, priority_queue


def main() -> None:
    """Score the current restaurant population."""
    args = parse_args()

    config = load_config(PROJECT_ROOT)

    all_scores_path = (
        config.output_directory
        / "restaurant_risk_scores.csv"
    )

    priority_queue_path = (
        config.output_directory
        / "restaurant_priority_queue.csv"
    )

    config.output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = load_scoring_population(
        config.database_path
    )

    scored, priority_queue = score_restaurants(
        df=df,
        config=config,
        capacity=args.capacity,
    )

    scored.to_csv(
        all_scores_path,
        index=False,
    )

    priority_queue.to_csv(
        priority_queue_path,
        index=False,
    )

    print(
        f"Scored restaurants: {len(scored)}"
    )
    print(
        f"Inspection capacity: {args.capacity}"
    )
    print(
        f"Priority queue size: {len(priority_queue)}"
    )
    print()

    print(
        f"All scores written to: {all_scores_path}"
    )
    print(
        f"Priority queue written to: "
        f"{priority_queue_path}"
    )

    print()

    print("Priority queue:")
    print(
        priority_queue.to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()