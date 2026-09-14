from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import boto3
import pandas as pd


REQUIRED_SCORE_COLUMNS = {
    "camis",
    "calibrated_high_severity_probability",
    "priority_rank",
}


def build_batch_metrics(
    *,
    run_id: str,
    status: str,
    capacity: int,
    population_size: int | None,
    priority_queue_size: int | None,
    duration_seconds: float | None,
    scores_path: Path | None,
) -> dict[str, Any]:
    """Build operational and prediction-distribution metrics for a batch run."""

    metrics: dict[str, Any] = {
        "run_id": run_id,
        "status": status,
        "capacity": capacity,
        "population_size": population_size,
        "priority_queue_size": priority_queue_size,
        "duration_seconds": duration_seconds,
    }

    if scores_path is None or not scores_path.exists():
        return metrics

    scores = pd.read_csv(scores_path)

    missing_columns = REQUIRED_SCORE_COLUMNS - set(scores.columns)

    if missing_columns:
        raise ValueError(
            "Score artifact is missing required monitoring columns: "
            + ", ".join(sorted(missing_columns))
        )

    probabilities = scores[
        "calibrated_high_severity_probability"
    ].dropna()

    metrics.update(
        {
            "prediction_count": int(len(scores)),
            "prediction_mean": (
                float(probabilities.mean())
                if not probabilities.empty
                else None
            ),
            "prediction_min": (
                float(probabilities.min())
                if not probabilities.empty
                else None
            ),
            "prediction_max": (
                float(probabilities.max())
                if not probabilities.empty
                else None
            ),
            "prediction_median": (
                float(probabilities.median())
                if not probabilities.empty
                else None
            ),
            "high_risk_rate_0_50": (
                float((probabilities >= 0.50).mean())
                if not probabilities.empty
                else None
            ),
            "high_risk_rate_0_75": (
                float((probabilities >= 0.75).mean())
                if not probabilities.empty
                else None
            ),
            "unique_restaurants": int(scores["camis"].nunique()),
            "top_rank_probability": (
                float(
                    scores.iloc[0][
                        "calibrated_high_severity_probability"
                    ]
                )
                if not scores.empty
                else None
            ),
        }
    )

    if "history_depth_bucket" in scores.columns:
        history_distribution = (
            scores["history_depth_bucket"]
            .fillna("missing")
            .value_counts(normalize=True)
            .to_dict()
        )

        metrics["history_depth_distribution"] = {
            str(key): float(value)
            for key, value in history_distribution.items()
        }

    return metrics


def publish_cloudwatch_metrics(
    metrics: dict[str, Any],
    *,
    region_name: str,
) -> None:
    """Publish batch monitoring metrics to CloudWatch."""

    cloudwatch = boto3.client(
        "cloudwatch",
        region_name=region_name,
    )

    metric_data: list[dict[str, Any]] = []

    numeric_metrics = {
        "PopulationSize": metrics.get("population_size"),
        "PriorityQueueSize": metrics.get("priority_queue_size"),
        "PredictionCount": metrics.get("prediction_count"),
        "UniqueRestaurants": metrics.get("unique_restaurants"),
        "PredictionMean": metrics.get("prediction_mean"),
        "PredictionMedian": metrics.get("prediction_median"),
        "PredictionMin": metrics.get("prediction_min"),
        "PredictionMax": metrics.get("prediction_max"),
        "HighRiskRate50": metrics.get("high_risk_rate_0_50"),
        "HighRiskRate75": metrics.get("high_risk_rate_0_75"),
        "TopRankProbability": metrics.get("top_rank_probability"),
        "DurationSeconds": metrics.get("duration_seconds"),
    }

    for metric_name, value in numeric_metrics.items():
        if value is None:
            continue

        metric_data.append(
            {
                "MetricName": metric_name,
                "Dimensions": [
                    {
                        "Name": "Environment",
                        "Value": "production",
                    },
                ],
                "Value": float(value),
                "Unit": (
                    "Seconds"
                    if metric_name == "DurationSeconds"
                    else "None"
                ),
            }
        )

    if not metric_data:
        return

    cloudwatch.put_metric_data(
        Namespace="RestaurantRisk",
        MetricData=metric_data,
    )


def write_batch_metrics(
    metrics: dict[str, Any],
    path: Path,
) -> None:
    """Write monitoring metrics as JSON."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            metrics,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )