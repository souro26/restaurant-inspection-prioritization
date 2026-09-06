import duckdb
import pytest

from restaurant_risk.exceptions import (
    TransformationError,
    ValidationError,
)
from restaurant_risk.pipeline.run_data_pipeline import (
    run_transformations,
    run_validations,
)


class TestLogger:
    """Minimal logger for testing pipeline functions."""

    def info(self, *args, **kwargs):
        """Accept informational log messages."""
        return

    def error(self, *args, **kwargs):
        """Accept error log messages."""
        return


@pytest.fixture
def connection():
    """Provide an in-memory DuckDB connection."""
    connection = duckdb.connect(":memory:")

    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def logger():
    """Provide a minimal test logger."""
    return TestLogger()


def test_run_transformations_rejects_missing_directory(
    connection,
    logger,
    tmp_path,
):
    """Missing transformation SQL should fail explicitly."""
    sql_directory = tmp_path / "sql"

    with pytest.raises(
        TransformationError,
        match="No transformation SQL files found",
    ):
        run_transformations(
            connection=connection,
            sql_directory=sql_directory,
            logger=logger,
        )


def test_run_transformations_rejects_invalid_sql(
    connection,
    logger,
    tmp_path,
):
    """Invalid transformation SQL should raise TransformationError."""
    transformation_directory = tmp_path / "sql" / "transformations"
    transformation_directory.mkdir(
        parents=True,
    )

    sql_file = transformation_directory / "01_invalid.sql"
    sql_file.write_text(
        "THIS IS NOT VALID SQL;",
        encoding="utf-8",
    )

    with pytest.raises(
        TransformationError,
        match="SQL execution failed",
    ):
        run_transformations(
            connection=connection,
            sql_directory=tmp_path / "sql",
            logger=logger,
        )


def test_run_validations_rejects_missing_directory(
    connection,
    logger,
    tmp_path,
):
    """Missing validation SQL should fail explicitly."""
    validation_directory = tmp_path / "validation"

    with pytest.raises(
        ValidationError,
        match="No validation SQL files found",
    ):
        run_validations(
            connection=connection,
            validation_directory=validation_directory,
            logger=logger,
        )


def test_run_validations_rejects_invalid_sql(
    connection,
    logger,
    tmp_path,
):
    """Invalid validation SQL should raise ValidationError."""
    validation_directory = tmp_path / "validation"
    validation_directory.mkdir(
        parents=True,
    )

    sql_file = validation_directory / "01_invalid.sql"
    sql_file.write_text(
        "THIS IS NOT VALID SQL;",
        encoding="utf-8",
    )

    with pytest.raises(
        ValidationError,
        match="SQL execution failed",
    ):
        run_validations(
            connection=connection,
            validation_directory=validation_directory,
            logger=logger,
        )
