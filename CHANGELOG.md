# Changelog

## 0.1.4 — 2026-11-06

From the Omarchy plugin's 0.1.2:

- A search for the next painting is about ten times faster: candidates are
  checked by size alone, and Commons' file description is fetched only for
  the painting picked (asking for it for 50 candidates took 7.6 s instead of
  0.6 s).
- Thumbnails are wide enough to cover the screen's height too, so a wide
  painting on a 5:4 or portrait monitor is no longer upscaled.
- Several downloads that need the same filtered painting pool ask Wikidata
  once instead of each running the ~20 s query.
- A download claimed by a process that has since quit no longer holds up
  Next or keeps its painting reserved.
- Titles in the card and notifications lose invisible and odd space
  characters, as the caption already did.

## 0.1.3 — 2026-11-04

- The first painting appears in seconds instead of about a minute: the lists
  of famous and known painters and their paintings (38 000 and 94 000) come
  with the app, about 3 MB, and are refreshed from Wikidata in the background
  after the start.
- When these lists are a week old they are refreshed in the background too;
  a change of painting no longer waits for Wikidata, and a broken answer from
  it keeps the old lists instead of failing the switch.
- Pool files in the cache are written compactly (about half the size).

## 0.1.2 — 2026-11-04

- Faster Next: 6 paintings kept ready (was 3), downloaded two at a time, each
  framed for the screens while it waits, so a switch only sets the wallpaper.
- Thumbnails are requested at Wikimedia's standard widths (1280, 1920, 3840),
  which its CDN keeps ready; other widths were rendered on demand and rate
  limited.
- A Next with the queue empty waits for the download already under way
  instead of starting another one; painting details are fetched in parallel.
- The caption no longer shows boxes for unusual spaces and invisible
  characters in titles, and switches to a font that has the script (Chinese,
  Japanese, Korean, Indic, Thai) when Georgia does not.
- The log (`state\museum-wallpapers.log`) records how long each stage took.
- Paintings without a date on Wikidata no longer show the scan's date as
  their year, and long titles end on a word.

## 0.1.1 — 2026-11-04

- Microsoft Store package (MSIX): installs without the SmartScreen warning.
  In the Store build, Start with Windows is the package's startup task
  (also listed in Settings → Apps → Startup), and cache and settings live in
  the package's own folder, removed on uninstall.
- CI builds the Store package and installs it on the runner to run the
  self-test with package identity.

## 0.1.0 — 2026-11-04

First Windows version, ported from omarchy-museum-wallpapers 0.1.1.

- The plugin's core unchanged in behaviour: Wikidata/Commons picking with
  `fame`, filters, landscape and resolution checks; titles, museums and
  Wikipedia summaries in any language; the prefetch queue; offline fallback;
  Save with `CREDITS.md`. Its 60 unit tests carried over.
- Wallpaper on every monitor through IDesktopWallpaper, each sized for its
  screen (orientation and scaling included), with SystemParametersInfo as the
  fallback; re-framed when monitors or scaling change.
- Framing (`blur`, `auto`, `wall`, `cover`) with Pillow instead of ImageMagick.
- The desktop placard becomes a caption drawn into the wallpaper, clear of the
  taskbar (`caption`, default bottom right).
- Tray app with every setting in its menu, a card window with the story and
  Next / Read more / Save / More by …, toast notifications with a Read more
  button and the painting as picture, Start with Windows, one instance only
  (starting it again opens the card).
- English and Russian interface; `language: auto` follows Windows.
- Settings in `%APPDATA%\MuseumWallpapers\settings.json`; cache and state in
  `%LOCALAPPDATA%\MuseumWallpapers`.
- Per-user Inno Setup installer (no administrator prompt), PyInstaller build,
  `selftest` command, GitHub Actions build on `windows-latest`.
