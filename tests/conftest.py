from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from restaurant_risk.api.app import create_app
from restaurant_risk.config import load_config
from restaurant_risk.modeling.features import MODEL_FEATURES

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def create_scoring_fixture(
    database_path: Path,
) -> None:
    """Create a minimal scoring population for API tests."""
    connection = duckdb.connect(str(database_path))

    try:
        numeric_features = [
            feature
            for feature in MODEL_FEATURES
            if feature
            not in {
                "borough",
                "cuisine_description",
                "history_depth_bucket",
            }
        ]

        columns = [
            '"camis" BIGINT',
            '"restaurant_name" VARCHAR',
            '"borough" VARCHAR',
            '"cuisine_description" VARCHAR',
            '"cutoff_date" DATE',
            '"history_depth_bucket" VARCHAR',
        ]

        columns.extend(
            f'"{feature}" DOUBLE'
            for feature in numeric_features
        )

        connection.execute(
            "CREATE SCHEMA processed"
        )

        connection.execute(
            f"""
            CREATE TABLE processed.scoring_population (
                {", ".join(columns)}
            )
            """
        )

        rows = []

        for index in range(5):
            row = {
                "camis": 90000000 + index,
                "restaurant_name": (
                    f"Test Restaurant {index + 1}"
                ),
                "borough": "Manhattan",
                "cuisine_description": "Test Cuisine",
                "cutoff_date": "2026-08-22",
                "history_depth_bucket": (
                    "1" if index == 0 else "2-3"
                ),
            }

            for feature in numeric_features:
                row[feature] = float(index + 1)

            rows.append(row)

        insert_columns = [
            "camis",
            "restaurant_name",
            "borough",
            "cuisine_description",
            "cutoff_date",
            "history_depth_bucket",
            *numeric_features,
        ]

        placeholders = ", ".join(
            ["?"] * len(insert_columns)
        )

        connection.executemany(
            f"""
            INSERT INTO processed.scoring_population (
                {", ".join(f'"{column}"' for column in insert_columns)}
            )
            VALUES ({placeholders})
            """,
            [
                [row[column] for column in insert_columns]
                for row in rows
            ],
        )
    finally:
        connection.close()


@pytest.fixture
def api_client(
    tmp_path: Path,
) -> TestClient:
    """Create a FastAPI client backed by an isolated test database."""
    database_path = tmp_path / "restaurant_risk_test.duckdb"

    create_scoring_fixture(database_path)

    base_config = load_config(PROJECT_ROOT)

    test_config = replace(
        base_config,
        database_path=database_path,
        output_directory=tmp_path / "output",
    )

    app = create_app(
        config=test_config,
    )

    return TestClient(app)
