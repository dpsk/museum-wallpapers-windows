"""The Windows layer, on Windows only (the CI runner and the target laptop).

Set MUSEUM_WALLPAPERS_LIVE_WALLPAPER=1 to also set a real wallpaper on every
monitor and put the previous one back (CI does; on your own desktop it
flashes a grey picture for a moment)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401 - puts src on the path

if sys.platform == "win32":
    from museum_wallpapers.platforms import windows


@unittest.skipUnless(sys.platform == "win32", "Windows only")
class WindowsHelpersTest(unittest.TestCase):
    def test_taskbar_inset(self):
        self.assertEqual(windows._inset((0, 0, 1920, 1080), (0, 0, 1920, 1032)), (0, 0, 0, 48))
        self.assertEqual(windows._inset((1920, 0, 4480, 1440), (1920, 0, 4480, 1440)), (0, 0, 0, 0))
        self.assertEqual(windows._inset((0, 0, 1920, 1080), (62, 0, 1920, 1080)), (62, 0, 0, 0))

    def test_guid_round_trip(self):
        guid = windows.GUID.parse(windows.FOLDERID_PICTURES)
        self.assertEqual(guid.Data1, 0x33E28130)

    def test_launch_command(self):
        command = windows.WindowsPlatform.launch_command()
        self.assertTrue(command.endswith("--background"))
        self.assertTrue(command.startswith('"'))


@unittest.skipUnless(sys.platform == "win32", "Windows only")
class WindowsLiveTest(unittest.TestCase):
    def setUp(self):
        self.platform = windows.WindowsPlatform()
        self.platform.setup()

    def test_folders(self):
        paths = self.platform.paths()
        self.assertTrue(str(paths["config"]).endswith("MuseumWallpapers") or os.environ.get("MUSEUM_WALLPAPERS_HOME"))
        self.assertTrue(Path(self.platform.pictures_folder()).is_absolute())

    def test_monitors_and_language(self):
        monitors = self.platform.monitors()
        print("monitors:", monitors, "work area:", self.platform.work_area(), file=sys.stderr)
        for monitor in monitors:
            self.assertGreater(monitor.width, 0)
            self.assertGreater(monitor.height, 0)
        self.assertRegex(self.platform.ui_language(), r"^[a-z]{2,3}$")
        title, body = self.platform.caption_fonts()
        self.assertTrue(body is None or Path(body).exists())

    @unittest.skipUnless(os.environ.get("MUSEUM_WALLPAPERS_LIVE_WALLPAPER") == "1", "set MUSEUM_WALLPAPERS_LIVE_WALLPAPER=1")
    def test_set_and_read_back_the_wallpaper(self):
        from PIL import Image
        monitors = self.platform.monitors()
        if not monitors:
            self.skipTest("no monitors on this session")
        before = self.platform.current_wallpaper()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            images = {}
            for n, monitor in enumerate(monitors):
                path = Path(tmp) / f"test-{n}.jpg"
                Image.new("RGB", (monitor.width, monitor.height), (90, 90, 90 + n * 20)).save(path)
                images[monitor.id] = path
            try:
                self.platform.set_wallpaper(images)
                shown = self.platform.current_wallpaper()
                print("current wallpaper:", shown, file=sys.stderr)
                self.assertIn(Path(os.path.realpath(shown)).name if shown else None,
                              {p.name for p in images.values()})
            finally:
                if before and before.exists():
                    self.platform.set_wallpaper({m.id: before for m in monitors})


if __name__ == "__main__":
    unittest.main()
