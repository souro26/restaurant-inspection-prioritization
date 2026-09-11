from __future__ import annotations

import argparse
import json
import sys
import traceback
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from restaurant_risk.config import load_config
from restaurant_risk.dataset.load import load_scoring_population
from restaurant_risk.exceptions import PipelineError
from restaurant_risk.logging import configure_logging
from restaurant_risk.modeling.artifacts import ModelArtifactError
from restaurant_risk.pipeline.metadata import RunMetadata
from restaurant_risk.pipeline.run_data_pipeline import (
    run_transformations,
    run_validations,
)
from restaurant_risk.score_restaurants import score_restaurants

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class BatchRunMetadata:
    """Metadata describing the scoring portion of one batch run."""

    run_id: str
    status: str
    capacity: int
    population_size: int | None
    priority_queue_size: int | None
    scores_path: str | None
    priority_queue_path: str | None

    def write(self, path: Path) -> None:
        """Write batch metadata as JSON."""
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                asdict(self),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the production batch pipeline: refresh and validate the "
            "DuckDB warehouse, score the current restaurant population "
            "with the frozen production model, and write a "
            "capacity-constrained inspection priority queue."
        )
    )

    parser.add_argument(
        "--capacity",
        type=int,
        required=True,
        help=("Maximum number of restaurants to include in the priority queue."),
    )

    return parser.parse_args()


def run_batch(capacity: int) -> int:
    """Run the full production batch pipeline: data pipeline + scoring.

    Reuses the existing transformation/validation SQL runner and the
    existing scoring module rather than reimplementing their logic. All
    artifacts for this run (pipeline log, pipeline metadata, batch
    metadata, scores, and priority queue) are written to a single
    timestamped run directory.
    """
    if capacity <= 0:
        raise ValueError("Capacity must be a positive integer.")

    config = load_config(PROJECT_ROOT)

    started_at = datetime.now(UTC)
    run_id = started_at.strftime("%Y%m%dT%H%M%SZ")
    run_directory = config.runs_directory / run_id
    run_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger = configure_logging(run_directory / "pipeline.log")

    logger.info("Starting restaurant-risk batch run")
    logger.info("Run ID: %s", run_id)
    logger.info("Capacity: %s", capacity)
    logger.info("Database: %s", config.database_path)

    connection = None
    status = "FAILED"
    population_size: int | None = None
    priority_queue_size: int | None = None
    scores_path: str | None = None
    priority_queue_path: str | None = None
    return_code = 1

    try:
        if not config.database_path.exists():
            raise PipelineError(f"DuckDB database not found: {config.database_path}")

        connection = duckdb.connect(str(config.database_path))
        logger.info("Connected to DuckDB")

        run_transformations(
            connection=connection,
            sql_directory=config.sql_directory,
            logger=logger,
        )
        logger.info("All transformations completed")

        run_validations(
            connection=connection,
            validation_directory=(config.sql_directory / "validation"),
            logger=logger,
        )
        logger.info("All validations completed")

        connection.close()
        connection = None
        logger.info("DuckDB connection closed")

        logger.info("Loading scoring population")
        df = load_scoring_population(config.database_path)
        population_size = len(df)
        logger.info("Scoring population size: %s", population_size)

        scored, priority_queue = score_restaurants(
            df=df,
            config=config,
            capacity=capacity,
        )
        priority_queue_size = len(priority_queue)
        logger.info("Priority queue size: %s", priority_queue_size)

        run_scores_path = run_directory / "restaurant_risk_scores.csv"
        run_queue_path = run_directory / "restaurant_priority_queue.csv"

        scored.to_csv(run_scores_path, index=False)
        priority_queue.to_csv(run_queue_path, index=False)

        # Also refresh the "latest" outputs consumed by
        # ScoringService.get_scoring_status() and manual inspection.
        config.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        scored.to_csv(
            config.output_directory / "restaurant_risk_scores.csv",
            index=False,
        )
        priority_queue.to_csv(
            config.output_directory / "restaurant_priority_queue.csv",
            index=False,
        )

        scores_path = str(run_scores_path)
        priority_queue_path = str(run_queue_path)

        status = "SUCCESS"
        return_code = 0

        logger.info("Batch run completed successfully")

    except (PipelineError, ModelArtifactError, ValueError) as exc:
        logger.error("Batch run failed: %s", exc)
        logger.error(traceback.format_exc())
        return_code = 1

    finally:
        if connection is not None:
            connection.close()
            logger.info("DuckDB connection closed")

        completed_at = datetime.now(UTC)

        pipeline_metadata = RunMetadata(
            run_id=run_id,
            status=status,
            started_at_utc=started_at.isoformat(),
            completed_at_utc=completed_at.isoformat(),
            duration_seconds=(completed_at - started_at).total_seconds(),
            project_name=config.project_name,
            database_path=str(config.database_path),
        )
        pipeline_metadata.write(run_directory / "run_metadata.json")

        batch_metadata = BatchRunMetadata(
            run_id=run_id,
            status=status,
            capacity=capacity,
            population_size=population_size,
            priority_queue_size=priority_queue_size,
            scores_path=scores_path,
            priority_queue_path=priority_queue_path,
        )
        batch_metadata.write(run_directory / "batch_metadata.json")

    return return_code


def main() -> None:
    """Run the batch pipeline from the command line."""
    args = parse_args()

    return_code = run_batch(capacity=args.capacity)

    sys.exit(return_code)


if __name__ == "__main__":
    main()