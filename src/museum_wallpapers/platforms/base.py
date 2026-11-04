"""What the core needs from the operating system, and a stand-in used for
development and tests on machines that are not Windows."""

import json
import locale
import os
import sys
import webbrowser
from pathlib import Path
from typing import NamedTuple


class Monitor(NamedTuple):
    """One active display. `id` is what set_wallpaper keys images by;
    width and height are physical pixels; `inset` is (left, top, right,
    bottom) pixels covered by the taskbar, so a caption stays visible."""

    id: str
    width: int
    height: int
    inset: tuple = (0, 0, 0, 0)


DEFAULT_MONITOR = Monitor("default", 3840, 2160)


def largest(monitors):
    return max(monitors, key=lambda m: (m.width * m.height, m.width)) if monitors else DEFAULT_MONITOR


def language_code(name):
    """'ru_RU', 'ru-RU' or 'Russian_Russia' (Windows) to 'ru'; '' when unknown."""
    name = (name or "").split(".")[0]
    code = name.replace("_", "-").split("-")[0].lower()
    if len(code) in (2, 3) and code.isalpha():
        return code
    windows_names = {"russian": "ru", "english": "en", "german": "de", "french": "fr", "spanish": "es",
                     "italian": "it", "ukrainian": "uk", "polish": "pl", "dutch": "nl", "portuguese": "pt"}
    return windows_names.get(code, "")


class Platform:
    """Base behaviour; subclasses override what their OS does differently."""

    name = "base"

    def paths(self):
        """Folders: settings (`config`), `cache`, `state`, and `pictures`
        (the parent of the default collection folder)."""
        root = Path(os.environ["MUSEUM_WALLPAPERS_HOME"]) if os.environ.get("MUSEUM_WALLPAPERS_HOME") else None
        if root:
            return {"config": root / "config", "cache": root / "cache", "state": root / "state",
                    "pictures": root / "Pictures"}
        home = Path.home()
        return {
            "config": Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "museum-wallpapers",
            "cache": Path(os.environ.get("XDG_CACHE_HOME", home / ".cache")) / "museum-wallpapers",
            "state": Path(os.environ.get("XDG_STATE_HOME", home / ".local/state")) / "museum-wallpapers",
            "pictures": home / "Pictures",
        }

    def setup(self):
        """Process-wide setup before any window or monitor query."""

    def monitors(self):
        return [DEFAULT_MONITOR]

    def set_wallpaper(self, images):
        """Show images: {monitor id: path}."""
        raise NotImplementedError

    def current_wallpaper(self):
        """The image on the largest monitor, or None."""
        return None

    def notify(self, title, body, actions=(), image=None, on_click=None):
        """A notification; `actions` are (label, callback) buttons, `image` a
        picture to show in it, `on_click` what clicking the notification does."""
        print(f"[notification] {title}: {body}", file=sys.stderr)

    def open_url(self, url):
        webbrowser.open(url)

    def open_folder(self, path):
        self.open_url(Path(path).as_uri())

    def ui_language(self):
        try:
            name = locale.getlocale()[0] or os.environ.get("LANG", "")
        except ValueError:
            name = os.environ.get("LANG", "")
        return language_code(name) or "en"

    def work_area(self):
        """(left, top, right, bottom) of the primary screen above the taskbar, or None."""
        return None

    packaged = False

    def launched_at_startup(self):
        """Started automatically at sign-in rather than by the user."""
        return False

    def autostart_enabled(self):
        return False

    def set_autostart(self, enabled):
        raise NotImplementedError

    def caption_fonts(self):
        """(title font path, body font path) for the caption; None for Pillow's default."""
        candidates = (
            ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
             "/usr/share/fonts/TTF/DejaVuSerif-Italic.ttf"),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/TTF/DejaVuSans.ttf"),
        )
        return tuple(next((p for p in group if os.path.exists(p)), None) for group in candidates)


class DevPlatform(Platform):
    """For development off Windows: the "wallpaper" is a JSON file naming the
    image per monitor, so the whole rotation can run and be inspected. The
    screen size comes from MUSEUM_WALLPAPERS_SCREEN (e.g. 2560x1440,1920x1080)."""

    name = "dev"

    def _wallpaper_file(self):
        return Path(self.paths()["state"]) / "dev-wallpaper.json"

    def monitors(self):
        spec = os.environ.get("MUSEUM_WALLPAPERS_SCREEN", "")
        result = []
        for n, size in enumerate(s for s in spec.split(",") if s.strip()):
            try:
                width, height = (int(x) for x in size.lower().split("x"))
            except ValueError:
                continue
            result.append(Monitor(f"monitor-{n + 1}", width, height, (0, 0, 0, round(height * 0.045))))
        return result or [Monitor("monitor-1", 3840, 2160, (0, 0, 0, 96))]

    def set_wallpaper(self, images):
        path = self._wallpaper_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({k: str(v) for k, v in images.items()}, indent=2))

    def current_wallpaper(self):
        try:
            images = json.loads(self._wallpaper_file().read_text())
        except (OSError, ValueError):
            return None
        wanted = largest(self.monitors()).id
        value = images.get(wanted) or next(iter(images.values()), None)
        return Path(value) if value else None
