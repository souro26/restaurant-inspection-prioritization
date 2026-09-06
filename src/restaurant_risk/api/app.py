from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from restaurant_risk.api.schemas import (
    HealthResponse,
    ModelInfoResponse,
    PriorityQueueRequest,
    PriorityQueueResponse,
    PriorityRestaurant,
    ScoringStatusResponse,
)
from restaurant_risk.api.service import ScoringService
from restaurant_risk.config import load_config
from restaurant_risk.exceptions import PipelineError
from restaurant_risk.modeling.artifacts import ModelArtifactError

PROJECT_ROOT = Path(__file__).resolve().parents[3]

logger = logging.getLogger("restaurant_risk.api")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = load_config(PROJECT_ROOT)

    scoring_service = ScoringService(config)

    app = FastAPI(
        title="Restaurant Inspection Prioritization API",
        description=(
            "API for serving the frozen restaurant "
            "inspection risk-scoring model and "
            "capacity-constrained inspection "
            "priority queues."
        ),
        version="0.1.0",
    )

    @app.middleware("http")
    async def log_request(
        request: Request,
        call_next,
    ):
        """Log HTTP request duration."""
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000

            logger.exception(
                "%s %s | unhandled exception | %.2f ms",
                request.method,
                request.url.path,
                duration_ms,
            )

            raise

        duration_ms = (time.perf_counter() - started_at) * 1000

        logger.info(
            "%s %s | %s | %.2f ms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["system"],
        summary="Check API health",
    )
    def health() -> HealthResponse:
        """Return application health."""
        return HealthResponse(status="ok")

    @app.get(
        "/model-info",
        response_model=ModelInfoResponse,
        tags=["system"],
        summary="Get model information",
    )
    def model_info() -> ModelInfoResponse:
        """Return information about the model artifacts."""
        try:
            return ModelInfoResponse(**scoring_service.get_model_info())
        except ModelArtifactError as exc:
            logger.error(
                "Model artifacts unavailable: %s",
                exc,
            )

            raise HTTPException(
                status_code=503,
                detail=str(exc),
            ) from exc

    @app.get(
        "/scoring-status",
        response_model=ScoringStatusResponse,
        tags=["scoring"],
        summary="Get scoring status",
    )
    def scoring_status() -> ScoringStatusResponse:
        """Return the current scoring population status."""
        try:
            return ScoringStatusResponse(**scoring_service.get_scoring_status())
        except PipelineError as exc:
            logger.error(
                "Scoring population unavailable: %s",
                exc,
            )

            raise HTTPException(
                status_code=503,
                detail=str(exc),
            ) from exc

    @app.post(
        "/priority-queue",
        response_model=PriorityQueueResponse,
        tags=["scoring"],
        summary="Generate an inspection priority queue",
    )
    def priority_queue(
        request: PriorityQueueRequest,
    ) -> PriorityQueueResponse:
        """Generate a capacity-constrained priority queue."""
        try:
            queue, population_size = scoring_service.generate_priority_queue(
                capacity=request.capacity
            )

        except ValueError as exc:
            logger.warning(
                "Invalid priority queue request: %s",
                exc,
            )

            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except (
            ModelArtifactError,
            PipelineError,
        ) as exc:
            logger.error(
                "Priority queue unavailable: %s",
                exc,
            )

            raise HTTPException(
                status_code=503,
                detail=str(exc),
            ) from exc

        restaurants = [
            PriorityRestaurant(**record) for record in queue.to_dict(orient="records")
        ]

        return PriorityQueueResponse(
            capacity=request.capacity,
            population_size=population_size,
            generated_at=datetime.now(UTC),
            restaurants=restaurants,
        )

    return app


app = create_app()
