"""Build the Windows app and its installer (run on Windows, in CI or locally):

    python packaging/build.py              # app folder + self-test + installer
    python packaging/build.py --no-installer

Steps: the built-in painter lists and painting pools (packaging/seed.py,
needs Wikidata), icon.ico and version info from the package, PyInstaller one-folder
build into dist/MuseumWallpapers, the frozen app's own `selftest` (catches
modules PyInstaller missed), Inno Setup into
dist/MuseumWallpapers-Setup-<version>.exe, and the Microsoft Store package
dist/MuseumWallpapers-<version>.0-store.msix (unsigned: the Store signs it).
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


def find_sdk_tool(name):
    """makeappx.exe / signtool.exe from the newest installed Windows SDK."""
    root = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Kits" / "10" / "bin"
    found = sorted(root.glob(f"10.*/x64/{name}"), key=lambda p: [int(x) for x in p.parts[-3].split(".")])
    return found[-1] if found else None


def build_msix(ver, app_dir):
    """The Store package: the PyInstaller folder, tile images and the
    manifest (version as a.b.c.0: the Store requires revision 0)."""
    from museum_wallpapers import resources
    makeappx = find_sdk_tool("makeappx.exe")
    if not makeappx:
        sys.exit("makeappx.exe not found: install the Windows 10/11 SDK")
    stage = BUILD / "msix"
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(app_dir, stage)
    resources.write_msix_assets(stage / "Assets")
    numbers = [int(x) for x in re.findall(r"\d+", ver)[:3]] + [0] * 3
    package_version = ".".join(str(n) for n in numbers[:3]) + ".0"
    manifest = (HERE / "AppxManifest.xml").read_text(encoding="utf-8").replace("{VERSION}", package_version)
    (stage / "AppxManifest.xml").write_text(manifest, encoding="utf-8")
    out = DIST / f"MuseumWallpapers-{package_version}-store.msix"
    subprocess.run([str(makeappx), "pack", "/d", str(stage), "/p", str(out), "/o"], check=True)
    print(f"store package: {out}")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-installer", action="store_true")
    parser.add_argument("--no-msix", action="store_true")
    parser.add_argument("--no-selftest", action="store_true")
    parser.add_argument("--no-seed", action="store_true",
                        help="reuse packaging/build/seed as it is (the app then starts from it, or from Wikidata)")
    args = parser.parse_args()
    if sys.platform != "win32":
        sys.exit("PyInstaller does not cross-compile: build on Windows (or let GitHub Actions do it).")

    ver = version()
    BUILD.mkdir(parents=True, exist_ok=True)
    from museum_wallpapers import resources
    resources.write_ico(BUILD / "icon.ico")
    (BUILD / "version_info.txt").write_text(version_info(ver), encoding="utf-8")
    if not args.no_seed:
        subprocess.run([sys.executable, str(HERE / "seed.py"), "--out", str(BUILD / "seed")], check=True)

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

    if not args.no_msix:
        build_msix(ver, app_dir)


if __name__ == "__main__":
    main()
