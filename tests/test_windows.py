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

    def test_process_alive(self):
        import subprocess
        self.assertTrue(windows.WindowsPlatform.process_alive(os.getpid()))
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        self.assertFalse(windows.WindowsPlatform.process_alive(child.pid))
        self.assertFalse(windows.WindowsPlatform.process_alive(999999999))

    def test_other_copy(self):
        from unittest import mock
        platform = windows.WindowsPlatform()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
            platform.packaged = False
            self.assertIsNone(platform.other_copy())
            store = Path(tmp) / "Packages" / windows.STORE_FAMILY
            store.mkdir(parents=True)
            self.assertEqual(platform.other_copy(), store)
            platform.packaged = True
            self.assertIsNone(platform.other_copy())
            exe = Path(tmp) / "Programs" / "Museum Wallpapers" / "MuseumWallpapers.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"")
            self.assertEqual(platform.other_copy(), exe)

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
        title, body, *fallbacks = self.platform.caption_fonts()
        print("caption fonts:", title, body, fallbacks, file=sys.stderr)
        self.assertTrue(body is None or Path(body).exists())
        for font in fallbacks:
            self.assertTrue(Path(font).exists())
        # Windows ships fonts for Chinese/Japanese/Korean; titles in them must not become boxes.
        from museum_wallpapers import framing
        cjk = framing.pick_font([title, body, *fallbacks], "神奈川沖浪裏")
        self.assertEqual(framing.missing(cjk, "神奈川沖浪裏"), 0)
        self.assertEqual(framing.missing(title, "Sea coast"), 0)

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




@unittest.skipUnless(sys.platform == "win32", "Windows only")
class ProxyTest(unittest.TestCase):
    """WinHTTP's auto-proxy with a PAC file, as on a company network."""

    def serve(self, body):
        import http.server
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                data = body.encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ns-proxy-autoconfig")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}/proxy.pac"

    def test_pac_names_a_proxy(self):
        pac = self.serve('function FindProxyForURL(url, host) {'
                         ' return host == "commons.wikimedia.org" ? "PROXY 10.1.2.3:8080; DIRECT" : "DIRECT"; }')
        self.assertEqual(windows.auto_proxy("https://commons.wikimedia.org/w/api.php", config_url=pac),
                         "http://10.1.2.3:8080")
        self.assertEqual(windows.auto_proxy("https://upload.wikimedia.org/x.jpg", config_url=pac), "")

    def test_no_pac_file(self):
        self.assertIsNone(windows.auto_proxy("https://commons.wikimedia.org/", config_url="http://127.0.0.1:9/none.pac"))

    def platform_with(self, config, answers):
        from unittest import mock
        platform = windows.WindowsPlatform()
        self.enterContext(mock.patch.object(windows, "ie_proxy_config", return_value=config))
        lookup = self.enterContext(mock.patch.object(windows, "auto_proxy", side_effect=answers))
        return platform, lookup

    def test_cache_per_host_and_forget(self):
        config = {"autoDetect": False, "autoConfigUrl": "http://pac/proxy.pac", "proxy": None, "bypass": None}
        platform, lookup = self.platform_with(config, ["http://p:8080", "", "http://q:8080"])
        proxied = {"http": "http://p:8080", "https": "http://p:8080"}
        self.assertEqual(platform.proxies("https://commons.wikimedia.org/w/api.php?x=1"), proxied)
        self.assertEqual(lookup.call_args.args[0], "https://commons.wikimedia.org/")
        self.assertEqual(platform.proxies("https://commons.wikimedia.org/other"), proxied)
        self.assertEqual(platform.proxies("https://upload.wikimedia.org/a.jpg"), {})
        self.assertEqual(lookup.call_count, 2)
        platform.forget_proxy("https://commons.wikimedia.org/")
        self.assertEqual(platform.proxies("https://commons.wikimedia.org/"),
                         {"http": "http://q:8080", "https": "http://q:8080"})
        self.assertEqual(platform.proxies("https://upload.wikimedia.org/b.jpg"), {})

    def test_no_wpad_is_remembered_for_every_host(self):
        config = {"autoDetect": True, "autoConfigUrl": None, "proxy": None, "bypass": None}
        platform, lookup = self.platform_with(config, [None])
        windows._lookup.error = windows.ERROR_WINHTTP_AUTODETECTION_FAILED
        self.addCleanup(vars(windows._lookup).clear)
        self.assertIsNone(platform.proxies("https://commons.wikimedia.org/"))
        self.assertIsNone(platform.proxies("https://upload.wikimedia.org/"))
        self.assertEqual(lookup.call_count, 1)

    def test_other_failure_is_retried_for_that_host_only(self):
        config = {"autoDetect": False, "autoConfigUrl": "http://pac/proxy.pac", "proxy": None, "bypass": None}
        platform, lookup = self.platform_with(config, ["http://p:8080", None, "http://p:8080"])
        self.assertIsNotNone(platform.proxies("https://commons.wikimedia.org/"))
        self.assertIsNone(platform.proxies("https://upload.wikimedia.org/"))
        # The failure for upload does not switch commons off.
        self.assertIsNotNone(platform.proxies("https://commons.wikimedia.org/"))
        self.assertEqual(lookup.call_count, 2)

    def test_no_automatic_proxy(self):
        config = {"autoDetect": False, "autoConfigUrl": None, "proxy": "fixed:80", "bypass": None}
        platform, lookup = self.platform_with(config, [])
        self.assertIsNone(platform.proxies("https://commons.wikimedia.org/"))
        lookup.assert_not_called()

    def test_ie_config_reads(self):
        config = windows.ie_proxy_config()
        self.assertIn("autoDetect", config)


if __name__ == "__main__":
    unittest.main()
