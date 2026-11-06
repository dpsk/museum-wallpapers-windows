"""Import the core against a throwaway home and the development platform, so
tests never touch the real desktop, settings or cache."""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ["MUSEUM_WALLPAPERS_PLATFORM"] = "dev"
os.environ.setdefault("MUSEUM_WALLPAPERS_HOME", tempfile.mkdtemp(prefix="museum-wallpapers-test-"))
# No built-in painter lists unless a test provides them (a local build leaves some in src).
os.environ["MUSEUM_WALLPAPERS_SEED"] = str(Path(os.environ["MUSEUM_WALLPAPERS_HOME"]) / "no-seed")

from museum_wallpapers import core, framing, platforms, strings  # noqa: E402
from museum_wallpapers import filelock as filelock_module  # noqa: E402
from museum_wallpapers import app as app_module  # noqa: E402
from museum_wallpapers.platforms import Monitor  # noqa: E402

# Helper commands never start real processes in tests.
core.RUNNER = lambda command: None



def _no_network(url, *args, **kwargs):
    raise OSError(f"no network in tests: {url}")


# Tests never reach Wikimedia: a test that needs an answer patches http_json
# itself; anything else (the language check of the default "only" setting,
# say) sees a failed request, as offline.
core.http_json = _no_network

class FakePlatform(platforms.Platform):
    """Records what the core asks of the OS."""

    name = "fake"

    def __init__(self, monitors=None, language="en"):
        self.current = None
        self.walls = []
        self.notifications = []
        self.opened = []
        self.language = language
        self._monitors = monitors or [Monitor("m1", 384, 216, (0, 0, 0, 12))]

    def monitors(self):
        return list(self._monitors)

    def set_wallpaper(self, images):
        self.walls.append(dict(images))
        biggest = platforms.largest(self._monitors).id
        self.current = Path(images.get(biggest) or next(iter(images.values())))

    def current_wallpaper(self):
        return self.current

    def notify(self, title, body, actions=(), image=None, on_click=None):
        self.notifications.append((title, body, [label for label, _ in actions]))

    def open_url(self, url):
        self.opened.append(url)

    def ui_language(self):
        return self.language


def make_jpeg(path, size=(600, 380), color=(120, 90, 60)):
    from PIL import Image, ImageDraw
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color)
    ImageDraw.Draw(image).rectangle((size[0] // 4, size[1] // 4, size[0] // 2, size[1] // 2), fill=(200, 180, 40))
    image.save(path, "JPEG", quality=90)
    return path
