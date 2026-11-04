"""Settings, locks, strings and the platform helpers that need no Windows."""

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from helpers import FakePlatform, Monitor, core, filelock_module, framing, platforms, strings
from museum_wallpapers import resources


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.tmp.name)
        mock.patch.object(core, "SETTINGS", root / "settings.json").start()
        mock.patch.object(core, "CACHE", root / "cache").start()
        mock.patch.object(core, "PLATFORM", FakePlatform(language="ru")).start()

    def tearDown(self):
        mock.patch.stopall()
        self.tmp.cleanup()

    def test_save_setting_keeps_other_keys(self):
        core.SETTINGS.write_text(json.dumps({"fit": "wall", "future": 1}), encoding="utf-8")
        core.save_setting("intervalMinutes", 15)
        self.assertEqual(json.loads(core.SETTINGS.read_text(encoding="utf-8")),
                         {"fit": "wall", "future": 1, "intervalMinutes": 15})
        self.assertEqual(core.load_config()["intervalMinutes"], 15)

    def test_save_setting_rejects_unknown_keys(self):
        with self.assertRaises(KeyError):
            core.save_setting("color", "red")

    def test_placard_is_migrated_on_save(self):
        core.SETTINGS.write_text(json.dumps({"placard": "top-left"}), encoding="utf-8")
        core.save_setting("fit", "wall")
        saved = json.loads(core.SETTINGS.read_text(encoding="utf-8"))
        self.assertEqual(saved, {"caption": "top-left", "fit": "wall"})

    def test_auto_language_follows_windows(self):
        config = core.load_config()
        self.assertEqual((config["languageSetting"], config["language"]), ("auto", "ru"))
        core.save_setting("language", "de")
        config = core.load_config()
        self.assertEqual((config["languageSetting"], config["language"]), ("de", "de"))


class LockTest(unittest.TestCase):
    def test_threads_exclude_each_other(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / ".lock"
            first = filelock_module.acquire(path)
            self.assertIsNone(filelock_module.acquire(path, wait=False))
            got = []
            waiter = threading.Thread(target=lambda: got.append(filelock_module.acquire(path)))
            waiter.start()
            time.sleep(0.3)
            self.assertEqual(got, [])
            first.close()
            waiter.join(5)
            self.assertEqual(len(got), 1)
            got[0].close()
            with filelock_module.acquire(path, wait=False) as again:
                self.assertIsNotNone(again)

    def test_timeout(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / ".lock"
            with filelock_module.acquire(path):
                start = time.monotonic()
                self.assertIsNone(filelock_module.acquire(path, timeout=0.3))
                self.assertGreaterEqual(time.monotonic() - start, 0.25)


class SpawnTest(unittest.TestCase):
    def test_runner_takes_helper_commands(self):
        calls = []
        with mock.patch.object(core, "RUNNER", calls.append):
            core.spawn("prefetch")
        self.assertEqual(calls, ["prefetch"])

    def test_command_line(self):
        self.assertEqual(core.command_line("tick")[1:], ["-m", "museum_wallpapers", "tick"])
        with mock.patch.object(core.sys, "frozen", True, create=True):
            self.assertEqual(core.command_line("tick")[1:], ["tick"])


class StringsTest(unittest.TestCase):
    def test_every_language_has_every_key(self):
        keys = {lang: set(table) for lang, table in strings.STRINGS.items()}
        for lang, found in keys.items():
            self.assertEqual(found, keys["en"], lang)

    def test_fallback_to_english(self):
        self.assertEqual(strings.t("quit", {"language": "de"}), "Quit")
        self.assertEqual(strings.t("quit", {"language": "ru"}), "Выход")
        self.assertEqual(strings.t("more_by", "en", name="Claude Monet"), "More by Claude Monet")

    def test_interval_labels(self):
        self.assertEqual(strings.interval_label(15), "15 minutes")
        self.assertEqual(strings.interval_label(60), "1 hour")
        self.assertEqual(strings.interval_label(180, "ru"), "3 часа")
        self.assertEqual(strings.interval_label(360, "ru"), "6 часов")
        self.assertEqual(strings.interval_label(0, "ru"), "Только по запросу")

    def test_menu_values_are_known(self):
        for minutes in core.INTERVALS:
            strings.interval_label(minutes)
        for lang in core.LANGUAGES[1:]:
            self.assertIn(lang, strings.LANGUAGE_NAMES)


class PlatformHelpersTest(unittest.TestCase):
    def test_language_codes(self):
        from museum_wallpapers.platforms.base import language_code
        self.assertEqual(language_code("ru_RU.UTF-8"), "ru")
        self.assertEqual(language_code("ru-RU"), "ru")
        self.assertEqual(language_code("Russian_Russia"), "ru")
        self.assertEqual(language_code(""), "")

    def test_largest_monitor(self):
        found = [Monitor("a", 1920, 1080), Monitor("b", 3840, 2160), Monitor("c", 2160, 3840)]
        self.assertEqual(platforms.largest(found).id, "b")
        self.assertEqual(platforms.largest([]), platforms.DEFAULT_MONITOR)

    def test_dev_platform_round_trip(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, \
                mock.patch.dict(os.environ, {"MUSEUM_WALLPAPERS_HOME": tmp,
                                             "MUSEUM_WALLPAPERS_SCREEN": "1920x1080,2560x1440"}):
            dev = platforms.DevPlatform()
            found = dev.monitors()
            self.assertEqual([(m.width, m.height) for m in found], [(1920, 1080), (2560, 1440)])
            image = Path(tmp) / "a.jpg"
            dev.set_wallpaper({"monitor-1": Path(tmp) / "small.jpg", "monitor-2": image})
            self.assertEqual(dev.current_wallpaper(), image)


class CaptionTest(unittest.TestCase):
    def test_long_titles_wrap_and_stay_inside(self):
        from PIL import Image
        canvas = Image.new("RGB", (1920, 1080), (90, 90, 90))
        caption = {"title": "A very long title of a painting that goes on and on about a harbour at dusk " * 2,
                   "byline": "Somebody Famous · 1850", "museum": "A Museum With A Very Long Name Indeed"}
        out = framing.draw_caption(canvas, caption, "top-left", (0, 0, 0, 0))
        # Label within the left 35% of the screen, nothing drawn on the right.
        right = out.crop((int(1920 * 0.36), 0, 1920, 1080))
        self.assertEqual(right.getextrema(), ((90, 90), (90, 90), (90, 90)))
        self.assertNotEqual(out.getpixel((40, 40)), (90, 90, 90))

    def test_no_title_no_caption(self):
        from PIL import Image
        canvas = Image.new("RGB", (400, 300), (90, 90, 90))
        self.assertEqual(framing.draw_caption(canvas, {"title": ""}).getextrema(), ((90, 90),) * 3)

    def test_crop_fraction(self):
        self.assertAlmostEqual(framing.crop_fraction(3840, 2160, (3840, 2160)), 0)


class CaptionTextTest(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(framing.clean_text("Sea\u2009\u200bcoast"), "Sea coast")
        self.assertEqual(framing.clean_text("Soft\u00adhyphen\u00a0and\u202fspaces"), "Softhyphen and spaces")
        self.assertEqual(framing.clean_text("\u200eLeft-to-right\u200f"), "Left-to-right")
        self.assertEqual(framing.clean_text(None), "")

    def test_fonts_are_picked_by_coverage(self):
        with mock.patch.object(framing, "_coverage", side_effect=lambda p: {
                "latin": frozenset(map(ord, "abcdefghijklmnopqrstuvwxyz ")),
                "cjk": frozenset(map(ord, "abc神奈川"))}.get(p)):
            self.assertEqual(framing.pick_font(["latin", "cjk"], "sea"), "latin")
            self.assertEqual(framing.pick_font(["latin", "cjk"], "神奈川"), "cjk")
            self.assertEqual(framing.pick_font(["latin", "cjk"], "abc 神"), "cjk")  # covers all
            self.assertEqual(framing.pick_font(["latin", "cjk"], "sea 神"), "latin")  # misses fewest
            self.assertEqual(framing.drawable("latin", "sea 神奈川 x"), "sea x")
            self.assertEqual(framing.drawable(None, "anything"), "anything")


class PackagingTest(unittest.TestCase):
    """The Store package's manifest and images (built on Windows by packaging/build.py)."""

    ROOT = Path(__file__).resolve().parent.parent

    def test_manifest(self):
        import re
        import xml.etree.ElementTree as ET
        text = (self.ROOT / "packaging" / "AppxManifest.xml").read_text(encoding="utf-8")
        root = ET.fromstring(text.replace("{VERSION}", "0.1.1.0"))
        ns = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
              "desktop": "http://schemas.microsoft.com/appx/manifest/desktop/windows10"}
        identity = root.find("m:Identity", ns)
        self.assertEqual(identity.get("Name"), "dpsk.MuseumWallpapers")
        self.assertTrue(identity.get("Publisher").startswith("CN="))
        task = root.find(".//desktop:StartupTask", ns)
        windows_py = (self.ROOT / "src" / "museum_wallpapers" / "platforms" / "windows.py").read_text(encoding="utf-8")
        self.assertIn(f'STARTUP_TASK_ID = "{task.get("TaskId")}"', windows_py)
        for logo in re.findall(r'(Assets\\[\w.]+\.png)', text):
            self.assertIn(logo.split("\\")[1], resources.MSIX_ASSETS)

    def test_assets(self):
        from PIL import Image
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            folder = resources.write_msix_assets(tmp)
            for name, size in resources.MSIX_ASSETS.items():
                with Image.open(folder / name) as image:
                    self.assertEqual(image.size, size)
                    self.assertEqual(image.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()
