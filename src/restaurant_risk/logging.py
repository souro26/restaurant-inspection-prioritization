from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(log_file: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("restaurant_risk")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(
            log_file,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger