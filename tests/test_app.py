"""The tray app's menu, tooltip and card data, with pystray's dummy backend."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import FakePlatform, app_module, core, make_jpeg

os.environ.setdefault("PYSTRAY_BACKEND", "dummy")
try:
    import pystray
except ImportError:  # pragma: no cover - CI installs it
    pystray = None


def flatten(items, depth=0):
    for item in items:
        if item is pystray.Menu.SEPARATOR:
            continue
        yield depth, item
        if item.submenu:
            yield from flatten(list(item.submenu.items), depth + 1)


@unittest.skipIf(pystray is None, "pystray is not installed")
class AppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(os.path.realpath(self.tmp.name))
        self.cache, self.state = root / "cache", root / "state"
        self.platform = FakePlatform()
        for patch in (mock.patch.object(core, "CACHE", self.cache),
                      mock.patch.object(core, "QUEUE", self.cache / "queue"),
                      mock.patch.object(core, "DISPLAY", self.cache / "display"),
                      mock.patch.object(core, "STATE", self.state),
                      mock.patch.object(core, "SETTINGS", root / "settings.json"),
                      mock.patch.object(core, "PLATFORM", self.platform),
                      mock.patch.object(core, "RUNNER", lambda command: self.app.run_command(command))):
            patch.start()
        core.save_setting("saveDir", str(root / "saved"))
        self.app = app_module.App()
        self.app.pystray = pystray
        self.app.icon = pystray.Icon("test", None, "x", menu=pystray.Menu(self.app.menu_items))
        self.app.icon.update_menu = lambda: None  # the dummy backend has no native menu

    def tearDown(self):
        mock.patch.stopall()
        self.tmp.cleanup()

    def show_painting(self):
        painting = make_jpeg(self.cache / "commons-5.jpg")
        core.write_json(painting.with_suffix(".json"), {
            "id": "Q1", "title": "The Ninth Wave", "artist": "Ivan Aivazovsky", "artistId": "Q186212",
            "year": "1850", "museum": "Russian Museum", "movement": "Romanticism", "movementId": "Q37068",
            "summary": "A storm at sea.", "url": "https://en.wikipedia.org/wiki/The_Ninth_Wave"})
        self.platform.current = painting
        core.record(painting)
        return painting

    def labels(self):
        return [(depth, item.text) for depth, item in flatten(self.app.menu_items())]

    def test_menu_without_a_painting(self):
        labels = [text for _, text in self.labels()]
        self.assertEqual(labels[:4], ["About this painting", "Next painting", "Read more", "Save to collection"])
        items = dict((item.text, item) for _, item in flatten(self.app.menu_items()))
        self.assertFalse(items["Read more"].enabled)
        self.assertTrue(items["About this painting"].default)
        self.assertIn("Quit", labels)
        self.assertNotIn("Start with Windows", labels)  # only on Windows

    def test_settings_from_the_menu(self):
        items = dict((item.text, item) for _, item in flatten(self.app.menu_items()))
        self.assertTrue(items["1 hour"].checked)
        items["15 minutes"](self.app.icon)
        self.assertEqual(core.load_config()["intervalMinutes"], 15)
        items = dict((item.text, item) for _, item in flatten(self.app.menu_items()))
        self.assertTrue(items["15 minutes"].checked)
        self.assertFalse(items["1 hour"].checked)
        items["Dark wall"](self.app.icon)
        items["Top left"](self.app.icon)
        items["Notify when it changes"](self.app.icon)
        config = core.load_config()
        self.assertEqual((config["fit"], config["caption"], config["notifyOnChange"]), ("wall", "top-left", True))
        self.assertTrue(self.app.wake.is_set())

    def test_menu_in_russian(self):
        core.save_setting("language", "ru")
        labels = [text for _, text in self.labels()]
        self.assertIn("Следующая картина", labels)
        self.assertIn("Русский", labels)
        self.assertIn("3 часа", labels)

    def test_tooltip_and_card_for_a_painting(self):
        painting = self.show_painting()
        self.app.refresh()
        self.assertEqual(self.app.icon.title, "The Ninth Wave — Ivan Aivazovsky")
        data = self.app.card_data()
        self.assertEqual(data["byline"], "Ivan Aivazovsky · 1850")
        self.assertEqual(data["place"], "Russian Museum · Romanticism")
        self.assertEqual(data["preview"], str(painting))
        self.assertEqual(data["more"], [("More by Ivan Aivazovsky", ("more_by", "Q186212", "Ivan Aivazovsky")),
                                        ("More Romanticism", ("more_of", "Q37068", "Romanticism"))])
        items = dict((item.text, item) for _, item in flatten(self.app.menu_items()))
        self.assertTrue(items["Read more"].enabled)

    def test_long_titles_fit_the_tooltip(self):
        painting = self.show_painting()
        core.write_json(painting.with_suffix(".json"), {"title": "T" * 200, "artist": "A"})
        self.app.refresh()
        self.assertLessEqual(len(self.app.icon.title), 120)

    def test_temporary_filter_shows_in_menu_and_card(self):
        self.show_painting()
        core.write_json(self.state / "filter.json", {"artists": [{"id": "Q186212", "label": "Ivan Aivazovsky"}],
                                                     "movements": [], "genres": []})
        labels = [text for _, text in self.labels()]
        self.assertIn("Showing only: Ivan Aivazovsky", labels)
        self.assertIn("Show all paintings again", labels)
        self.assertEqual(self.app.card_data()["filter"], "Showing only: Ivan Aivazovsky")

    def test_more_by_sets_the_filter_and_switches(self):
        self.show_painting()
        with mock.patch.object(core, "cmd_next") as cmd_next:
            self.app.more_by("Q186212", "Ivan Aivazovsky")
            for _ in range(50):
                if cmd_next.called:
                    break
                import time
                time.sleep(0.05)
        filt = core.read_json(self.state / "filter.json")
        self.assertEqual(filt["artists"], [{"id": "Q186212", "label": "Ivan Aivazovsky"}])
        cmd_next.assert_called_once()

    def test_first_tick_shows_a_painting_with_its_caption(self):
        """The whole path the scheduler takes, with Wikimedia replaced by a
        fetch that drops one painting into the queue."""
        config = core.load_config()

        def fetch(_config, unfiltered=False, note=None):
            image = make_jpeg(self.cache / "queue" / "commons-9.jpg", size=(800, 500))
            core.write_json(image.with_suffix(".json"), {"title": "Poppies", "artist": "Claude Monet", "year": "1873",
                                                         "filter": core.queue_key(core.load_config())})
            return image

        with mock.patch.object(core, "fetch_next", side_effect=fetch), \
                mock.patch.object(self.app, "run_command") as run_command:
            self.app.tick()
        wall = self.platform.walls[-1]["m1"]
        self.assertEqual(wall.parent, self.cache / "display")
        self.assertIn(".blur.bottom-right.384x216.", wall.name)
        self.assertEqual(self.app.icon.title, "Poppies — Claude Monet")
        run_command.assert_called_with("prefetch")
        status = core.status(config)
        self.assertTrue(status["active"])
        self.assertEqual(status["image"], str(self.cache / "commons-9.jpg"))
        # Not due again for an hour.
        with mock.patch.object(core, "fetch_next") as fetch_again, mock.patch.object(self.app, "run_command"):
            self.app.tick()
        fetch_again.assert_not_called()

    def test_helper_commands_run_on_threads(self):
        with mock.patch.object(core, "cmd_prefetch") as prefetch:
            self.app.run_command("prefetch")
            for _ in range(50):
                if prefetch.called:
                    break
                import time
                time.sleep(0.05)
        prefetch.assert_called_once()


class FilterLabelTest(unittest.TestCase):
    def test_label(self):
        self.assertEqual(app_module.filter_label({"artists": [{"id": "Q1", "label": "Monet"}], "yearFrom": 1850}),
                         "Monet, 1850–")


if __name__ == "__main__":
    unittest.main()
