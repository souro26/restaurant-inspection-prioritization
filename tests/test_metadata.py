import json

from restaurant_risk.pipeline.metadata import RunMetadata


def test_run_metadata_writes_json(tmp_path):
    metadata = RunMetadata(
        run_id="20260906T120000Z",
        status="SUCCESS",
        started_at_utc="2026-09-06T12:00:00+00:00",
        completed_at_utc="2026-09-06T12:00:05+00:00",
        duration_seconds=5.0,
        project_name="restaurant-inspection-prioritization",
        database_path="data/restaurant_risk.duckdb",
    )

    output_path = tmp_path / "run_metadata.json"

    metadata.write(output_path)

    assert output_path.exists()

    data = json.loads(
        output_path.read_text(
            encoding="utf-8"
        )
    )

    assert data["run_id"] == "20260906T120000Z"
    assert data["status"] == "SUCCESS"
    assert data["duration_seconds"] == 5.0
    assert (
        data["project_name"]
        == "restaurant-inspection-prioritization"
    )