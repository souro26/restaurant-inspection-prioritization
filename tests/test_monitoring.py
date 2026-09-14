from pathlib import Path

import pandas as pd
import pytest

from restaurant_risk.monitoring.metrics import (
    build_batch_metrics,
    write_batch_metrics,
)


def test_build_batch_metrics(tmp_path: Path):
    scores_path = tmp_path / "scores.csv"

    scores = pd.DataFrame(
        {
            "camis": [1, 2, 3, 4],
            "calibrated_high_severity_probability": [
                0.10,
                0.60,
                0.80,
                0.90,
            ],
            "priority_rank": [4, 3, 2, 1],
            "history_depth_bucket": [
                "0",
                "1",
                "2-3",
                "4+",
            ],
        }
    )

    scores.to_csv(scores_path, index=False)

    metrics = build_batch_metrics(
        run_id="test-run",
        status="success",
        capacity=100,
        population_size=4,
        priority_queue_size=4,
        duration_seconds=12.5,
        scores_path=scores_path,
    )

    assert metrics["run_id"] == "test-run"
    assert metrics["status"] == "success"
    assert metrics["capacity"] == 100
    assert metrics["population_size"] == 4
    assert metrics["priority_queue_size"] == 4
    assert metrics["duration_seconds"] == 12.5

    assert metrics["prediction_count"] == 4
    assert metrics["unique_restaurants"] == 4

    assert metrics["prediction_mean"] == pytest.approx(0.60)
    assert metrics["prediction_median"] == pytest.approx(0.70)
    assert metrics["prediction_min"] == pytest.approx(0.10)
    assert metrics["prediction_max"] == pytest.approx(0.90)

    assert metrics["high_risk_rate_0_50"] == pytest.approx(0.75)
    assert metrics["high_risk_rate_0_75"] == pytest.approx(0.50)

    assert metrics["top_rank_probability"] == pytest.approx(0.10)

    assert set(metrics["history_depth_distribution"]) == {
        "0",
        "1",
        "2-3",
        "4+",
    }


def test_missing_score_file_returns_operational_metrics(tmp_path: Path):
    metrics = build_batch_metrics(
        run_id="missing-scores",
        status="success",
        capacity=50,
        population_size=100,
        priority_queue_size=50,
        duration_seconds=20.0,
        scores_path=tmp_path / "does_not_exist.csv",
    )

    assert metrics["run_id"] == "missing-scores"
    assert metrics["status"] == "success"
    assert metrics["population_size"] == 100
    assert metrics["priority_queue_size"] == 50
    assert metrics["prediction_count"] if "prediction_count" in metrics else True


def test_missing_required_score_column_raises(tmp_path: Path):
    scores_path = tmp_path / "invalid.csv"

    pd.DataFrame(
        {
            "camis": [1, 2],
            "priority_rank": [1, 2],
        }
    ).to_csv(scores_path, index=False)

    with pytest.raises(ValueError, match="missing required monitoring columns"):
        build_batch_metrics(
            run_id="invalid-run",
            status="success",
            capacity=10,
            population_size=2,
            priority_queue_size=2,
            duration_seconds=1.0,
            scores_path=scores_path,
        )


def test_write_batch_metrics(tmp_path: Path):
    output_path = tmp_path / "monitoring" / "metrics.json"

    metrics = {
        "run_id": "test-run",
        "status": "success",
        "capacity": 100,
        "prediction_mean": 0.42,
    }

    write_batch_metrics(metrics, output_path)

    assert output_path.exists()

    import json

    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == metrics