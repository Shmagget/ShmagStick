#!/usr/bin/env python3
"""ShmagStick — cross-platform system health scanner.

Detects OS, loads the appropriate platform collector, and launches the
PyQt6 desktop GUI. Requires Python 3.9+.

Usage:
    python shmagstick.py [--profile Everyday|Gaming|Workstation]

Run via run.bat (Windows) or run.sh (Linux/macOS) for automatic venv setup.
"""

from __future__ import annotations

import sys
import argparse

from core.logging_config import configure_logging


def _arguments(argv: list[str]):
    parser = argparse.ArgumentParser(description="Read-only cross-platform system health scanner")
    parser.add_argument("--profile", choices=("Everyday", "Gaming", "Workstation"), default="Everyday")
    parser.add_argument("--device", choices=("Auto", "Desktop", "Laptop"), default="Auto")
    return parser.parse_args(argv)


def main():
    # Check Python version
    if sys.version_info < (3, 9):
        print("Error: Python 3.9+ required.")
        sys.exit(1)

    # Check PyQt6
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("Error: PyQt6 not installed. Run: pip install PyQt6 psutil")
        sys.exit(1)

    # Check platform
    platform_name = sys.platform
    if platform_name not in ("win32", "linux", "darwin"):
        print(f"Error: Unsupported platform: {platform_name}")
        sys.exit(1)

    args = _arguments(sys.argv[1:])
    logger = configure_logging().getChild("entrypoint")
    logger.info("Starting ShmagStick on %s", platform_name)

    # Create application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    # Branding: window / taskbar / dock icon (works in source and frozen builds).
    from PyQt6.QtGui import QIcon
    from core.paths import resource_path

    icon_path = resource_path("assets/icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Import and show main window
    from gui.main_window import MainWindow
    window = MainWindow(initial_profile=args.profile, device_mode=args.device)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
