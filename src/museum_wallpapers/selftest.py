"""`museum-wallpapers selftest [--out FILE]`: checks that this build has
everything it needs (the libraries PyInstaller has to bundle, the Windows
APIs, the folders) without changing the wallpaper, and writes a JSON report.
CI runs it against the built .exe; it also helps on a machine where the app
misbehaves. Exit code 0 when everything needed works."""

import importlib
import json
import platform
import sys
import traceback
from pathlib import Path

from . import VERSION

REQUIRED = ["PIL.Image", "PIL.ImageFilter", "pystray", "tkinter", "PIL.ImageTk", "fontTools.ttLib"]
WINDOWS_REQUIRED = ["comtypes", "windows_toasts", "pystray._win32", "winreg",
                    "winrt.windows.applicationmodel", "winrt.windows.applicationmodel.activation"]


def run(out=None):
    report = {"version": VERSION, "python": sys.version, "frozen": bool(getattr(sys, "frozen", False)),
              "os": platform.platform(), "modules": {}, "checks": {}, "ok": True}

    def check(name, work, required=True):
        try:
            report["checks"][name] = {"ok": True, "value": work()}
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            report["checks"][name] = {"ok": False, "error": repr(exc), "trace": traceback.format_exc(limit=3)}
            if required:
                report["ok"] = False

    modules = REQUIRED + (WINDOWS_REQUIRED if sys.platform == "win32" else [])
    for name in modules:
        try:
            importlib.import_module(name)
            report["modules"][name] = "ok"
        except Exception as exc:  # noqa: BLE001
            report["modules"][name] = repr(exc)
            report["ok"] = False

    from . import core, framing, resources
    check("platform", lambda: core.PLATFORM.name)
    check("setup", lambda: core.PLATFORM.setup() or "done")
    check("paths", lambda: {k: str(v) for k, v in core.PLATFORM.paths().items()})
    check("monitors", lambda: [m._asdict() for m in core.PLATFORM.monitors()])
    check("current_wallpaper", lambda: str(core.PLATFORM.current_wallpaper()), required=False)
    check("work_area", lambda: core.PLATFORM.work_area(), required=False)
    check("ui_language", lambda: core.PLATFORM.ui_language())
    check("fonts", lambda: [str(f) for f in core.PLATFORM.caption_fonts()])
    check("packaged", lambda: {"packaged": core.PLATFORM.packaged,
                               "family": getattr(sys.modules.get(type(core.PLATFORM).__module__), "PACKAGE_FAMILY", None),
                               "aumid": getattr(sys.modules.get(type(core.PLATFORM).__module__), "PACKAGED_AUMID", None)})
    check("autostart", lambda: core.PLATFORM.autostart_enabled())
    check("settings", lambda: {k: v for k, v in core.load_config().items() if k != "filters"})

    def frame():
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "painting.jpg"
            Image.new("RGB", (800, 500), (120, 90, 60)).save(src)
            out_path = framing.frame(src, Path(tmp) / "framed.jpg", "blur", (1920, 1080),
                                     {"title": "Test", "byline": "Painter · 1850", "museum": "Museum"},
                                     "bottom-right", (0, 0, 0, 48), core.PLATFORM.caption_fonts())
            return framing.image_size(out_path)

    check("framing", frame)
    check("icon", lambda: resources.icon_image(64).size)

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    elif sys.stdout is not None:
        print(text)
    return 0 if report["ok"] else 1
