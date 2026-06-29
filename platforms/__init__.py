"""Platform detection and collector factory."""

import sys

PLATFORM_WINDOWS = sys.platform == "win32"
PLATFORM_LINUX = sys.platform == "linux"
PLATFORM_MACOS = sys.platform == "darwin"

PLATFORM_NAME = {
    "win32": "Windows",
    "linux": "Linux",
    "darwin": "macOS",
}.get(sys.platform, sys.platform)


def get_collector():
    """Return the appropriate metric collector for the current OS."""
    if PLATFORM_WINDOWS:
        from platforms.windows import WindowsCollector
        return WindowsCollector()
    elif PLATFORM_LINUX:
        from platforms.linux import LinuxCollector
        return LinuxCollector()
    elif PLATFORM_MACOS:
        from platforms.macos import MacOSCollector
        return MacOSCollector()
    else:
        raise OSError(f"Unsupported platform: {sys.platform}")
