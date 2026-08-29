from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from restaurant_risk.config import load_yaml
from restaurant_risk.exceptions import PipelineError
from restaurant_risk.logging import configure_logging


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "configs" / "project.yaml"


def resolve_path(project_root: Path, path: str) -> Path:
    """Resolve a project-relative path."""
    resolved = Path(path)

    if not resolved.is_absolute():
        resolved = project_root / resolved

    return resolved.resolve()


def execute_sql_file(
    connection: duckdb.DuckDBPyConnection,
    sql_file: Path,
    logger,
) -> None:
    """Execute a DuckDB SQL script."""
    if not sql_file.exists():
        raise PipelineError(f"SQL file not found: {sql_file}")

    logger.info(
        "Executing SQL: %s",
        sql_file.relative_to(PROJECT_ROOT),
    )

    try:
        sql = sql_file.read_text(encoding="utf-8")
        connection.execute(sql)
    except Exception as exc:
        raise PipelineError(
            f"SQL execution failed: {sql_file}"
        ) from exc


def run_transformations(
    connection: duckdb.DuckDBPyConnection,
    sql_directory: Path,
    logger,
) -> None:
    """Execute SQL transformations in dependency order."""
    transformation_directory = sql_directory / "transformations"

    transformation_files = sorted(
        transformation_directory.glob("*.sql")
    )

    if not transformation_files:
        raise PipelineError(
            f"No transformation SQL files found in "
            f"{transformation_directory}"
        )

    for sql_file in transformation_files:
        execute_sql_file(
            connection,
            sql_file,
            logger,
        )


def run_validations(
    connection: duckdb.DuckDBPyConnection,
    validation_directory: Path,
    logger,
) -> None:
    """Execute all validation SQL scripts."""
    validation_files = sorted(
        validation_directory.glob("*.sql")
    )

    if not validation_files:
        raise PipelineError(
            f"No validation SQL files found in "
            f"{validation_directory}"
        )

    for sql_file in validation_files:
        execute_sql_file(
            connection,
            sql_file,
            logger,
        )


def write_run_metadata(
    run_directory: Path,
    run_id: str,
    status: str,
) -> None:
    """Write metadata describing the pipeline run."""
    metadata = (
        f"run_id={run_id}\n"
        f"status={status}\n"
        f"completed_at_utc="
        f"{datetime.now(timezone.utc).isoformat()}\n"
    )

    metadata_file = run_directory / "run_metadata.txt"

    metadata_file.write_text(
        metadata,
        encoding="utf-8",
    )


def run_pipeline() -> int:
    """Run the complete data transformation and validation pipeline."""
    config = load_yaml(CONFIG_PATH)

    database_path = resolve_path(
        PROJECT_ROOT,
        config["database"]["path"],
    )

    sql_directory = resolve_path(
        PROJECT_ROOT,
        config["pipeline"]["sql_directory"],
    )

    runs_directory = resolve_path(
        PROJECT_ROOT,
        config["artifacts"]["runs_directory"],
    )

    run_id = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    run_directory = runs_directory / run_id
    run_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger = configure_logging(
        run_directory / "pipeline.log"
    )

    logger.info(
        "Starting restaurant-risk data pipeline"
    )
    logger.info("Run ID: %s", run_id)
    logger.info("Database: %s", database_path)
    logger.info("Project root: %s", PROJECT_ROOT)

    connection = None

    try:
        if not database_path.exists():
            raise PipelineError(
                f"DuckDB database not found: {database_path}"
            )

        connection = duckdb.connect(
            str(database_path)
        )

        logger.info("Connected to DuckDB")

        run_transformations(
            connection,
            sql_directory,
            logger,
        )

        logger.info(
            "All transformations completed"
        )

        run_validations(
            connection,
            sql_directory / "validation",
            logger,
        )

        logger.info(
            "All validations completed"
        )

        write_run_metadata(
            run_directory,
            run_id,
            "SUCCESS",
        )

        logger.info(
            "Pipeline completed successfully"
        )

        return 0

    except Exception as exc:
        logger.error(
            "Pipeline failed: %s",
            exc,
        )
        logger.error(
            traceback.format_exc()
        )

        write_run_metadata(
            run_directory,
            run_id,
            "FAILED",
        )

        return 1

    finally:
        if connection is not None:
            connection.close()
            logger.info(
                "DuckDB connection closed"
            )


if __name__ == "__main__":
    sys.exit(run_pipeline())