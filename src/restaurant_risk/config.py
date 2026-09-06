from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class ConfigurationError(Exception):
    """Raised when project configuration is invalid."""


@dataclass(frozen=True)
class ProjectConfig:
    """Resolved configuration for the restaurant risk project."""

    project_root: Path

    project_name: str
    random_seed: int
    timezone: str

    source_dataset_id: str
    source_name: str
    source_url: str

    database_path: Path
    sql_directory: Path
    raw_table: str

    runs_directory: Path
    models_directory: Path
    reports_directory: Path
    output_directory: Path

    model_path: Path
    calibrator_path: Path


def load_yaml(path: Path) -> dict:
    """Load a YAML configuration file."""
    if not path.exists():
        raise ConfigurationError(
            f"Configuration file does not exist: {path}"
        )

    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"Failed to parse YAML configuration: {path}"
        ) from exc

    if not isinstance(data, dict):
        raise ConfigurationError(
            f"Configuration must contain a YAML mapping: {path}"
        )

    return data


def _resolve_path(project_root: Path, value: str) -> Path:
    """Resolve a project-relative path."""
    path = Path(value)

    if path.is_absolute():
        return path

    return project_root / path


def load_config(project_root: Path) -> ProjectConfig:
    """Load and validate project configuration."""
    project_root = project_root.resolve()
    config_path = project_root / "configs" / "project.yaml"

    config = load_yaml(config_path)

    try:
        project = config["project"]
        source = config["source"]
        database = config["database"]
        pipeline = config["pipeline"]
        artifacts = config["artifacts"]
        model = config["model"]

        models_directory = _resolve_path(
            project_root,
            artifacts["models_directory"],
        )

        return ProjectConfig(
            project_root=project_root,
            project_name=project["name"],
            random_seed=int(project["random_seed"]),
            timezone=project["timezone"],
            source_dataset_id=source["dataset_id"],
            source_name=source["source_name"],
            source_url=source["bulk_csv_url"],
            database_path=_resolve_path(
                project_root,
                database["path"],
            ),
            sql_directory=_resolve_path(
                project_root,
                pipeline["sql_directory"],
            ),
            raw_table=pipeline["raw_table"],
            runs_directory=_resolve_path(
                project_root,
                artifacts["runs_directory"],
            ),
            models_directory=models_directory,
            reports_directory=_resolve_path(
                project_root,
                artifacts["reports_directory"],
            ),
            output_directory=_resolve_path(
                project_root,
                artifacts["output_directory"],
            ),
            model_path=models_directory / model["model_filename"],
            calibrator_path=models_directory / model["calibrator_filename"],
        )

    except KeyError as exc:
        raise ConfigurationError(
            f"Missing required configuration key: {exc}"
        ) from exc