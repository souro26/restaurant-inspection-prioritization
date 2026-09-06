from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunMetadata:
    """Metadata describing one pipeline execution."""

    run_id: str
    status: str
    started_at_utc: str
    completed_at_utc: str
    duration_seconds: float

    project_name: str
    database_path: str

    def write(self, path: Path) -> None:
        """Write metadata as JSON."""
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                asdict(self),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )