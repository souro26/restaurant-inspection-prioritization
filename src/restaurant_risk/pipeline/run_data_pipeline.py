from __future__ import annotations

import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from restaurant_risk.config import load_config
from restaurant_risk.exceptions import (
    PipelineError,
    TransformationError,
    ValidationError,
)
from restaurant_risk.logging import configure_logging
from restaurant_risk.pipeline.metadata import RunMetadata

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def execute_sql_file(
    connection: duckdb.DuckDBPyConnection,
    sql_file: Path,
    logger,
    error_type: type[PipelineError],
) -> None:
    """Execute a DuckDB SQL script."""
    if not sql_file.exists():
        raise error_type(f"SQL file not found: {sql_file}")

    try:
        display_path = sql_file.relative_to(PROJECT_ROOT)
    except ValueError:
        display_path = sql_file

    logger.info(
        "Executing SQL: %s",
        display_path,
    )

    try:
        sql = sql_file.read_text(encoding="utf-8")
        connection.execute(sql)
    except duckdb.Error as exc:
        raise error_type(f"SQL execution failed: {sql_file}") from exc
    except OSError as exc:
        raise error_type(f"Unable to read SQL file: {sql_file}") from exc


def run_transformations(
    connection: duckdb.DuckDBPyConnection,
    sql_directory: Path,
    logger,
) -> None:
    """Execute all transformation SQL scripts."""
    transformation_directory = sql_directory / "transformations"

    transformation_files = sorted(transformation_directory.glob("*.sql"))

    if not transformation_files:
        raise TransformationError(
            f"No transformation SQL files found: {transformation_directory}"
        )

    for sql_file in transformation_files:
        execute_sql_file(
            connection=connection,
            sql_file=sql_file,
            logger=logger,
            error_type=TransformationError,
        )


def run_validations(
    connection: duckdb.DuckDBPyConnection,
    validation_directory: Path,
    logger,
) -> None:
    """Execute all validation SQL scripts."""
    validation_files = sorted(validation_directory.glob("*.sql"))

    if not validation_files:
        raise ValidationError(f"No validation SQL files found: {validation_directory}")

    for sql_file in validation_files:
        execute_sql_file(
            connection=connection,
            sql_file=sql_file,
            logger=logger,
            error_type=ValidationError,
        )


def write_run_metadata(
    metadata: RunMetadata,
    run_directory: Path,
) -> None:
    """Write metadata for a pipeline run."""
    metadata.write(run_directory / "run_metadata.json")


def run_pipeline() -> int:
    """Run the complete data pipeline."""
    config = load_config(PROJECT_ROOT)

    database_path = config.database_path
    sql_directory = config.sql_directory
    runs_directory = config.runs_directory

    started_at = datetime.now(UTC)

    run_id = started_at.strftime("%Y%m%dT%H%M%SZ")

    run_directory = runs_directory / run_id

    run_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger = configure_logging(run_directory / "pipeline.log")

    logger.info("Starting restaurant-risk data pipeline")
    logger.info(
        "Run ID: %s",
        run_id,
    )
    logger.info(
        "Database: %s",
        database_path,
    )
    logger.info(
        "Project root: %s",
        PROJECT_ROOT,
    )

    connection = None

    try:
        if not database_path.exists():
            raise PipelineError(f"DuckDB database not found: {database_path}")

        connection = duckdb.connect(str(database_path))

        logger.info("Connected to DuckDB")

        run_transformations(
            connection=connection,
            sql_directory=sql_directory,
            logger=logger,
        )

        logger.info("All transformations completed")

        run_validations(
            connection=connection,
            validation_directory=(sql_directory / "validation"),
            logger=logger,
        )

        logger.info("All validations completed")

        completed_at = datetime.now(UTC)

        metadata = RunMetadata(
            run_id=run_id,
            status="SUCCESS",
            started_at_utc=(started_at.isoformat()),
            completed_at_utc=(completed_at.isoformat()),
            duration_seconds=(completed_at - started_at).total_seconds(),
            project_name=config.project_name,
            database_path=str(database_path),
        )

        write_run_metadata(
            metadata,
            run_directory,
        )

        logger.info("Pipeline completed successfully")

        return 0

    except PipelineError as exc:
        completed_at = datetime.now(UTC)

        logger.error(
            "Pipeline failed: %s",
            exc,
        )
        logger.error(traceback.format_exc())

        metadata = RunMetadata(
            run_id=run_id,
            status="FAILED",
            started_at_utc=(started_at.isoformat()),
            completed_at_utc=(completed_at.isoformat()),
            duration_seconds=(completed_at - started_at).total_seconds(),
            project_name=config.project_name,
            database_path=str(database_path),
        )

        write_run_metadata(
            metadata,
            run_directory,
        )

        return 1

    finally:
        if connection is not None:
            connection.close()

            logger.info("DuckDB connection closed")


if __name__ == "__main__":
    sys.exit(run_pipeline())
