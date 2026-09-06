from pathlib import Path

from restaurant_risk.config import ProjectConfig, load_config


def test_load_project_config():
    project_root = Path(__file__).resolve().parents[1]

    config = load_config(project_root)

    assert isinstance(config, ProjectConfig)

    assert config.project_name == "restaurant-inspection-prioritization"
    assert config.random_seed == 42

    assert config.database_path == (project_root / "data" / "restaurant_risk.duckdb")

    assert config.sql_directory == project_root / "sql"

    assert config.model_path == (
        project_root / "models" / "logistic_regression_C1.joblib"
    )

    assert config.calibrator_path == (
        project_root / "models" / "logistic_regression_C1_sigmoid_calibrator.joblib"
    )

    assert config.output_directory == project_root / "output"
