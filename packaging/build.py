"""Build the Windows app and its installer (run on Windows, in CI or locally):

    python packaging/build.py              # app folder + self-test + installer
    python packaging/build.py --no-installer

Steps: icon.ico and version info from the package, PyInstaller one-folder
build into dist/MuseumWallpapers, the frozen app's own `selftest` (catches
modules PyInstaller missed), then Inno Setup into
dist/MuseumWallpapers-Setup-<version>.exe.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / "build"
DIST = ROOT / "dist"
sys.path.insert(0, str(ROOT / "src"))


def version():
    text = (ROOT / "src" / "museum_wallpapers" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'VERSION = "([^"]+)"', text).group(1)


def version_info(ver):
    numbers = [int(x) for x in re.findall(r"\d+", ver)[:3]]
    numbers += [0] * (4 - len(numbers))
    tup = tuple(numbers)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tup}, prodvers={tup}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'dpsk'),
      StringStruct('FileDescription', 'Museum Wallpapers'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'MuseumWallpapers'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', 'MuseumWallpapers.exe'),
      StringStruct('ProductName', 'Museum Wallpapers'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def find_iscc():
    candidates = [os.environ.get("ISCC", ""), shutil.which("iscc") or "", shutil.which("ISCC") or ""]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                 os.environ.get("LOCALAPPDATA") and str(Path(os.environ["LOCALAPPDATA"]) / "Programs")):
        if base:
            candidates.append(str(Path(base) / "Inno Setup 6" / "ISCC.exe"))
    return next((c for c in candidates if c and Path(c).exists()), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-installer", action="store_true")
    parser.add_argument("--no-selftest", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32":
        sys.exit("PyInstaller does not cross-compile: build on Windows (or let GitHub Actions do it).")

    ver = version()
    BUILD.mkdir(parents=True, exist_ok=True)
    from museum_wallpapers import resources
    resources.write_ico(BUILD / "icon.ico")
    (BUILD / "version_info.txt").write_text(version_info(ver), encoding="utf-8")

    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(DIST),
                    "--workpath", str(BUILD / "pyinstaller"), str(HERE / "MuseumWallpapers.spec")], check=True)
    app_dir = DIST / "MuseumWallpapers"
    exe = app_dir / "MuseumWallpapers.exe"
    print(f"built {exe}")

    if not args.no_selftest:
        report_path = BUILD / "selftest.json"
        report_path.unlink(missing_ok=True)
        home = BUILD / "selftest-home"
        env = {**os.environ, "MUSEUM_WALLPAPERS_HOME": str(home)}
        result = subprocess.run([str(exe), "selftest", "--out", str(report_path)], env=env, timeout=180)
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if result.returncode != 0 or not report.get("ok"):
            sys.exit(f"the frozen app failed its self-test (exit code {result.returncode})")

    if not args.no_installer:
        iscc = find_iscc()
        if not iscc:
            sys.exit("Inno Setup 6 not found: install it (winget install JRSoftware.InnoSetup) or set ISCC")
        subprocess.run([iscc, f"/DAppVersion={ver}", f"/DSourceDir={app_dir}", f"/DOutputDir={DIST}",
                        f"/DIconFile={BUILD / 'icon.ico'}", str(HERE / "installer.iss")], check=True)
        print(f"installer: {DIST / f'MuseumWallpapers-Setup-{ver}.exe'}")


if __name__ == "__main__":
    main()
