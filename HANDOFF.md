# Handoff: Museum Wallpapers for Windows

Goal: a Windows version of the Omarchy plugin
[omarchy-museum-wallpapers](https://github.com/dpsk/omarchy-museum-wallpapers)
for a non-technical user: install from a single setup `.exe`, then it just
works. Endless public-domain paintings as the desktop wallpaper, changing on an
interval, with the title, artist, museum and a short story one click away.

## Status — 2026-11-04

Steps 1–3 of the plan below and the packaging are written; **nothing has run
on Windows yet**. The code was built and tested in a Linux sandbox (Wikimedia
was unreachable there too, so no live fetch either). The first real run is the
GitHub Actions `windows-latest` job, then the target laptop.

### Done

- `src/museum_wallpapers/core.py` — the plugin's `museum.py` (v0.1.1) with
  every OS call behind `PLATFORM` (`platforms/`): `set_wallpaper`,
  `monitors`, `current_wallpaper`, `notify`, `open_url`, paths, locks
  (`filelock.py`, msvcrt/fcntl, also excludes threads), framing (`framing.py`,
  Pillow). Picking, describing, queue, Save, filters unchanged.
- Changes forced by Windows: images per monitor (a framed copy per distinct
  monitor size, `DISPLAY/<stem>.<fit>.<corner>.<w>x<h>.<inset>.jpg`); the
  placard is a caption drawn into the wallpaper, clear of the taskbar
  (`caption` setting; `placard` accepted for compatibility); `refit` also
  re-frames on caption or monitor-layout changes; settings are a flat
  `settings.json`; `language: auto` = Windows UI language; helper commands
  run on threads in the app (`core.RUNNER`) instead of detached processes;
  UTF-8 everywhere (CREDITS.md with Cyrillic was the trap).
- `platforms/windows.py` — IDesktopWallpaper (comtypes, own interface
  definition, COM init per thread) with SPI fallback; DPI awareness
  (per-monitor v2); monitors + taskbar insets from EnumDisplayMonitors;
  toasts via windows-toasts with a Read more button and the painting as hero
  image, tray balloon as fallback; AUMID registration; Run-key autostart;
  named mutex + event (a second launch opens the card); Georgia Italic /
  Segoe UI for the caption.
- `app.py` — pystray tray icon, menu exactly as proposed below, minute
  scheduler thread, log file in `state\museum-wallpapers.log`.
  `card.py` — Tk card window (dark, bottom-right flyout): preview, title,
  byline, museum · movement, summary, Next / Read more / Save, More by … /
  More …, active filter with "show all". Checked visually under Xvfb.
- `strings.py` — English and Russian UI.
- `selftest.py` — `MuseumWallpapers.exe selftest --out x.json` checks
  bundled modules, Windows APIs and framing without touching the wallpaper;
  the build fails if the frozen app fails it.
- Packaging: `packaging/MuseumWallpapers.spec` (PyInstaller onedir,
  windowed), `packaging/build.py`, `packaging/installer.iss` (Inno Setup,
  per-user, no admin, en/ru, autostart task, AUMID on the Start menu
  shortcut, uninstall removes cache and settings), icon drawn by
  `resources.py`.
- `.github/workflows/build.yml` — tests on Ubuntu and Windows, a live
  wallpaper round trip on the runner (non-fatal), build + self-test +
  installer, artifact upload, release on `v*` tags.
- Tests: 95 passing (the plugin's 60 adapted + Windows-layer logic, framing and
  caption, settings, locks, strings, tray menu and card data, a full
  scheduler tick); 6 more run only on Windows.

- A second review of the Windows layer against the library sources fixed:
  the single-instance check now runs before the log is touched; Tk is torn
  down on its own thread (else a Tcl panic on Quit); all COM calls run on
  one long-lived thread that never uninitializes; the tray menu is rebuilt
  only when what it shows changed (pystray destroys the old native menu,
  possibly while open); a refreshed card keeps its window and focus; one
  failed card render no longer kills the card; CI upgrades Inno Setup to
  6.3+ (`x64compatible`).

### Not verified yet (first CI run / the laptop)

1. The frozen build: hidden imports for `winrt` (windows-toasts) and
   `pystray._win32`; the self-test step catches what is missing.
2. IDesktopWallpaper per monitor, and that the path it reports back equals
   the one set (the "is this ours" check depends on it).
3. Monitor rects from COM matching EnumDisplayMonitors at 125–150% scaling
   (insets fall back to none when they do not match).
4. Toast buttons from an unpackaged app with the registry AUMID.
5. The Tk card on a real desktop: focus-out closing, position above the
   taskbar, DPI scaling.
6. Live Wikimedia fetching end to end (same code as the plugin).

### Next steps

1. ~~Create the repo `dpsk/museum-wallpapers-windows`~~ (created private on
   2026-11-04; make it public in Settings when ready), push, let CI run; fix
   what the Windows job reports (download `selftest-report` if the build
   fails).
2. Install the artifact on the target laptop and walk the checklist:
   multiple monitors, scaling 125–150%, sleep and resume, offline start,
   first run with an empty cache, Spotlight/slideshow background before
   install, uninstall.
3. Tag `v0.1.0` for a release with the installer attached.
4. Later: optional global hotkeys (off by default), winget manifest, update
   check against GitHub releases, code signing (Azure Trusted Signing).

---

## The plan (written before any code)

### What carries over from the Omarchy plugin

`museum.py` in the plugin repo (Python, standard library only) already does the
hard part, and most of it is OS-independent:

- Picking paintings: Wikidata SPARQL pools (`famous_painters`, `entity_pool`,
  `sparql_query`), Commons random search for `fame: any`, filters by years,
  artists, movements, genres, the `fame` setting (famous ~280 painters / known
  ~1200 / any), landscape and resolution checks (`usable`), tile detection.
- Describing them: Wikidata labels in any language, museum, movement, the
  Wikipedia summary, Commons QuickStatements cleanup (`object_name`,
  `commons_description`).
- The prefetch queue (`prefetchCount`, oldest first, sidecar JSON claims),
  repeats for small pools, error kinds and backoff, offline fallback, Save to a
  collection folder with `CREDITS.md`.
- 60 unit tests in `test/test_museum.py` cover these.

Read the plugin's README and museum.py first; the behaviour and the edge cases
(see its CHANGELOG and the tests) were reviewed several times and should be
kept.

### What has to change on Windows

| Omarchy plugin | Windows replacement |
| --- | --- |
| `fcntl.flock` locks | `msvcrt.locking` on a lock file, or a small cross-platform lock helper |
| `hyprctl monitors -j` for screen size | `ctypes` + `EnumDisplayMonitors` / `GetSystemMetrics` (handle DPI awareness) |
| `omarchy-theme-bg-set` | `IDesktopWallpaper` COM (per monitor, set position `FILL`) via `comtypes`, or `SystemParametersInfoW(SPI_SETDESKWALLPAPER)` as a fallback |
| ImageMagick `magick` for `fit` framing | Pillow (`ImageFilter.GaussianBlur` on a downscaled copy, then paste), bundled |
| `notify-send` | Windows toast notifications (`windows-toasts` or `winotify`) with a "Read more" button |
| `xdg-open` | `os.startfile(url)` / `webbrowser` |
| `~/.config/omarchy/shell.json` settings | `%APPDATA%\MuseumWallpapers\settings.json` |
| XDG cache/state dirs | `%LOCALAPPDATA%\MuseumWallpapers\{cache,state}` |
| Quickshell service: minute tick, IPC | The app's own scheduler thread; single-instance guard (named mutex) |
| Bar widget + popup card | Tray icon (`pystray`) with a menu, and a small card window |
| Desktop placard (layer-shell window under all windows) | Draw the caption into the wallpaper image itself with Pillow; no overlay window needed |
| Hyprland hotkeys | Optional global hotkeys (`RegisterHotKey` via ctypes), off by default |

### Proposed app

- **Tray app**, starts with Windows (shortcut in the Startup folder or the
  `Run` registry key, created by the installer, toggle in the menu).
- **Tray menu**: About this painting, Next painting, Read more, Save to
  collection, Change every (15m … 1d, Off), Artists (Famous / Known / Any),
  Fit (Blur / Auto / Wall / Fill), Caption on wallpaper (on/off, corner),
  Start with Windows, Open collection folder, Quit.
- **Card window** ("About this painting"): preview, title, artist · year,
  museum · movement, summary, Next / Read more / Save, More by … / More ….
  Easiest good-looking option: `pywebview` (uses the Edge WebView2 runtime
  that ships with Windows 10/11) rendering a small HTML/CSS card. Tkinter is
  smaller but looks dated; PySide6 adds ~80 MB. *(Built with Tkinter in the
  end, styled flat and dark: pywebview needs the main thread, which pystray
  also wants.)*
- **Caption**: rendered into the wallpaper corner (same look as the Omarchy
  placard: italic title, small byline, translucent dark box).

### Packaging

- PyInstaller (`--onedir` is faster to start than `--onefile`) with an icon and
  version info, then an **Inno Setup** installer: Start menu entry, optional
  autostart, clean uninstall (also removes the cache).
- PyInstaller does not cross-compile: the `.exe` must be built on Windows, on a
  real machine or a GitHub Actions `windows-latest` runner.
- **Code signing**: unsigned installers trigger SmartScreen ("Windows protected
  your PC" → More info → Run anyway). Fine for family use; for public release
  consider Azure Trusted Signing or a code-signing certificate.
- Later: winget manifest, auto-update check against GitHub releases.

### Effort estimate (agent time)

- MVP (tray icon, rotation, wallpaper on every monitor, toast with the
  painting info, Save, settings file): about 1 day.
- Polished (card window, all menu settings, caption on wallpaper, autostart,
  installer, icon, tests for the Windows layer, GitHub Actions build): 3-5 days.
- Signing and winget: extra, mostly paperwork.

### Where to work

- Refactoring the shared core and its tests can happen anywhere, including
  Omarchy.
- Everything Windows-specific (wallpaper COM, tray, toasts, DPI, PyInstaller,
  the installer) needs a real Windows machine to run and test. Best: Claude Code
  on Windows (native Python, not WSL, because WSL cannot set the Windows
  wallpaper or show the tray), in a new repo `dpsk/museum-wallpapers-windows`.
- Add a GitHub Actions `windows-latest` workflow early: unit tests plus a
  PyInstaller + Inno Setup build that uploads the installer as an artifact, so
  builds do not depend on one machine.

### Suggested first steps

1. ~~New repo; copy `museum.py` and its tests from the plugin repo at its current
   release; keep the plugin's logic, behaviour and tests.~~ Done (repo not
   created on GitHub yet).
2. ~~Move the platform calls behind a small interface (`set_wallpaper`,
   `screen_sizes`, `notify`, `open_url`, `lock`, paths, `frame_image`) with a
   Windows implementation; keep the tests passing with mocks.~~ Done.
3. ~~Tray app + scheduler + single-instance guard; then the card window; then
   packaging.~~ Written, not yet run on Windows.
4. Test on the target laptop: multiple monitors, scaling 125-150%, sleep and
   resume, offline start, first run with an empty cache.
