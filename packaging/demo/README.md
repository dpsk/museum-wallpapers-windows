# Demo recording

The scripts behind the Windows demo on [nikaliuk.in](https://nikaliuk.in/) and in this README
(`windows-<lang>-3.*` in `media/demo` of dpsk/dpsk.github.io; how to cut and publish it is in
`media/demo/RECORDING-windows.md` there).

1. Put an `ffmpeg.exe` with `ddagrab` and `h264_nvenc` next to `take.ps1` (FFmpeg 6 or later).
2. `powershell -ExecutionPolicy Bypass -File settings.ps1 en` — landscapes only, English interface;
   it backs up `settings.json`, restarts the Store app and waits for nothing, so give it a minute to
   fill its queue, then run `museum-wallpapers next` once.
3. Show the app's tray icon on the taskbar (not under ^) and pass its position in physical pixels
   with `-Tray X,Y` if it is not at the default.
4. `powershell -ExecutionPolicy Bypass -File take.ps1 -Lang en` — minimizes every window, records
   24 s at 60 fps (`dda-en-HHmmss.mkv`), glides the cursor to the tray icon while a second launch of
   the app opens its card, clicks Next and the close button in the card, twice.
5. Repeat 2 and 4 with `ru`, then `settings.ps1 restore`.

Check the paintings before publishing: the landscape filter still lets through some nudity and
grim subjects.
