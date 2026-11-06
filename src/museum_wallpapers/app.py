"""The tray app: an icon by the clock with the painting's title as tooltip,
a menu with every setting, the "About this painting" card on left click, and
a scheduler thread that does what the Omarchy plugin's minute tick did."""

import argparse
import datetime
import sys
import threading
import time
import traceback

from . import APP_NAME, VERSION, card, core, resources, strings

TICK_SECONDS = 60
LOG_LIMIT = 1_000_000


class TimestampedLog:
    """stderr for a windowed app: a log file in the state folder."""

    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if path.exists() and path.stat().st_size > LOG_LIMIT:
                path.replace(path.with_suffix(".old.log"))
        except OSError:  # held open by another instance; rotate next time
            pass
        self._file = open(path, "a", encoding="utf-8", buffering=1)
        self._lock = threading.Lock()

    def write(self, text):
        if not text.strip():
            return len(text)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            for line in text.rstrip("\n").splitlines():
                self._file.write(f"{stamp} {line}\n")
        return len(text)

    def flush(self):
        self._file.flush()


class App:
    def __init__(self, background=False):
        self.background = background
        self.platform = core.PLATFORM
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.switching = threading.Lock()
        self.icon = None
        self.instance = None
        self.menu_lock = threading.Lock()
        self.menu_signature = None
        self.card = card.Card({
            "next": self.next,
            "open": self.read_more,
            "save": self.save,
            "more_by": self.more_by,
            "more_of": self.more_of,
            "show_all": self.show_all,
            "set": self.set_setting,
            "toggle": self.toggle_setting,
            "toggle_autostart": self.toggle_autostart,
            "open_collection": self.open_collection,
        }, work_area=self.platform.work_area)

    # -- start and stop

    def two_copies(self):
        """Both the Store package and the installer's copy are installed.
        The installer's copy steps aside: no autostart, and a launch opens the
        Store app instead (returns True: exit). The Store copy cannot remove
        the other one (its registry writes are virtualized), so it says once
        a day how to uninstall it."""
        try:
            other = self.platform.other_copy()
        except OSError:
            return False
        if not other:
            return False
        if not self.platform.packaged:
            try:
                self.platform.set_autostart(False)
            except OSError as exc:
                print(f"museum-wallpapers: could not turn off autostart: {exc}", file=sys.stderr)
            if not self.background:
                self.platform.launch_store_app()
            return True
        stamp = core.STATE / "two-copies.json"
        if time.time() - core.read_json(stamp, {}).get("at", 0) >= 86400:
            core.write_json(stamp, {"at": time.time()})
            config = core.load_config()
            core.notify(strings.t("two_copies_title", config), strings.t("two_copies", config))
        return False

    def run(self):
        if self.two_copies():
            return 0
        # Before anything touches shared files: a second launch only asks
        # the running app to open its card.
        if self.platform.name == "windows":
            from .platforms.windows import SingleInstance
            self.instance = SingleInstance()
            if not self.instance.first:
                self.instance.signal_running()
                return 0

        log = TimestampedLog(core.STATE / "museum-wallpapers.log")
        if sys.stderr is None or getattr(sys, "frozen", False):
            sys.stderr = log
        sys.excepthook = lambda *exc: log.write("".join(traceback.format_exception(*exc)))
        threading.excepthook = lambda args: log.write(
            "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))
        print(f"museum-wallpapers: {APP_NAME} {VERSION} starting on {self.platform.name}"
              f"{' (Store package)' if self.platform.packaged else ''}", file=sys.stderr)
        self.platform.setup()
        if self.platform.launched_at_startup():
            self.background = True
        icon_path = resources.icon_file(core.CACHE.parent)
        if hasattr(self.platform, "register_app"):
            try:
                self.platform.register_app(icon_path)
            except OSError as exc:
                print(f"museum-wallpapers: could not register for notifications: {exc}", file=sys.stderr)

        import pystray
        self.pystray = pystray
        core.RUNNER = self.run_command
        self.icon = pystray.Icon("MuseumWallpapers", resources.icon_image(64), APP_NAME,
                                 menu=pystray.Menu(self.menu_items))
        if hasattr(self.platform, "balloon"):
            self.platform.balloon = lambda title, body: self.icon.notify(body[:250], title[:60])
        if self.instance:
            self.instance.listen(self.about)
        self.icon.run(setup=self._started)
        return 0

    def _started(self, icon):
        icon.visible = True
        threading.Thread(target=self._scheduler, name="scheduler", daemon=True).start()
        if not (core.STATE / "state.json").exists():
            # First run: say where the app lives; the first painting follows within seconds.
            core.notify(APP_NAME, strings.t("started", core.load_config()))
        elif not self.background:
            # Opened from the Start menu rather than at sign-in: show what is on screen.
            threading.Timer(1.0, self.about).start()

    def quit(self, *_args):
        self.stop.set()
        self.wake.set()
        self.card.quit()  # waits for Tk to be torn down on its own thread
        if self.icon:
            self.icon.stop()

    # -- background work

    def _scheduler(self):
        while not self.stop.is_set():
            self._safely(self.tick)
            self.wake.wait(TICK_SECONDS)
            self.wake.clear()

    def tick(self):
        with self.switching:
            core.cmd_tick(core.load_config(), None)
        self.refresh()

    def run_command(self, command):
        """core.spawn() lands here: helper commands on threads, not processes."""
        work = {"prefetch": core.cmd_prefetch, "notify": core.cmd_notify}.get(command)
        if work:
            threading.Thread(target=self._safely, args=(lambda: work(core.load_config(), None),),
                             name=command, daemon=True).start()

    @staticmethod
    def _safely(work):
        try:
            work()
        except Exception:  # noqa: BLE001 - logged; the app keeps running
            print("museum-wallpapers: " + traceback.format_exc(), file=sys.stderr)

    def _in_background(self, work):
        threading.Thread(target=self._safely, args=(work,), daemon=True).start()

    # -- actions

    def next(self, *_args):
        if not self.switching.acquire(blocking=False):
            return  # a switch is already running; presses meanwhile are ignored
        config = core.load_config()
        self.card.busy(strings.t("finding", config))

        def work():
            try:
                core.cmd_next(core.load_config(), None)
            finally:
                self.switching.release()
            self.refresh()

        self._in_background(work)

    def read_more(self, *_args):
        self._in_background(lambda: core.cmd_open(core.load_config(), None))

    def save(self, *_args):
        self._in_background(lambda: core.cmd_keep(core.load_config(), None))

    def about(self, *_args):
        data = self.card_data()
        self.card.show(data)
        if not self.card.available:  # no Tk in this build: a notification instead
            self._in_background(lambda: core.cmd_notify(core.load_config(), None))

    def _filter(self, action, **values):
        args = argparse.Namespace(action=action, artist=None, movement=None, genre=None, years=None, label=None,
                                  switch=True)
        for key, value in values.items():
            setattr(args, key, value)
        if not self.switching.acquire(blocking=False):
            return

        def work():
            try:
                core.cmd_filter(core.load_config(), args)
            finally:
                self.switching.release()
            self.refresh()

        self.card.busy(strings.t("finding", core.load_config()))
        self._in_background(work)

    def more_by(self, qid, name):
        self._filter("set", artist=[qid], label=name)

    def more_of(self, qid, name):
        self._filter("set", movement=[qid], label=name)

    def show_all(self, *_args):
        self._filter("clear")

    def set_setting(self, key, value):
        core.save_setting(key, value)
        self.refresh()
        self.wake.set()  # re-frame or switch now, not in a minute

    def toggle_setting(self, key):
        self.set_setting(key, not core.load_config()[key])

    def _autostart(self):
        try:
            return self.platform.autostart_enabled()
        except Exception:  # noqa: BLE001
            return False

    def toggle_autostart(self, *_args):
        wanted = not self._autostart()
        try:
            done = self.platform.set_autostart(wanted)
        except Exception as exc:  # noqa: BLE001 - OSError, or WinRT errors in the Store build
            print(f"museum-wallpapers: autostart: {exc}", file=sys.stderr)
            done = False
        if wanted and done is False:
            core.notify(APP_NAME, strings.t("autostart_blocked", core.load_config()))
        self.refresh()

    def open_collection(self, *_args):
        self.platform.open_folder(core.load_config()["saveDir"])

    # -- what the menu, tooltip and card show

    def current(self):
        config = core.load_config()
        return config, core.status(config)

    def refresh(self):
        """Tooltip, menu and an open card after anything changed."""
        if not self.icon:
            return
        config, status = self.current()
        info = status.get("info")
        tooltip = APP_NAME
        if info and info.get("title"):
            tooltip = " — ".join(x for x in (info["title"], info.get("artist")) if x)
        # Windows tooltips hold 127 characters.
        self.icon.title = tooltip if len(tooltip) <= 120 else tooltip[:119] + "…"
        # Rebuilding the native menu destroys the old one, possibly while it is
        # open: only when what it shows changed, and one thread at a time.
        # The win32 menu bakes in check marks when built, so every setting it shows is part of it.
        signature = (bool(status.get("active")), repr(status.get("filter")), self._autostart(),
                     *(config[key] for key in ("language", "languageSetting", "intervalMinutes", "fame", "fit",
                                               "caption", "localized", "localizedBy", "notifyOnChange")))
        with self.menu_lock:
            if signature != self.menu_signature:
                self.menu_signature = signature
                self.icon.update_menu()
        if self.card.is_open:
            self.card.update(self.card_data(config, status))

    def card_data(self, config=None, status=None):
        if config is None:
            config, status = self.current()
        labels = {key: strings.t(key, config) for key in strings.STRINGS["en"]}
        info = status.get("info") if status.get("active") else None
        data = {"labels": labels, "info": info, "error": status.get("error") or ""}
        if info:
            data["preview"] = status.get("image")
            data["byline"] = core.byline(info)
            data["place"] = " · ".join(x for x in (info.get("museum"), info.get("movement")) if x)
            more = []
            if info.get("artistId") and info.get("artist"):
                more.append((strings.t("more_by", config, name=info["artist"]),
                             ("more_by", info["artistId"], info["artist"])))
            if info.get("movementId") and info.get("movement"):
                more.append((strings.t("more_of", config, name=info["movement"]),
                             ("more_of", info["movementId"], info["movement"])))
            data["more"] = more
        override = status.get("filter")
        if override:
            data["filter"] = strings.t("showing_only", config, name=filter_label(override))
        data["settings"] = self.card_settings(config)
        return data

    # -- settings: the tray menu and the card's gear show the same list

    def settings_spec(self, config):
        """The settings, in order: ("choices", label, key, [(value, label)], check_key),
        ("toggle", label, key), ("autostart", label), ("command", label, action)."""
        t = lambda key, **values: strings.t(key, config, **values)  # noqa: E731
        languages = [("auto", t("lang_auto"))] + [(code, strings.LANGUAGE_NAMES[code]) for code in core.LANGUAGES[1:]]
        spec = [
            ("choices", t("change_every"), "intervalMinutes",
             [(m, strings.interval_label(m, config)) for m in core.INTERVALS], "intervalMinutes"),
            ("choices", t("artists"), "fame", [(f, t(f"fame_{f}")) for f in ("famous", "known", "any")], "fame"),
            ("choices", t("fit"), "fit", [(f, t(f"fit_{f}")) for f in ("blur", "auto", "wall", "cover")], "fit"),
            ("choices", t("caption"), "caption",
             [(c, t(f"caption_{c}")) for c in ("off", "bottom-right", "bottom-left", "top-right", "top-left")],
             "caption"),
            ("choices", t("language"), "language", languages, "languageSetting"),
            ("choices", t("localized"), "localized",
             [(v, t(f"loc_{v}")) for v in ("prefer", "only", "all")], "localized"),
            ("choices", t("localized_by"), "localizedBy",
             [(v, t(f"by_{v}")) for v in ("title", "article")], "localizedBy"),
            ("toggle", t("notify_on_change"), "notifyOnChange"),
        ]
        if self.platform.name == "windows":
            spec.append(("autostart", t("start_with_windows")))
        spec.append(("command", t("open_collection"), "open_collection"))
        return spec

    def card_settings(self, config):
        """The settings for the card's gear menu, with what is checked now."""
        items = []
        for entry in self.settings_spec(config):
            kind, label = entry[0], entry[1]
            if kind == "choices":
                _, _, key, values, check_key = entry
                items.append(("menu", label, [(text, ("set", key, value), config[check_key] == value)
                                              for value, text in values]))
            elif kind == "toggle":
                items.append(("check", label, ("toggle", entry[2]), bool(config[entry[2]])))
            elif kind == "autostart":
                items.append(("check", label, ("toggle_autostart",), self._autostart()))
            else:
                items.append(("command", label, (entry[2],)))
        return items

    def menu_items(self):
        pystray = self.pystray
        Item, Menu = pystray.MenuItem, pystray.Menu
        config, status = self.current()
        t = lambda key, **values: strings.t(key, config, **values)  # noqa: E731
        has_painting = bool(status.get("active"))

        def choice(key, value, label, check_key):
            return Item(label, lambda *_: self.set_setting(key, value),
                        checked=lambda _item: core.load_config().get(check_key) == value, radio=True)

        items = [
            Item(t("about"), self.about, default=True),
            Item(t("next"), self.next),
            Item(t("read_more"), self.read_more, enabled=has_painting),
            Item(t("save"), self.save, enabled=has_painting),
            Menu.SEPARATOR,
        ]
        override = status.get("filter")
        if override:
            items += [Item(t("showing_only", name=filter_label(override)), None, enabled=False),
                      Item(t("show_all"), self.show_all), Menu.SEPARATOR]
        actions = {"open_collection": self.open_collection}
        for entry in self.settings_spec(config):
            kind, label = entry[0], entry[1]
            if kind == "choices":
                _, _, key, values, check_key = entry
                items.append(Item(label, Menu(*[choice(key, value, text, check_key) for value, text in values])))
            elif kind == "toggle":
                items.append(Item(label, (lambda k: lambda *_: self.toggle_setting(k))(entry[2]),
                                  checked=(lambda k: lambda _i: core.load_config()[k])(entry[2])))
            elif kind == "autostart":
                items.append(Item(label, self.toggle_autostart, checked=lambda _i: self._autostart()))
            else:
                items.append(Item(label, actions[entry[2]]))
        items += [
            Menu.SEPARATOR,
            Item(t("quit"), self.quit),
        ]
        return items


def filter_label(override):
    names = [x.get("label") or x.get("id") for key in ("artists", "movements", "genres")
             for x in override.get(key, []) if isinstance(x, dict)]
    years = ""
    if override.get("yearFrom") is not None or override.get("yearTo") is not None:
        years = f"{override.get('yearFrom') or ''}–{override.get('yearTo') or ''}"
    return ", ".join(x for x in names + [years] if x)


def main(background=False):
    return App(background=background).run()


if __name__ == "__main__":
    sys.exit(main("--background" in sys.argv))
