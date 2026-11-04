# Changelog

## 0.1.0 — unreleased

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
