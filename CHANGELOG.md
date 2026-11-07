# Changelog

## 0.1.7 — 2026-11-07

- The Store version asks once for a rating, through the Store's own dialog:
  a week or more after the first start, when you save a painting or open
  the card for the fifth time. Rated or dismissed, it never asks again.
- The Store package declares all ten interface languages, so the Microsoft
  Store lists the app (and its page) in each of them.
- `packaging/store_shots.py` and the `store-shots` workflow render the
  Store screenshots with the app's own framing and caption, in every
  listing language.

## 0.1.6 — 2026-11-06

- By default only paintings with a Wikipedia article in your language are
  shown (`localized: only`, `localizedBy: article`), so the story under
  **Read more** is in your language. Of the famous painters' 38 390
  paintings that leaves 2 115 in Russian, 3 961 in English, 850 in German;
  the earlier behaviour is one menu click away.
- Installed both from the Microsoft Store and with the installer from
  GitHub, the two copies no longer compete at sign-in (the older one could
  win and run instead): the installer's copy turns its autostart off and
  hands over to the Store app, and the Store app says once a day how to
  uninstall the other copy.

## 0.1.5 — 2026-11-06

From the Omarchy plugin's 0.1.3–0.1.4:

- The interface speaks ten languages: English, Русский, Українська, Deutsch,
  Français, Español, Italiano, Nederlands, Polski, Português — menu, card,
  notifications and error messages. Any other language gets an English
  interface, with titles and stories still in that language.
- Paintings described in your language come first: **Paintings described in
  my language** (show them first / only them / no preference) and
  **Described means** (a title in your language, or a Wikipedia article in
  it). For Russian only about a fifth of the famous painters' works have a
  Russian title, so the default puts those first.
- The card has a gear that opens the settings, the same list as the tray
  menu, and a longer story (Wikipedia's first six sentences instead of four;
  Commons descriptions up to 600 characters).

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
