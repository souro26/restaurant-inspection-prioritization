from __future__ import annotations
from pathlib import Path
import pandas as pd 
import duckdb

MODEL_DATASET_QUERY = """
SELECT
    f.*,
    l.cutoff_inspection_type,
    l.cutoff_is_cycle_initial,
    l.cutoff_is_cycle_reinspection,
    l.target_inspection_id,
    l.target_inspection_date,
    l.target_inspection_type,
    l.days_to_target,
    l.target_high_severity,
    l.target_label
FROM processed.features AS f
INNER JOIN processed.labels AS l
    ON f.cutoff_inspection_id = l.cutoff_inspection_id
"""

def load_modeling_dataset(database_path: Path) -> pd.DataFrame:
    """Load the features and future labels,"""
    connection = duckdb.connect(str(database_path), read_only = True)
    try:
        df = connection.execute(MODEL_DATASET_QUERY).df()
    finally:
        connection.close()
    df.cutoff_date = pd.to_datetime(df.cutoff_date)
    df.target_inspection_date = pd.to_datetime(df.target_inspection_date)

    return df

SCORING_POPULATION_QUERY = """
SELECT *
FROM processed.scoring_population
"""

def load_scoring_population(database_path: Path) -> pd.DataFrame:
    """Load the current restaurant population used for model scoring."""
    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        df = connection.execute(SCORING_POPULATION_QUERY).df()
    finally:
        connection.close()

    df.cutoff_date = pd.to_datetime(df.cutoff_date)

    return df