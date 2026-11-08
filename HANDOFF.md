# Handoff: Museum Wallpapers for Windows

Goal: a Windows version of the Omarchy plugin
[omarchy-museum-wallpapers](https://github.com/dpsk/omarchy-museum-wallpapers)
for a non-technical user: install from a single setup `.exe`, then it just
works. Endless public-domain paintings as the desktop wallpaper, changing on an
interval, with the title, artist, museum and a short story one click away.

## Status — 2026-11-04

Steps 1–3 of the plan below and the packaging are done, and the repo
[dpsk/museum-wallpapers-windows](https://github.com/dpsk/museum-wallpapers-windows)
(private for now) builds green on GitHub Actions. Release **v0.1.0** carries
the installer. What has **not** happened yet is a run of the installed app on
a real desktop (the target laptop): the tray, the card, toasts, multiple
monitors and live Wikimedia fetching are only covered by tests and the CI
runner.

First CI run (`windows-latest`, Python 3.12): 100 tests passed (1 skipped:
symlinks), the 6 Windows-only tests passed too, including a live round trip:
IDesktopWallpaper found the runner's monitor (1024×768, taskbar inset 48),
set an image and read the same path back. The frozen `MuseumWallpapers.exe
selftest` found every module (comtypes, windows_toasts/winrt, pystray._win32,
tkinter, PIL.ImageTk) and passed all checks; Inno Setup compiled a 15 MB
installer.

### 0.1.7 — Store listing in ten languages, rating dialog

`App.maybe_ask_for_review(moment)`: Store build only; `state/review.json`
holds `firstRun` (stamped at start), the card count, `retryAfter` and the
`answer`; due a week (`REVIEW_AFTER`) after the first start on Save or the
fifth card (`REVIEW_MIN_CARDS`), never again once rated or dismissed, three
days after a failure. `WindowsPlatform.request_review(owner)` calls
`StoreContext.RequestRateAndReviewAppAsync` after
`winrt.runtime.interop.initialize_with_window(context, hwnd)` (pystray's
hidden window; package `winrt-Windows.Services.Store`). The manifest
declares the ten languages (`<Resources>`; a test keeps them equal to
`strings.STRINGS`). Store screenshots: the `store-shots` workflow (run by
hand) renders `packaging/store_shots.py` on Windows — The Ninth Wave, Hunters
in the Snow, The Birth of Venus at 1920x1080, blur frame, caption from
Wikidata in each language — and force-pushes them to the `store-shots`
branch (artifact storage is out of reach of the agent's proxy). Listing
texts for the ten languages were written for Partner Center on 2026-11-07.

### 0.1.6 — defaults, two copies

Defaults `localized: only`, `localizedBy: article` (asked for on
2026-11-06; measured: 2 115 / 3 961 / 850 / 778 of the 38 390 famous
paintings have a ru / en / de / uk article). Tests block the network in
`tests/helpers.py` (`core.http_json` raises) since the default now asks
Wikidata in every search. Two installations: `Platform.other_copy()` (Store
package: the installer's exe in `%LOCALAPPDATA%\Programs\Museum Wallpapers`;
installer copy: `%LOCALAPPDATA%\Packages\<STORE_FAMILY>`), `App.two_copies()`
before the single-instance check. The Store copy cannot uninstall the other
(HKCU writes from a package are virtualized; a child process runs in the
package context too), so it only notifies, once a day. The plugin keeps its
own defaults (prefer/title) unless asked.

### 0.1.5 — ten languages, language preference (GitHub issue #2)

From the plugin's 0.1.3–0.1.4: `strings.py` has ten tables (the plugin's
`strings.json` texts for shared keys: errors, Saved, About the artist, nm_*;
Windows-only keys translated here); `t()` falls back per key and on a broken
placeholder; interval labels are `interval_<minutes>` keys (no plural code).
Core messages (NoMatch, switch errors, About the artist) follow the language.
`localized`/`localizedBy` settings, `described_in`/`prefer_described` in
`fetch_next`, `only` relaxed to `prefer` in the unfiltered fallback,
`queue_key` includes them only for `only` — as in the plugin. The card's
gear (`Card._settings_menu`) pops up the same list as the tray menu, both
built from `App.settings_spec()`. Summary 6 sentences / 600 characters, card
limit 900 characters.

### 0.1.4 — back from the plugin

The plugin's 0.1.2 (2026-11-06, ported from docs/OMARCHY-PLUGIN-HANDOFF.md
on a MacBook) added improvements of its own; these came back here:
`image_infos` without `extmetadata` and `file_metadata(pageid)` in
`describe` (measured: 50 files 7.6 s → 0.6 s); `thumb_width(screen, ratio)`
covering the height, `thumb_width_for(page)` over all monitors; one
`_load_pool` query at a time (`pools/.<key>.lock`); `alive(pid)` for claims
(`Platform.process_alive`: `os.kill(pid, 0)` on POSIX, OpenProcess +
GetExitCodeProcess on Windows — never `os.kill` there, it terminates);
`clean_text` on titles in `describe`. Not ported, already covered or
plugin-only: screen size in framed names / refit on a new screen (Windows
had per-monitor names and `screens_key`), keeping the previous framed copy
for the shell's cross-fade, detached helpers logging to the journal.

### 0.1.3 — built-in painter lists

The first run spent ~60 s on Wikidata before the first painting: the painter
list for `fame: famous` (282 painters with 60+ Wikipedias) takes ~28 s, their
paintings (38 390) another 9–20 s; `known` is 1200 painters and 94 079
paintings (a 30 MB answer, once seen cut off mid-JSON). Now
`packaging/seed.py` (run by `build.py`, so every release is fresh) writes
`fame-<level>.json.gz` (~0.9 MB and ~2.3 MB) into the build; the core's
`fame_bundle(level)` uses the cached copy in `cache/pools/fame-<level>.json`,
else the built-in one, and refreshes in a background thread (one at a time,
`pools/.fame-<level>.lock`) when the cached copy is missing or a week old; a
failed refresh is retried after 10 minutes and the old copy stays. Only `fame`
alone uses the bundle's pool; `fame` with years, artists etc. still queries
Wikidata (with the bundle's painters). The frozen self-test requires the
built-in data. To be ported to the plugin: section 9 of
[docs/OMARCHY-PLUGIN-HANDOFF.md](docs/OMARCHY-PLUGIN-HANDOFF.md).

### 0.1.2 — faster Next, caption fix

Standard thumbnail widths, 6 paintings ready and downloaded two at a time,
framed ahead, waiting for an in-flight download instead of a second one,
parallel `describe`, stage timings in the log, caption text cleanup and font
fallback. **To be ported to the Omarchy plugin:**
[docs/OMARCHY-PLUGIN-HANDOFF.md](docs/OMARCHY-PLUGIN-HANDOFF.md).

### Microsoft Store (0.1.1)

- Product reserved in Partner Center: **Museum Wallpapers**, Store ID
  `9PLK21LK9KSL`, identity `dpsk.MuseumWallpapers`, publisher
  `CN=11410CB1-4E3D-406F-8EAE-2D56EEB598E5`, PFN
  `dpsk.MuseumWallpapers_9n62pad56wkq8`. These are in
  `packaging/AppxManifest.xml`.
- `packaging/build.py` also makes `dist/MuseumWallpapers-<v>.0-store.msix`
  (unsigned; the Store signs it). CI signs a copy with a throwaway
  certificate, installs it and runs the self-test through the
  `museum-wallpapers.exe` alias, so with package identity.
- Packaged differences (`platforms/windows.py`): StartupTask
  `MuseumWallpapersStartup` instead of the Run key; cache/settings in
  `%LOCALAPPDATA%\Packages\<PFN>\LocalCache\MuseumWallpapers` by real path
  (AppData seen from inside a package is redirected and Explorer could not
  open the wallpaper); toasts under the package AUMID; a sign-in start is
  detected from the activation kind.
- Release flow: bump `VERSION`, CHANGELOG, tag `vX.Y.Z`; upload the release's
  `-store.msix` to a new Partner Center submission (Update → Packages; the
  package version must be higher, revision 0). Only one submission can be in
  progress. 0.1.7.0 is live in the Store (published 2026-11-07), and winget
  serves the Store package through its msstore source
  (`winget install 9PLK21LK9KSL -s msstore`), so no separate winget manifest is
  needed for the Store build.
- Ideas queued (2026-11-04): an update check (GitHub Releases for the
  installer build — download and run the setup silently; `StoreContext`
  update check for the Store build, which the Store itself updates); a
  `ru-ru` Store listing (add the language to `<Resources>`); publishing to the
  Store from CI (msstore CLI / Submission API, needs an Entra ID app linked
  to Partner Center).

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

### Verified in CI

- The frozen build has every module it needs (self-test).
- IDesktopWallpaper per monitor: set and read back the same path; monitor
  enumeration through COM and EnumDisplayMonitors; taskbar inset.

### Not verified yet (the laptop)

1. Monitor rects from COM matching EnumDisplayMonitors at 125–150% scaling
   (insets fall back to none when they do not match), and several monitors.
2. Toast buttons from an unpackaged app with the registry AUMID.
3. The Tk card on a real desktop: focus-out closing, position above the
   taskbar, DPI scaling.
4. Live Wikimedia fetching end to end (same code as the plugin).
5. The installer: autostart, Start menu shortcut, update over a running app,
   uninstall.

### Next steps

1. Install `MuseumWallpapers-Setup-0.1.0.exe` (Releases, or the
   `MuseumWallpapers-Setup` artifact of any CI run) on the target laptop and
   walk the list above, plus sleep and resume, offline start, first run with
   an empty cache, a Spotlight/slideshow background before install.
2. Fix what that finds; bump `VERSION` in `src/museum_wallpapers/__init__.py`,
   add a CHANGELOG entry, tag `vX.Y.Z` — CI attaches the installer to the
   release.
3. Make the repo public when ready (Settings → General → Danger Zone).
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
