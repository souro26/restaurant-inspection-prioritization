from __future__ import annotations

from pathlib import Path

import yaml


def load_yaml(path: Path) -> dict:
    """Load a YAML configuration file."""
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}