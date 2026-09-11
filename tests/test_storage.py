from __future__ import annotations

from pathlib import Path

import pytest

from restaurant_risk.storage.artifacts import (
    ArtifactStoreError,
    LocalArtifactStore,
    S3ArtifactStore,
)


def test_local_artifact_store_round_trip(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_text(
        "restaurant-risk",
        encoding="utf-8",
    )

    store = LocalArtifactStore(tmp_path / "store")

    store.upload_file(
        source,
        "runs/test/source.txt",
    )

    assert store.exists(
        "runs/test/source.txt"
    )

    destination = tmp_path / "downloaded.txt"

    store.download_file(
        "runs/test/source.txt",
        destination,
    )

    assert destination.read_text(
        encoding="utf-8"
    ) == "restaurant-risk"


def test_local_store_rejects_path_traversal(tmp_path: Path):
    store = LocalArtifactStore(
        tmp_path / "store"
    )

    with pytest.raises(
        ArtifactStoreError,
        match="Invalid artifact key",
    ):
        store.exists("../secret.txt")


def test_s3_key_prefix():
    store = S3ArtifactStore(
        bucket="example-bucket",
        prefix="restaurant-risk",
        client=object(),
    )

    assert store._key(
        "queues/20260911/queue.csv"
    ) == (
        "restaurant-risk/"
        "queues/20260911/queue.csv"
    )