"""Privacy-conscious rotating application logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.paths import logs_directory


LOGGER_NAME = "shmagstick"


def configure_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    try:
        handler: logging.Handler = RotatingFileHandler(
            logs_directory() / "shmagstick.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            "%Y-%m-%dT%H:%M:%S",
        ))
    except OSError:
        handler = logging.NullHandler()
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def safe_path(path: str | Path) -> str:
    """Avoid writing a user's home directory to logs."""
    try:
        return str(path).replace(str(Path.home()), "~")
    except Exception:
        return "<path unavailable>"
