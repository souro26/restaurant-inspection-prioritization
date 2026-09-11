from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from restaurant_risk.config import ProjectConfig


class ArtifactStoreError(RuntimeError):
    """Raised when persistent artifact storage fails."""


class ArtifactStore(Protocol):
    """Interface for durable artifact storage."""

    def upload_file(self, local_path: Path, key: str) -> None:
        """Upload a local file under a storage key."""

    def download_file(self, key: str, local_path: Path) -> None:
        """Download a storage key to a local file."""

    def exists(self, key: str) -> bool:
        """Return whether a storage key exists."""


class LocalArtifactStore:
    """Filesystem-backed artifact store used for local development/tests."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        relative = Path(key)

        if relative.is_absolute() or ".." in relative.parts:
            raise ArtifactStoreError(f"Invalid artifact key: {key}")

        return self.root / relative

    def upload_file(self, local_path: Path, key: str) -> None:
        if not local_path.is_file():
            raise ArtifactStoreError(f"Artifact does not exist: {local_path}")

        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(local_path.read_bytes())

    def download_file(self, key: str, local_path: Path) -> None:
        source = self._path(key)

        if not source.is_file():
            raise ArtifactStoreError(f"Artifact does not exist: {key}")

        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(source.read_bytes())

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


def _is_aws_storage_error(exc: Exception) -> bool:
    """Identify boto3/botocore errors without importing them in local mode."""
    try:
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        return False

    return isinstance(exc, (BotoCoreError, ClientError))


def _is_missing_s3_object(exc: Exception) -> bool:
    """Return whether an S3 head request reported a missing object."""
    try:
        from botocore.exceptions import ClientError
    except ImportError:
        return False

    if not isinstance(exc, ClientError):
        return False

    return exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}


class S3ArtifactStore:
    """Amazon S3-backed artifact store."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        region: str | None = None,
        client=None,
    ) -> None:
        if not bucket:
            raise ArtifactStoreError("S3 bucket must be configured")

        self.bucket = bucket
        self.prefix = prefix.strip("/")

        if client is None:
            try:
                import boto3
            except ImportError as exc:
                raise ArtifactStoreError(
                    "boto3 is required for S3 storage. Install project dependencies."
                ) from exc

            client = boto3.client("s3", region_name=region)

        self.client = client

    def _key(self, key: str) -> str:
        relative = Path(key)

        if relative.is_absolute() or ".." in relative.parts:
            raise ArtifactStoreError(f"Invalid artifact key: {key}")

        normalized = relative.as_posix().lstrip("/")

        if not normalized:
            raise ArtifactStoreError("Artifact key cannot be empty")

        return (
            f"{self.prefix}/{normalized}"
            if self.prefix
            else normalized
        )

    def upload_file(self, local_path: Path, key: str) -> None:
        if not local_path.is_file():
            raise ArtifactStoreError(f"Artifact does not exist: {local_path}")

        try:
            self.client.upload_file(
                str(local_path),
                self.bucket,
                self._key(key),
            )
        except Exception as exc:
            if not _is_aws_storage_error(exc):
                raise

            raise ArtifactStoreError(
                f"Failed to upload artifact: "
                f"s3://{self.bucket}/{self._key(key)}"
            ) from exc

    def download_file(self, key: str, local_path: Path) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self.client.download_file(
                self.bucket,
                self._key(key),
                str(local_path),
            )
        except Exception as exc:
            if not _is_aws_storage_error(exc):
                raise

            raise ArtifactStoreError(
                f"Failed to download artifact: "
                f"s3://{self.bucket}/{self._key(key)}"
            ) from exc

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(
                Bucket=self.bucket,
                Key=self._key(key),
            )
        except Exception as exc:
            if _is_missing_s3_object(exc):
                return False

            if not _is_aws_storage_error(exc):
                raise

            raise ArtifactStoreError(
                f"Failed to inspect artifact: "
                f"s3://{self.bucket}/{self._key(key)}"
            ) from exc

        return True


def create_artifact_store(config: ProjectConfig) -> ArtifactStore:
    """Create the configured persistent artifact store."""

    provider = os.environ.get(
        "RESTAURANT_RISK_STORAGE_PROVIDER",
        config.storage_provider,
    ).lower()

    if provider == "local":
        root = Path(
            os.environ.get(
                "RESTAURANT_RISK_LOCAL_ARTIFACT_ROOT",
                str(config.project_root / ".artifact_store"),
            )
        )

        return LocalArtifactStore(root)

    if provider == "s3":
        bucket = os.environ.get(
            "RESTAURANT_RISK_S3_BUCKET",
            config.s3_bucket,
        )

        prefix = os.environ.get(
            "RESTAURANT_RISK_S3_PREFIX",
            config.s3_prefix,
        )

        region = os.environ.get(
            "AWS_REGION",
            config.s3_region,
        )

        return S3ArtifactStore(
            bucket=bucket,
            prefix=prefix,
            region=region,
        )

    raise ArtifactStoreError(
        f"Unsupported storage provider: {provider}"
    )