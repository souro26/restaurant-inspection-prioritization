from pathlib import Path

from fastapi.testclient import TestClient

from restaurant_risk.config import load_config
from restaurant_risk.modeling.artifacts import (
    load_model_artifacts,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_health(
    api_client: TestClient,
):
    """Health endpoint should return a successful response."""
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_model_info(
    api_client: TestClient,
):
    """Model info should match the artifact contract."""
    response = api_client.get("/model-info")

    assert response.status_code == 200

    data = response.json()

    config = load_config(PROJECT_ROOT)

    artifacts = load_model_artifacts(config)

    assert data["model_name"] == (
        "logistic_regression_C1"
    )

    assert data["model_filename"] == (
        "logistic_regression_C1.joblib"
    )

    assert data["calibrator_filename"] == (
        "logistic_regression_C1_sigmoid_calibrator.joblib"
    )

    assert data["feature_count"] == (
        len(artifacts.feature_names)
    )


def test_scoring_status(
    api_client: TestClient,
):
    """Scoring status should describe the test population."""
    response = api_client.get("/scoring-status")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "no_scoring_output"
    assert data["population_size"] == 5
    assert data["latest_scoring_output"]


def test_priority_queue_rejects_zero_capacity(
    api_client: TestClient,
):
    """Zero capacity should be rejected by request validation."""
    response = api_client.post(
        "/priority-queue",
        json={"capacity": 0},
    )

    assert response.status_code == 422


def test_priority_queue_rejects_negative_capacity(
    api_client: TestClient,
):
    """Negative capacity should be rejected by request validation."""
    response = api_client.post(
        "/priority-queue",
        json={"capacity": -1},
    )

    assert response.status_code == 422


def test_priority_queue_rejects_missing_capacity(
    api_client: TestClient,
):
    """Missing capacity should be rejected by request validation."""
    response = api_client.post(
        "/priority-queue",
        json={},
    )

    assert response.status_code == 422


def test_priority_queue(
    api_client: TestClient,
):
    """Priority queue should contain the requested top-N restaurants."""
    response = api_client.post(
        "/priority-queue",
        json={"capacity": 5},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["capacity"] == 5
    assert data["population_size"] == 5
    assert len(data["restaurants"]) == 5

    assert [
        restaurant["priority_rank"]
        for restaurant in data["restaurants"]
    ] == [
        1,
        2,
        3,
        4,
        5,
    ]

    probabilities = [
        restaurant[
            "calibrated_high_severity_probability"
        ]
        for restaurant in data["restaurants"]
    ]

    assert probabilities == sorted(
        probabilities,
        reverse=True,
    )


def test_openapi_documentation(
    api_client: TestClient,
):
    """OpenAPI documentation should expose the API endpoints."""
    response = api_client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "/health" in paths
    assert "/model-info" in paths
    assert "/scoring-status" in paths
    assert "/priority-queue" in paths


def test_priority_queue_returns_503_when_database_is_unavailable(
    api_client: TestClient,
    monkeypatch,
):
    """Unavailable scoring data should return HTTP 503."""
    from restaurant_risk.exceptions import SourceDataError

    def raise_source_error(self):
        raise SourceDataError(
            "Unable to open DuckDB database."
        )

    monkeypatch.setattr(
        "restaurant_risk.api.service.ScoringService.load_population",
        raise_source_error,
    )

    response = api_client.post(
        "/priority-queue",
        json={"capacity": 5},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Unable to open DuckDB database."
    )