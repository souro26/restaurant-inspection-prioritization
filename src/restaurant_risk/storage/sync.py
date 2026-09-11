from __future__ import annotations

import argparse
from pathlib import Path

from restaurant_risk.config import load_config
from restaurant_risk.storage.artifacts import (
    ArtifactStoreError,
    create_artifact_store,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Persist restaurant-risk artifacts to the configured store."
    )

    parser.add_argument(
        "--run-id",
        required=True,
        help="Pipeline/batch run ID whose metadata and log should be uploaded.",
    )

    return parser.parse_args()


def sync_artifacts(run_id: str) -> list[str]:
    """Upload the durable artifacts produced by one local batch run."""

    config = load_config(PROJECT_ROOT)
    store = create_artifact_store(config)

    run_directory = config.runs_directory / run_id

    files = [
        (
            config.output_directory / "restaurant_risk_scores.csv",
            f"predictions/{run_id}/restaurant_risk_scores.csv",
        ),
        (
            config.output_directory / "restaurant_priority_queue.csv",
            f"queues/{run_id}/restaurant_priority_queue.csv",
        ),
        (
            run_directory / "run_metadata.json",
            f"runs/{run_id}/run_metadata.json",
        ),
        (
            run_directory / "pipeline.log",
            f"runs/{run_id}/pipeline.log",
        ),
        (
            config.models_directory / config.model_path.name,
            f"models/production/{config.model_path.name}",
        ),
        (
            config.models_directory / config.calibrator_path.name,
            f"models/production/{config.calibrator_path.name}",
        ),
    ]

    raw_source = (
        config.project_root
        / "data"
        / "raw"
        / "dohmh_inspections.csv"
    )

    if raw_source.exists():
        files.append(
            (
                raw_source,
                f"raw/{run_id}/{raw_source.name}",
            )
        )

    uploaded: list[str] = []

    for local_path, key in files:
        store.upload_file(local_path, key)
        uploaded.append(key)

    return uploaded


def main() -> int:
    args = parse_args()

    try:
        uploaded = sync_artifacts(args.run_id)
    except ArtifactStoreError as exc:
        print(f"Artifact sync failed: {exc}")
        return 1

    print(
        f"Uploaded {len(uploaded)} artifacts "
        f"for run {args.run_id}"
    )

    for key in uploaded:
        print(f"  {key}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())