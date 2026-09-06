from __future__ import annotations

import pandas as pd

from restaurant_risk.config import ProjectConfig
from restaurant_risk.dataset.load import load_scoring_population
from restaurant_risk.modeling.artifacts import load_model_artifacts
from restaurant_risk.score_restaurants import score_restaurants


class ScoringService:
    """Application service for restaurant risk scoring."""

    def __init__(self, config: ProjectConfig) -> None:
        """Initialize the scoring service."""
        self.config = config

    def load_population(self) -> pd.DataFrame:
        """Load the current scoring population."""
        return load_scoring_population(self.config.database_path)

    def get_model_info(self) -> dict[str, object]:
        """Return metadata for the frozen model artifacts."""
        artifacts = load_model_artifacts(self.config)

        return {
            "model_name": self.config.model_path.stem,
            "model_filename": self.config.model_path.name,
            "calibrator_filename": (self.config.calibrator_path.name),
            "feature_count": len(artifacts.feature_names),
        }

    def get_scoring_status(
        self,
    ) -> dict[str, object]:
        """Return the current scoring population status."""
        population = self.load_population()

        output_path = self.config.output_directory / "restaurant_priority_queue.csv"

        return {
            "status": ("ready" if output_path.exists() else "no_scoring_output"),
            "population_size": len(population),
            "latest_scoring_output": str(output_path),
        }

    def generate_priority_queue(
        self,
        capacity: int,
    ) -> tuple[pd.DataFrame, int]:
        """Generate a capacity-constrained priority queue."""
        population = self.load_population()

        _, priority_queue = score_restaurants(
            df=population,
            config=self.config,
            capacity=capacity,
        )

        return priority_queue, len(population)


def create_scoring_service(
    config: ProjectConfig,
) -> ScoringService:
    """Create a scoring service from project configuration."""
    return ScoringService(config)
