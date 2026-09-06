from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response returned by the health endpoint."""

    status: str


class ModelInfoResponse(BaseModel):
    """Response describing the loaded model artifacts."""

    model_name: str
    model_filename: str
    calibrator_filename: str
    feature_count: int


class ScoringStatusResponse(BaseModel):
    """Response describing the current scoring population."""

    status: str
    population_size: int
    latest_scoring_output: str


class PriorityQueueRequest(BaseModel):
    """Request for a capacity-constrained priority queue."""

    capacity: int = Field(
        gt=0,
        description="Maximum number of restaurants to return.",
    )


class PriorityRestaurant(BaseModel):
    """A restaurant included in the priority queue."""

    camis: int | str
    restaurant_name: str | None = None
    borough: str | None = None
    cuisine_description: str | None = None
    cutoff_date: datetime | None = None
    history_depth_bucket: str | None = None
    raw_logistic_probability: float
    calibrated_high_severity_probability: float
    priority_rank: int


class PriorityQueueResponse(BaseModel):
    """Response containing the requested priority queue."""

    capacity: int
    population_size: int
    generated_at: datetime
    restaurants: list[PriorityRestaurant]
