# Museum Wallpapers for Windows

Your desktop as a slow museum walk: an endless supply of public-domain
paintings from museums worldwide, a new one every hour (or whenever you like),
with the title, artist, year, museum and a short story one click away.

The Windows version of the Omarchy plugin
[omarchy-museum-wallpapers](https://github.com/dpsk/omarchy-museum-wallpapers):
the same painting picker, descriptions, filters, prefetch queue and Save, in a
tray app you install with one setup file.

Website: **[nikaliuk.in](https://nikaliuk.in/)**

- **Endless and high-resolution.** Tens of thousands of paintings listed on
  Wikidata, shown from their Wikimedia Commons scans: only scans large enough
  for your screen (up to 4K), only landscape-shaped works, never tiles or
  detail crops.
- **Every monitor.** Each screen gets the painting sized for it, whatever its
  resolution, orientation or scaling (125%, 150%…).
- **Know what you are looking at.** A small museum label in a corner of the
  wallpaper; click the tray icon for the card with the story, **Read more**,
  **Save**, and **More by …** / **More Impressionism**.
- **Famous painters first.** By default only the ~280 painters covered by 60+
  Wikipedias; widen it to ~1200 or to everyone.
- **In your language.** Titles and stories from the Wikipedia in your Windows
  language (or any you pick); the app itself speaks English and Russian.

## Install

**Microsoft Store** (recommended): [Museum Wallpapers](https://apps.microsoft.com/detail/9PLK21LK9KSL)
— installs without warnings and updates itself (live once Microsoft certifies it).

**Or the installer** from
[Releases](https://github.com/dpsk/museum-wallpapers-windows/releases):
download `MuseumWallpapers-Setup-<version>.exe` and run it. It is not
code-signed, so Windows says "Windows protected your PC": click
**More info → Run anyway**. No administrator rights needed. (The `.msix` on
the release page is the Store upload; it does not install by itself.)

The first painting appears within a few seconds; a gilt-frame icon sits by
the clock (it may hide under the **^** arrow — drag it onto the taskbar to
keep it visible). Requires Windows 10 or 11 and an internet connection to
Wikimedia.

## Using it

| Do | What happens |
| --- | --- |
| Hover the tray icon | Title and artist |
| Click the tray icon | The card: preview, title, artist, museum, story, **Next**, **Read more**, **Save**, **More by …** |
| Right-click the tray icon | Next painting, Read more, Save, and all settings |
| Open *Museum Wallpapers* from the Start menu while it runs | Opens the card |

**Save** copies the painting to `Pictures\Museum Wallpapers` with a line in
`CREDITS.md`; that folder is also what is shown when there is no internet.

## Settings

All of these are in the tray menu; they are stored in
`%APPDATA%\MuseumWallpapers\settings.json`, which you can also edit by hand.

| Key | Default | Menu | Meaning |
| --- | --- | --- | --- |
| `intervalMinutes` | `60` | Change every | Minutes between paintings; `0` changes only on demand |
| `fame` | `"famous"` | Artists | `famous` (~280 painters), `known` (~1200) or `any` |
| `fit` | `"blur"` | Paintings that are not widescreen | `blur` (framed by a blurred copy of itself), `auto` (fill unless that crops more than 10%), `wall` (on a dark wall), `cover` (fill and crop) |
| `caption` | `"bottom-right"` | Caption on wallpaper | `off`, `bottom-right`, `bottom-left`, `top-right`, `top-left` |
| `language` | `"auto"` | Language | Wikipedia language for titles and stories; `auto` follows Windows |
| `notifyOnChange` | `false` | Notify when it changes | A notification with the painting each time it changes |
| `saveDir` | `Pictures\Museum Wallpapers` | Open collection folder | Where **Save** puts paintings; also the offline fallback |
| `prefetchCount` | `6` | | Paintings downloaded (and framed) ahead, so **Next** is instant |
| `cacheSize` | `24` | | Downloaded paintings kept |
| `minRatio`, `maxRatio` | `1.3`, `2.0` | | Accepted width/height ratios |
| `filters` | none | | `yearFrom`, `yearTo`, `artists`, `movements`, `genres`; see the [plugin's README](https://github.com/dpsk/omarchy-museum-wallpapers#filters) |

**Start with Windows** in the menu adds or removes the app from sign-in
(on by default; in the Store version it is also in Settings → Apps → Startup).

## Remove

**Settings → Apps → Installed apps → Museum Wallpapers → Uninstall.** This
removes the app, its cache and settings (the Store version keeps them in its
own package folder, which Windows removes); paintings you saved stay in
`Pictures\Museum Wallpapers`. The wallpaper on screen stays until you pick
another one.

## Data, privacy and licensing

See [PRIVACY.md](PRIVACY.md).

The app talks only to Wikimedia: `commons.wikimedia.org`, `upload.wikimedia.org`,
`www.wikidata.org`, `query.wikidata.org` and `*.wikipedia.org`. Requests carry
a User-Agent naming this app and nothing about you.

The images are photographs of public-domain paintings. Stories are excerpts
from Wikipedia (CC BY-SA); **Read more** links to the source article.

Cache and state: `%LOCALAPPDATA%\MuseumWallpapers` (a log is in `state\museum-wallpapers.log`).

## Troubleshooting

- **Nothing changes:** click the tray icon: the card shows the last error in red;
  the log is `%LOCALAPPDATA%\MuseumWallpapers\state\museum-wallpapers.log`.
- **Check the installation:** run
  `"%LOCALAPPDATA%\Programs\Museum Wallpapers\MuseumWallpapers.exe" selftest --out "%TEMP%\mw.json"`
  and open the JSON file: every check should say `"ok": true`.
- **Windows Spotlight or a slideshow keeps replacing the painting:** set
  *Settings → Personalization → Background* to *Picture* once.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest                        # unit tests (any OS; Windows-only ones skip elsewhere)
python -m museum_wallpapers             # the tray app (from src/, or after pip install -e .)
python -m museum_wallpapers next        # core commands: tick, next, status, keep, filter …
python -m museum_wallpapers selftest    # what the build can and cannot do
python packaging/build.py               # Windows only: app + self-test + installer + Store .msix
```

Off Windows, `MUSEUM_WALLPAPERS_PLATFORM=dev` (the default there) runs the whole
rotation against a fake desktop: the "wallpaper" is a JSON file in the state
folder, and `MUSEUM_WALLPAPERS_SCREEN=2560x1440,1920x1080` sets the monitors.
`MUSEUM_WALLPAPERS_HOME` puts all folders under one directory.

Layout:

| Path | What |
| --- | --- |
| `src/museum_wallpapers/core.py` | The plugin's `museum.py`: picking, describing, queue, Save, filters, commands |
| `src/museum_wallpapers/platforms/` | What the OS does: `windows.py` (IDesktopWallpaper, monitors, toasts, autostart), `base.py` (interface + dev stand-in) |
| `src/museum_wallpapers/framing.py` | Blur / wall / fill framing and the caption, with Pillow |
| `src/museum_wallpapers/app.py`, `card.py` | Tray icon, menu, scheduler; the card window (Tk) |
| `packaging/` | PyInstaller spec, build script, Inno Setup installer, MSIX manifest for the Store |
| `.github/workflows/build.yml` | Tests on Linux and Windows, builds the installer, attaches it to `v*` releases |

## License

MIT
