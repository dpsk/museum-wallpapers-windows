"""Pick the platform implementation for this machine."""

import os
import sys

from .base import DEFAULT_MONITOR, DevPlatform, Monitor, Platform, largest

__all__ = ["DEFAULT_MONITOR", "DevPlatform", "Monitor", "Platform", "current", "largest"]


def current():
    """WindowsPlatform on Windows, DevPlatform elsewhere or when
    MUSEUM_WALLPAPERS_PLATFORM=dev (to try things without touching the desktop)."""
    if sys.platform == "win32" and os.environ.get("MUSEUM_WALLPAPERS_PLATFORM") != "dev":
        from .windows import WindowsPlatform
        return WindowsPlatform()
    return DevPlatform()
