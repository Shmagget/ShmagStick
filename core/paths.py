"""Portable paths that keep reports and logs beside the application."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def application_root() -> Path:
    override = os.environ.get("SHMAGSTICK_HOME")
    if override:
        return Path(override).expanduser().resolve()

    if getattr(sys, "frozen", False):
        # Standalone build: keep reports and logs next to the executable.
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def resource_path(relative: str) -> Path:
    """Locate a bundled read-only resource (e.g. assets/icon.png).

    In a PyInstaller build, bundled data lives in the temporary extraction
    directory exposed as ``sys._MEIPASS``. From source, it sits beside the
    project root. This is distinct from :func:`application_root`, which points
    at the *writable* location next to the executable.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent.parent / relative


def data_directory(name: str) -> Path:
    path = application_root() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def reports_directory() -> Path:
    return data_directory("Reports")


def logs_directory() -> Path:
    return data_directory("logs")
