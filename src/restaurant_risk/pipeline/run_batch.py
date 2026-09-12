from __future__ import annotations

import argparse
import json
import random
import os
import shutil
import sys
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
from restaurant_risk.storage.artifacts import (
    ArtifactStoreError,
    create_artifact_store,
)


PROJECT_ROOT = Path(
    os.environ.get(
        "RESTAURANT_RISK_PROJECT_ROOT",
        Path(__file__).resolve().parents[3],
    )
)


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
            "Run the restaurant-risk batch pipeline, validate the data, "
            "score the current restaurant population, and create a "
            "capacity-constrained inspection priority queue."
        )
    )

    parser.add_argument(
        "--capacity",
        type=int,
        required=True,
        help=(
            "Maximum number of restaurants in the "
            "priority queue."
        ),
    )

    return parser.parse_args()


def _download_source_csv(
    url: str,
    destination: Path,
    logger,
    max_attempts: int = 5,
    timeout: int = 300,
) -> None:
    """
    Download the source CSV with retries for transient failures.

    Retryable conditions:
    - HTTP 408
    - HTTP 429
    - HTTP 500
    - HTTP 502
    - HTTP 503
    - HTTP 504
    - network-level URL errors

    Uses exponential backoff with jitter between attempts.
    """

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    user_agent = (
        "restaurant-inspection-prioritization/1.0 "
        "(automated data pipeline)"
    )

    transient_statuses = {
        408,
        429,
        500,
        502,
        503,
        504,
    }

    for attempt in range(
        1,
        max_attempts + 1,
    ):
        logger.info(
            "Source download attempt %d/%d",
            attempt,
            max_attempts,
        )

        request = Request(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/csv,*/*",
            },
        )

        try:
            started_at = time.monotonic()

            with urlopen(
                request,
                timeout=timeout,
            ) as response:
                with destination.open(
                    "wb"
                ) as output_file:
                    shutil.copyfileobj(
                        response,
                        output_file,
                    )

            duration_seconds = (
                time.monotonic()
                - started_at
            )

            file_size_mb = (
                destination.stat().st_size
                / (1024 * 1024)
            )

            logger.info(
                "Source dataset downloaded successfully "
                "on attempt %d/%d",
                attempt,
                max_attempts,
            )

            logger.info(
                "Downloaded file size: %.2f MB",
                file_size_mb,
            )

            logger.info(
                "Download duration: %.2f seconds",
                duration_seconds,
            )

            return

        except HTTPError as exc:
            status = exc.code

            if status not in transient_statuses:
                logger.error(
                    "Source download failed with "
                    "non-retryable HTTP status %d",
                    status,
                )
                raise

            if attempt == max_attempts:
                logger.error(
                    "Source download failed after "
                    "%d attempts; final HTTP status: %d",
                    max_attempts,
                    status,
                )
                raise

            retry_after = exc.headers.get(
                "Retry-After"
            )

            delay: float | None = None

            if retry_after is not None:
                try:
                    delay = float(
                        retry_after
                    )
                except ValueError:
                    delay = None

            if delay is None:
                delay = (
                    2 ** (attempt - 1)
                    + random.uniform(0, 1)
                )

            logger.warning(
                "Source returned HTTP %d on "
                "attempt %d/%d",
                status,
                attempt,
                max_attempts,
            )

            logger.warning(
                "Retrying source download in %.1f seconds",
                delay,
            )

            time.sleep(delay)

        except URLError as exc:
            if attempt == max_attempts:
                logger.error(
                    "Source download failed after "
                    "%d attempts due to network error: %s",
                    max_attempts,
                    exc,
                )
                raise

            delay = (
                2 ** (attempt - 1)
                + random.uniform(0, 1)
            )

            logger.warning(
                "Network error during source download "
                "on attempt %d/%d: %s",
                attempt,
                max_attempts,
                exc,
            )

            logger.warning(
                "Retrying source download in %.1f seconds",
                delay,
            )

            time.sleep(delay)


def _create_raw_table(
    connection: duckdb.DuckDBPyConnection,
    raw_csv_path: Path,
) -> None:
    """Create the raw_inspection table from the downloaded CSV."""
    connection.execute(
        """
        CREATE OR REPLACE TABLE raw_inspection AS
        SELECT *
        FROM read_csv_auto(
            ?,
            header = true,
            sample_size = -1
        )
        """,
        [str(raw_csv_path)],
    )


def _prepare_cloud_database(
    database_path: Path,
    source_url: str,
    raw_csv_path: Path,
    logger,
) -> None:
    """Create an ephemeral DuckDB database from the source dataset."""

    logger.info(
        "Downloading source dataset"
    )

    logger.info(
        "Source URL: %s",
        source_url,
    )

    _download_source_csv(
        url=source_url,
        destination=raw_csv_path,
        logger=logger,
    )

    logger.info(
        "Source dataset downloaded: %s",
        raw_csv_path,
    )

    connection = duckdb.connect(
        str(database_path)
    )

    try:
        logger.info(
            "Creating raw_inspection table"
        )

        _create_raw_table(
            connection=connection,
            raw_csv_path=raw_csv_path,
        )

        raw_count = connection.execute(
            "SELECT COUNT(*) FROM raw_inspection"
        ).fetchone()[0]

        logger.info(
            "Raw inspection row count: %s",
            raw_count,
        )

    finally:
        connection.close()


def _sync_cloud_artifacts(
    config,
    run_id: str,
    run_directory: Path,
    raw_csv_path: Path | None,
) -> list[str]:
    """Upload durable batch artifacts to the configured store."""

    store = create_artifact_store(
        config
    )

    files = [
        (
            run_directory
            / "restaurant_risk_scores.csv",
            (
                f"predictions/{run_id}/"
                "restaurant_risk_scores.csv"
            ),
        ),
        (
            run_directory
            / "restaurant_priority_queue.csv",
            (
                f"queues/{run_id}/"
                "restaurant_priority_queue.csv"
            ),
        ),
        (
            run_directory
            / "run_metadata.json",
            (
                f"runs/{run_id}/"
                "run_metadata.json"
            ),
        ),
        (
            run_directory
            / "batch_metadata.json",
            (
                f"runs/{run_id}/"
                "batch_metadata.json"
            ),
        ),
        (
            run_directory
            / "pipeline.log",
            (
                f"runs/{run_id}/"
                "pipeline.log"
            ),
        ),
        (
            config.models_directory
            / config.model_path.name,
            (
                f"models/production/"
                f"{config.model_path.name}"
            ),
        ),
        (
            config.models_directory
            / config.calibrator_path.name,
            (
                f"models/production/"
                f"{config.calibrator_path.name}"
            ),
        ),
    ]

    if raw_csv_path is not None:
        files.append(
            (
                raw_csv_path,
                (
                    f"raw/{run_id}/"
                    "dohmh_inspections.csv"
                ),
            )
        )

    uploaded: list[str] = []

    for local_path, key in files:
        store.upload_file(
            local_path=local_path,
            key=key,
        )

        uploaded.append(key)

    return uploaded


def run_batch(
    capacity: int,
) -> int:
    """Run the complete batch pipeline."""

    if capacity <= 0:
        raise ValueError(
            "Capacity must be a positive integer."
        )

    config = load_config(
        PROJECT_ROOT
    )

    started_at = datetime.now(
        UTC
    )

    run_id = started_at.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    run_directory = (
        config.runs_directory
        / run_id
    )

    run_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger = configure_logging(
        run_directory
        / "pipeline.log"
    )

    logger.info(
        "Starting restaurant-risk batch run"
    )

    logger.info(
        "Run ID: %s",
        run_id,
    )

    logger.info(
        "Capacity: %s",
        capacity,
    )

    logger.info(
        "Storage provider: %s",
        config.storage_provider,
    )

    connection = None

    status = "FAILED"

    population_size: int | None = None

    priority_queue_size: int | None = None

    scores_path: str | None = None

    priority_queue_path: str | None = None

    return_code = 1

    try:
        cloud_mode = (
            config.storage_provider.lower()
            == "s3"
        )

        if cloud_mode:
            with tempfile.TemporaryDirectory(
                prefix="restaurant-risk-"
            ) as temp_directory:
                temp_root = Path(
                    temp_directory
                )

                database_path = (
                    temp_root
                    / "restaurant_risk.duckdb"
                )

                raw_csv_path = (
                    temp_root
                    / "dohmh_inspections.csv"
                )

                logger.info(
                    "Cloud batch workspace: %s",
                    temp_root,
                )

                _prepare_cloud_database(
                    database_path=database_path,
                    source_url=config.source_url,
                    raw_csv_path=raw_csv_path,
                    logger=logger,
                )

                connection = duckdb.connect(
                    str(database_path)
                )

                logger.info(
                    "Connected to DuckDB"
                )

                run_transformations(
                    connection=connection,
                    sql_directory=config.sql_directory,
                    logger=logger,
                )

                logger.info(
                    "All transformations completed"
                )

                run_validations(
                    connection=connection,
                    validation_directory=(
                        config.sql_directory
                        / "validation"
                    ),
                    logger=logger,
                )

                logger.info(
                    "All validations completed"
                )

                connection.close()

                connection = None

                logger.info(
                    "DuckDB connection closed"
                )

                df = load_scoring_population(
                    database_path
                )

                population_size = len(
                    df
                )

                logger.info(
                    "Scoring population size: %s",
                    population_size,
                )

                scored, priority_queue = (
                    score_restaurants(
                        df=df,
                        config=config,
                        capacity=capacity,
                    )
                )

                priority_queue_size = len(
                    priority_queue
                )

                logger.info(
                    "Priority queue size: %s",
                    priority_queue_size,
                )

                run_scores_path = (
                    run_directory
                    / "restaurant_risk_scores.csv"
                )

                run_queue_path = (
                    run_directory
                    / "restaurant_priority_queue.csv"
                )

                scored.to_csv(
                    run_scores_path,
                    index=False,
                )

                priority_queue.to_csv(
                    run_queue_path,
                    index=False,
                )

                config.output_directory.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                scored.to_csv(
                    config.output_directory
                    / "restaurant_risk_scores.csv",
                    index=False,
                )

                priority_queue.to_csv(
                    config.output_directory
                    / "restaurant_priority_queue.csv",
                    index=False,
                )

                scores_path = str(
                    run_scores_path
                )

                priority_queue_path = str(
                    run_queue_path
                )

                status = "SUCCESS"

                return_code = 0

                logger.info(
                    "Batch scoring completed successfully"
                )

                completed_at = datetime.now(
                    UTC
                )

                pipeline_metadata = RunMetadata(
                    run_id=run_id,
                    status=status,
                    started_at_utc=(
                        started_at.isoformat()
                    ),
                    completed_at_utc=(
                        completed_at.isoformat()
                    ),
                    duration_seconds=(
                        completed_at
                        - started_at
                    ).total_seconds(),
                    project_name=(
                        config.project_name
                    ),
                    database_path=str(
                        database_path
                    ),
                )

                pipeline_metadata.write(
                    run_directory
                    / "run_metadata.json"
                )

                batch_metadata = BatchRunMetadata(
                    run_id=run_id,
                    status=status,
                    capacity=capacity,
                    population_size=population_size,
                    priority_queue_size=(
                        priority_queue_size
                    ),
                    scores_path=scores_path,
                    priority_queue_path=(
                        priority_queue_path
                    ),
                )

                batch_metadata.write(
                    run_directory
                    / "batch_metadata.json"
                )

                logger.info(
                    "Uploading batch artifacts to S3"
                )

                uploaded = (
                    _sync_cloud_artifacts(
                        config=config,
                        run_id=run_id,
                        run_directory=run_directory,
                        raw_csv_path=raw_csv_path,
                    )
                )

                logger.info(
                    "Uploaded %s artifacts to S3",
                    len(uploaded),
                )

                logger.info(
                    "Batch run completed successfully"
                )

        else:
            if not config.database_path.exists():
                raise PipelineError(
                    "DuckDB database not found: "
                    f"{config.database_path}"
                )

            connection = duckdb.connect(
                str(config.database_path)
            )

            logger.info(
                "Connected to DuckDB"
            )

            run_transformations(
                connection=connection,
                sql_directory=config.sql_directory,
                logger=logger,
            )

            logger.info(
                "All transformations completed"
            )

            run_validations(
                connection=connection,
                validation_directory=(
                    config.sql_directory
                    / "validation"
                ),
                logger=logger,
            )

            logger.info(
                "All validations completed"
            )

            connection.close()

            connection = None

            logger.info(
                "DuckDB connection closed"
            )

            df = load_scoring_population(
                config.database_path
            )

            population_size = len(
                df
            )

            logger.info(
                "Scoring population size: %s",
                population_size,
            )

            scored, priority_queue = (
                score_restaurants(
                    df=df,
                    config=config,
                    capacity=capacity,
                )
            )

            priority_queue_size = len(
                priority_queue
            )

            logger.info(
                "Priority queue size: %s",
                priority_queue_size,
            )

            run_scores_path = (
                run_directory
                / "restaurant_risk_scores.csv"
            )

            run_queue_path = (
                run_directory
                / "restaurant_priority_queue.csv"
            )

            scored.to_csv(
                run_scores_path,
                index=False,
            )

            priority_queue.to_csv(
                run_queue_path,
                index=False,
            )

            config.output_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            scored.to_csv(
                config.output_directory
                / "restaurant_risk_scores.csv",
                index=False,
            )

            priority_queue.to_csv(
                config.output_directory
                / "restaurant_priority_queue.csv",
                index=False,
            )

            scores_path = str(
                run_scores_path
            )

            priority_queue_path = str(
                run_queue_path
            )

            status = "SUCCESS"

            return_code = 0

            logger.info(
                "Batch run completed successfully"
            )

    except (
        PipelineError,
        ModelArtifactError,
        ArtifactStoreError,
        ValueError,
        OSError,
        HTTPError,
        URLError,
    ) as exc:
        logger.error(
            "Batch run failed: %s",
            exc,
        )

        logger.error(
            traceback.format_exc()
        )

        return_code = 1

    finally:
        if connection is not None:
            connection.close()

            logger.info(
                "DuckDB connection closed"
            )

        if not (
            config.storage_provider.lower()
            == "s3"
            and return_code == 0
        ):
            completed_at = datetime.now(
                UTC
            )

            pipeline_metadata = RunMetadata(
                run_id=run_id,
                status=status,
                started_at_utc=(
                    started_at.isoformat()
                ),
                completed_at_utc=(
                    completed_at.isoformat()
                ),
                duration_seconds=(
                    completed_at
                    - started_at
                ).total_seconds(),
                project_name=(
                    config.project_name
                ),
                database_path=str(
                    config.database_path
                ),
            )

            pipeline_metadata.write(
                run_directory
                / "run_metadata.json"
            )

            batch_metadata = BatchRunMetadata(
                run_id=run_id,
                status=status,
                capacity=capacity,
                population_size=population_size,
                priority_queue_size=(
                    priority_queue_size
                ),
                scores_path=scores_path,
                priority_queue_path=(
                    priority_queue_path
                ),
            )

            batch_metadata.write(
                run_directory
                / "batch_metadata.json"
            )

    return return_code


def main() -> None:
    """Run the batch pipeline from the command line."""

    args = parse_args()

    return_code = run_batch(
        capacity=args.capacity
    )

    sys.exit(
        return_code
    )


if __name__ == "__main__":
    main()