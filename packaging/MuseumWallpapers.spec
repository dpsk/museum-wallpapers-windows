# PyInstaller spec: a windowed one-folder build (starts faster than one-file).
# Run through packaging/build.py, which writes icon.ico and version_info.txt first.
# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

HERE = Path(SPECPATH)
ROOT = HERE.parent
BUILD = HERE / "build"

hiddenimports = (
    ["pystray._win32", "PIL.ImageTk", "tkinter", "comtypes.client"]
    + collect_submodules("windows_toasts")
    # windows-toasts reaches WinRT through the winrt.* namespace packages,
    # which PyInstaller cannot see through static analysis.
    + collect_submodules("winrt")
    # fontTools loads its table modules by name (cmap for the caption fonts).
    + collect_submodules("fontTools.ttLib.tables")
)

a = Analysis(
    [str(HERE / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=collect_dynamic_libs("winrt"),
    datas=[(str(BUILD / "icon.ico"), ".")],
    hiddenimports=hiddenimports,
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MuseumWallpapers",
    icon=str(BUILD / "icon.ico"),
    version=str(BUILD / "version_info.txt"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MuseumWallpapers", upx=False)
