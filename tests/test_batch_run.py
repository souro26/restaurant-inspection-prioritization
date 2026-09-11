from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from restaurant_risk.config import load_config
from restaurant_risk.modeling.features import MODEL_FEATURES
from restaurant_risk.pipeline import run_batch as run_batch_module

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CATEGORICAL_FEATURES = {
    "borough",
    "cuisine_description",
    "history_depth_bucket",
}


class FakeModel:
    """Minimal model used to test batch scoring behavior."""

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return deterministic probabilities."""
        probabilities = np.linspace(0.1, 0.9, len(X))
        return np.column_stack([1 - probabilities, probabilities])


class FakeCalibrator:
    """Minimal calibrator used to test batch scoring behavior."""

    def predict_positive_probability(
        self,
        model,
        data_to_score: pd.DataFrame,
    ) -> pd.Series:
        """Return deterministic calibrated probabilities."""
        return pd.Series(np.linspace(0.2, 0.8, len(data_to_score)))


class FakeArtifacts:
    """Minimal model artifact bundle."""

    model = FakeModel()
    calibrator = FakeCalibrator()
    feature_names = tuple(MODEL_FEATURES)


def _write_scoring_population(database_path: Path, n: int = 5) -> None:
    """Create a minimal processed.scoring_population table."""
    connection = duckdb.connect(str(database_path))

    try:
        numeric_features = [
            feature for feature in MODEL_FEATURES if feature not in CATEGORICAL_FEATURES
        ]

        columns = [
            '"camis" BIGINT',
            '"restaurant_name" VARCHAR',
            '"borough" VARCHAR',
            '"cuisine_description" VARCHAR',
            '"cutoff_date" DATE',
            '"history_depth_bucket" VARCHAR',
        ]
        columns.extend(f'"{feature}" DOUBLE' for feature in numeric_features)

        connection.execute("CREATE SCHEMA processed")
        connection.execute(
            f"CREATE TABLE processed.scoring_population ({', '.join(columns)})"
        )

        insert_columns = [
            "camis",
            "restaurant_name",
            "borough",
            "cuisine_description",
            "cutoff_date",
            "history_depth_bucket",
            *numeric_features,
        ]
        placeholders = ", ".join(["?"] * len(insert_columns))

        rows = []
        for index in range(n):
            row = {
                "camis": 90000000 + index,
                "restaurant_name": f"Test Restaurant {index + 1}",
                "borough": "Manhattan",
                "cuisine_description": "Test Cuisine",
                "cutoff_date": "2026-08-22",
                "history_depth_bucket": "2-3",
            }
            for feature in numeric_features:
                row[feature] = float(index + 1)
            rows.append([row[column] for column in insert_columns])

        connection.executemany(
            f"""
            INSERT INTO processed.scoring_population (
                {", ".join(f'"{column}"' for column in insert_columns)}
            )
            VALUES ({placeholders})
            """,
            rows,
        )
    finally:
        connection.close()


def _make_batch_config(tmp_path: Path):
    """Build an isolated ProjectConfig pointed at a scratch directory."""
    base_config = load_config(PROJECT_ROOT)

    database_path = tmp_path / "restaurant_risk_test.duckdb"
    _write_scoring_population(database_path)

    sql_directory = tmp_path / "sql"
    (sql_directory / "transformations").mkdir(parents=True)
    (sql_directory / "validation").mkdir(parents=True)

    (sql_directory / "transformations" / "01_noop.sql").write_text(
        "SELECT 1;", encoding="utf-8"
    )
    (sql_directory / "validation" / "01_noop.sql").write_text(
        "SELECT 1;", encoding="utf-8"
    )

    return replace(
        base_config,
        database_path=database_path,
        sql_directory=sql_directory,
        runs_directory=tmp_path / "runs",
        output_directory=tmp_path / "output",
    )


def _latest_run_directory(runs_directory: Path) -> Path:
    """Return the single run directory created by a batch run."""
    run_dirs = [entry for entry in runs_directory.iterdir() if entry.is_dir()]
    assert len(run_dirs) == 1
    return run_dirs[0]


def test_run_batch_success_writes_unified_run_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """A successful batch run writes logs, metadata, scores, and a queue."""
    config = _make_batch_config(tmp_path)

    monkeypatch.setattr(run_batch_module, "load_config", lambda project_root: config)
    monkeypatch.setattr(
        "restaurant_risk.score_restaurants.load_model_artifacts",
        lambda config: FakeArtifacts(),
    )

    return_code = run_batch_module.run_batch(capacity=3)

    assert return_code == 0

    run_directory = _latest_run_directory(config.runs_directory)

    assert (run_directory / "pipeline.log").exists()
    assert (run_directory / "restaurant_risk_scores.csv").exists()
    assert (run_directory / "restaurant_priority_queue.csv").exists()

    run_metadata = json.loads((run_directory / "run_metadata.json").read_text())
    assert run_metadata["status"] == "SUCCESS"

    batch_metadata = json.loads((run_directory / "batch_metadata.json").read_text())
    assert batch_metadata["status"] == "SUCCESS"
    assert batch_metadata["capacity"] == 3
    assert batch_metadata["population_size"] == 5
    assert batch_metadata["priority_queue_size"] == 3

    queue = pd.read_csv(run_directory / "restaurant_priority_queue.csv")
    assert len(queue) == 3

    # "Latest" copies used by ScoringService.get_scoring_status().
    assert (config.output_directory / "restaurant_risk_scores.csv").exists()
    assert (config.output_directory / "restaurant_priority_queue.csv").exists()


def test_run_batch_rejects_non_positive_capacity(tmp_path: Path):
    """Non-positive capacity should fail fast without creating a run."""
    with pytest.raises(ValueError, match="positive integer"):
        run_batch_module.run_batch(capacity=0)


def test_run_batch_missing_database_is_recorded_as_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """A missing DuckDB file should fail the run and still write metadata."""
    config = _make_batch_config(tmp_path)
    config = replace(config, database_path=tmp_path / "does_not_exist.duckdb")

    monkeypatch.setattr(run_batch_module, "load_config", lambda project_root: config)

    return_code = run_batch_module.run_batch(capacity=3)

    assert return_code == 1

    run_directory = _latest_run_directory(config.runs_directory)

    run_metadata = json.loads((run_directory / "run_metadata.json").read_text())
    assert run_metadata["status"] == "FAILED"

    batch_metadata = json.loads((run_directory / "batch_metadata.json").read_text())
    assert batch_metadata["status"] == "FAILED"
    assert batch_metadata["population_size"] is None